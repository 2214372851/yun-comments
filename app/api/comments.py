from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db, check_db_connection, check_redis_connection
from app.core.config import settings
from app.core.exceptions import ValidationException, NotFoundError, DatabaseException
from app.services.comment_service import get_comment_service
from app.schemas.comment import (
    CommentCreate, CommentResponse, CommentListResponse, 
    CommentQuery, CommentUpdate, HealthCheck, ErrorResponse
)
from app.utils.rate_limiter import limiter, check_email_rate_limit_for_comment
from app.utils.helpers import ResponseUtils
from typing import Dict, Any
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
    response_model=CommentListResponse,
    summary="获取评论列表",
    description="获取指定页面的评论列表，支持分页和排序"
)
@limiter.limit("10/minute")
async def get_comments(
    request: Request,
    page: str,
    page_num: int = 1,
    page_size: int = 20,
    sort: str = "created_at",
    order: str = "desc",
    db: Session = Depends(get_db)
):
    """获取评论列表"""
    try:
        # 验证查询参数
        if page_size > settings.MAX_PAGE_SIZE:
            page_size = settings.MAX_PAGE_SIZE
        
        query = CommentQuery(
            page=page,
            page_num=page_num,
            page_size=page_size,
            sort=sort,
            order=order
        )
        
        # 获取评论服务
        comment_service = get_comment_service(db)
        
        # 查询评论
        result = await comment_service.get_comments(query)
        
        return CommentListResponse(**result)
        
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
@limiter.limit("5/minute")
async def create_comment(
    request: Request,
    comment_data: CommentCreate,
    db: Session = Depends(get_db)
):
    """创建评论"""
    try:
        # 获取客户端信息
        client_ip = getattr(request.state, 'client_ip', request.client.host)
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