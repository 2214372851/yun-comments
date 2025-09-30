from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db, check_db_connection, check_redis_connection
from app.core.config import settings
from app.core.exceptions import ValidationException, NotFoundError, DatabaseException
from app.services.comment_service import get_comment_service
from app.schemas.comment import (
    CommentCreate, CommentResponse, CommentListResponse, 
    CommentQuery, CommentUpdate, HealthCheck, ErrorResponse,
    CursorPaginationResponse, RepliesQuery
)
from app.utils.rate_limiter import limiter, check_comment_rate_limit
from app.utils.helpers import ResponseUtils
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["评论系统"],
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "资源不存在"},
        429: {"model": ErrorResponse, "description": "请求过于频繁"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"}
    }
)


@router.get(
    "/comments",
    response_model=CursorPaginationResponse,
    summary="获取评论列表（只返回顶级评论及回复数）",
    description="获取指定页面的顶级评论列表，每条评论包含回复数量"
)
@limiter.limit("30/minute")
async def get_comments(
    request: Request,
    page: str,
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """获取顶级评论列表（不包含回复内容）"""
    try:
        query = CommentQuery(
            page=page,
            cursor=cursor,
            limit=limit,
            sort=sort,
            order=order,
            parent_only=True  # 强制为 True
        )
        
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 查询评论
        result = await comment_service.get_comments(query)
        
        return CursorPaginationResponse(**result)
        
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in get_comments: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取评论失败")


@router.post(
    "/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建评论",
    description="创建新评论或回复现有评论"
)
@limiter.limit("10/minute")
async def create_comment(
    request: Request,
    comment_data: CommentCreate,
    db: Session = Depends(get_db)
):
    """创建评论"""
    try:
        # 检查评论提交限流（5分钟内最多3次）
        await check_comment_rate_limit(request)
        
        # 获取客户端信息
        client_ip = getattr(request.state, 'client_ip', request.client.host if request.client else '127.0.0.1')
        user_agent = getattr(request.state, 'user_agent', request.headers.get("user-agent", ""))
        
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 创建评论
        comment = await comment_service.create_comment(
            comment_data=comment_data,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        return CommentResponse.from_orm(comment)
        
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in create_comment: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建评论失败")


@router.delete(
    "/comments/{comment_id}",
    summary="删除评论",
    description="软删除指定评论（管理员功能）"
)
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """删除评论"""
    try:
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 删除评论
        success = await comment_service.delete_comment(comment_id)
        
        if success:
            return ResponseUtils.success_response(message="评论删除成功")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除评论失败")
        
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in delete_comment: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除评论失败")


@router.put(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="更新评论",
    description="更新指定评论内容（管理员功能）"
)
async def update_comment(
    comment_id: int,
    update_data: CommentUpdate,
    db: Session = Depends(get_db)
):
    """更新评论"""
    try:
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 更新评论
        comment = await comment_service.update_comment(comment_id, update_data)
        
        return CommentResponse.from_orm(comment)
        
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in update_comment: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新评论失败")


@router.get(
    "/comments/{comment_id}/replies",
    response_model=CursorPaginationResponse,
    summary="获取评论回复",
    description="获取指定评论的回复列表"
)
async def get_comment_replies(
    comment_id: int,
    cursor: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """获取评论回复"""
    try:
        query = RepliesQuery(
            parent_id=comment_id,
            cursor=cursor,
            limit=limit
        )
        
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 查询回复
        result = await comment_service.get_replies(query)
        
        return CursorPaginationResponse(**result)
        
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in get_comment_replies: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取回复失败")


@router.get(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="获取单个评论",
    description="根据ID获取指定评论详情"
)
async def get_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """获取单个评论"""
    try:
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 查询评论
        comment = await comment_service.get_comment_by_id(comment_id)
        
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")
        
        return CommentResponse.from_orm(comment)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_comment: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取评论失败")


@router.get(
    "/stats/{page}",
    summary="获取页面统计",
    description="获取指定页面的评论统计信息"
)
async def get_page_stats(
    page: str,
    db: Session = Depends(get_db)
):
    """获取页面评论统计"""
    try:
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 获取统计信息
        stats = await comment_service.get_page_stats(page)
        
        return ResponseUtils.success_response(data=stats, message="获取统计信息成功")
        
    except Exception as e:
        logger.error(f"Unexpected error in get_page_stats: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取统计信息失败")


@router.get(
    "/health",
    response_model=HealthCheck,
    summary="健康检查",
    description="检查系统各组件运行状态"
)
async def health_check():
    """健康检查"""
    try:
        # 检查数据库连接
        db_status = await check_db_connection()
        
        # 检查Redis连接
        redis_status = await check_redis_connection()
        
        # 确定整体状态
        overall_status = "healthy" if db_status and redis_status else "unhealthy"
        
        return HealthCheck(
            status=overall_status,
            timestamp=datetime.now(),
            database=db_status,
            redis=redis_status,
            version=settings.APP_VERSION
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(
            status="error",
            timestamp=datetime.now(),
            database=False,
            redis=False,
            version=settings.APP_VERSION
        )