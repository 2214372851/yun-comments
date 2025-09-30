"""
简化的评论服务实现，支持游标分页和IP限流
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc, or_
from app.models.comment import Comment
from app.schemas.comment import (
    CommentCreate, CommentUpdate, CommentQuery, 
    RepliesQuery, CursorPaginationResponse, CommentResponse
)
from app.core.exceptions import NotFoundError, ValidationException, DatabaseException
from app.utils.helpers import SecurityUtils, CacheUtils
from app.utils.user_info import system_detector, location_service
from app.core.database import get_redis
from app.core.config import settings
from typing import List, Optional, Dict, Any
import logging
import json
import base64
from datetime import datetime

logger = logging.getLogger(__name__)


class SimplifiedCommentService:
    """简化的评论服务类"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = get_redis()

    def _encode_cursor(self, value: Any, comment_id: int) -> str:
        """编码游标"""
        try:
            # 处理datetime类型
            if isinstance(value, datetime):
                value = value.isoformat()
            
            cursor_data = {
                'value': value,
                'id': comment_id
            }
            cursor_json = json.dumps(cursor_data, default=str)
            return base64.b64encode(cursor_json.encode()).decode()
        except Exception:
            return ""

    def _decode_cursor(self, cursor: str) -> Optional[Dict]:
        """解码游标"""
        try:
            cursor_json = base64.b64decode(cursor.encode()).decode()
            cursor_data = json.loads(cursor_json)
            
            # 尝试解析datetime
            if isinstance(cursor_data.get('value'), str):
                try:
                    cursor_data['value'] = datetime.fromisoformat(cursor_data['value'])
                except:
                    pass
                    
            return cursor_data
        except Exception:
            return None

    async def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """从缓存获取数据"""
        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        return None

    async def _set_cache(self, cache_key: str, data: Dict, ttl: int):
        """设置缓存"""
        try:
            await self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(data, default=str, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def _clear_page_cache(self, page: str):
        """清除页面相关缓存"""
        try:
            pattern = f"*comments*{page}*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
    
    async def create_comment(
        self, 
        comment_data: CommentCreate, 
        ip_address: str, 
        user_agent: str
    ) -> Comment:
        """
        创建评论
        """
        try:
            # 验证父评论是否存在
            if comment_data.parent_id:
                parent_comment = self.db.query(Comment).filter(
                    Comment.id == comment_data.parent_id,
                    Comment.is_deleted == False
                ).first()
                
                if not parent_comment:
                    raise NotFoundError("回复的评论不存在")
                
                # 检查父评论是否在同一页面
                if parent_comment.page != comment_data.page:
                    raise ValidationException("不能回复不同页面的评论")
            
            # 检查垃圾内容
            if SecurityUtils.check_spam_content(comment_data.content):
                raise ValidationException("评论内容包含不当内容，请修改后重试")
            
            # 获取用户系统信息和地区信息
            system_type = system_detector.detect_system(user_agent)
            location = await location_service.get_location(ip_address)
            
            # 创建评论对象
            comment = Comment(
                page=comment_data.page,
                email=comment_data.email,
                email_hash=Comment.generate_email_hash(comment_data.email),
                username=comment_data.username,
                content=SecurityUtils.sanitize_content(comment_data.content),
                parent_id=comment_data.parent_id,
                ip_address=ip_address,
                user_agent=user_agent,
                system_type=system_type,
                location=location
            )
            
            # 保存到数据库
            self.db.add(comment)
            self.db.commit()
            self.db.refresh(comment)
            
            # 清除相关缓存
            await self._clear_page_cache(comment_data.page)
            
            logger.info(f"Comment created: {comment.id} by {comment.username}")
            return comment
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, (NotFoundError, ValidationException)):
                raise
            logger.error(f"Failed to create comment: {e}")
            raise DatabaseException("评论创建失败")

    async def get_comments(self, query: CommentQuery) -> Dict[str, Any]:
        """
        获取评论列表（游标分页）
        只返回顶级评论，但包含回复数量
        """
        try:
            # 尝试从缓存获取
            cache_key = CacheUtils.generate_cache_key(
                "comments_cursor", query.page, query.cursor or "", query.limit, 
                query.sort, query.order, query.parent_only
            )
            
            cached_result = await self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # 构建基础查询 - 只获取顶级评论
            base_query = self.db.query(Comment).filter(
                Comment.page == query.page,
                Comment.is_deleted == False,
                Comment.parent_id.is_(None)  # 强制只获取顶级评论
            )
            
            # 排序
            order_column = getattr(Comment, query.sort, Comment.created_at)
            if query.order == "asc":
                base_query = base_query.order_by(asc(order_column), asc(Comment.id))
            else:
                base_query = base_query.order_by(desc(order_column), desc(Comment.id))
            
            # 游标分页
            if query.cursor:
                cursor_data = self._decode_cursor(query.cursor)
                if cursor_data:
                    cursor_value = cursor_data.get('value')
                    cursor_id = cursor_data.get('id')
                    
                    if query.order == "asc":
                        base_query = base_query.filter(
                            or_(
                                order_column > cursor_value,
                                and_(order_column == cursor_value, Comment.id > cursor_id)
                            )
                        )
                    else:
                        base_query = base_query.filter(
                            or_(
                                order_column < cursor_value,
                                and_(order_column == cursor_value, Comment.id < cursor_id)
                            )
                        )
            
            # 获取数据（多获取1条用于判断是否有下一页）
            comments = base_query.limit(query.limit + 1).all()
            
            # 判断是否有下一页
            has_next = len(comments) > query.limit
            if has_next:
                comments = comments[:-1]  # 移除多余的一条
            
            # 生成下一页游标
            next_cursor = None
            if has_next and comments:
                last_comment = comments[-1]
                cursor_value = getattr(last_comment, query.sort)
                next_cursor = self._encode_cursor(cursor_value, last_comment.id)
            
            # 转换为响应模型并计算回复数量
            comment_responses = []
            for comment in comments:
                # 查询该评论的回复数量
                reply_count = self.db.query(Comment).filter(
                    Comment.parent_id == comment.id,
                    Comment.is_deleted == False
                ).count()
                
                # 直接构造符合 Pydantic 的字典格式
                comment_dict = {
                    "id": comment.id,
                    "page": comment.page,
                    "email_hash": comment.email_hash,
                    "username": comment.username,
                    "content": comment.content,
                    "parent_id": comment.parent_id,
                    "created_at": comment.created_at.isoformat() if comment.created_at else None,
                    "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
                    "system_type": comment.system_type,
                    "location": comment.location,
                    "reply_count": reply_count
                }
                comment_responses.append(comment_dict)
            
            result = {
                "comments": comment_responses,
                "has_next": has_next,
                "next_cursor": next_cursor
            }
            
            # 缓存结果
            await self._set_cache(cache_key, result, settings.CACHE_TTL)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get comments: {e}")
            raise DatabaseException("获取评论失败")
    
    async def get_replies(self, query: RepliesQuery) -> Dict[str, Any]:
        """
        获取评论的回复（游标分页）
        """
        try:
            # 尝试从缓存获取
            cache_key = CacheUtils.generate_cache_key(
                "replies", query.parent_id, query.cursor or "", query.limit
            )
            
            cached_result = await self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # 构建查询
            base_query = self.db.query(Comment).filter(
                Comment.parent_id == query.parent_id,
                Comment.is_deleted == False
            ).order_by(asc(Comment.created_at), asc(Comment.id))
            
            # 游标分页
            if query.cursor:
                cursor_data = self._decode_cursor(query.cursor)
                if cursor_data:
                    cursor_value = cursor_data.get('value')
                    cursor_id = cursor_data.get('id')
                    
                    base_query = base_query.filter(
                        or_(
                            Comment.created_at > cursor_value,
                            and_(Comment.created_at == cursor_value, Comment.id > cursor_id)
                        )
                    )
            
            # 获取数据
            replies = base_query.limit(query.limit + 1).all()
            
            # 判断是否有下一页
            has_next = len(replies) > query.limit
            if has_next:
                replies = replies[:-1]
            
            # 生成下一页游标
            next_cursor = None
            if has_next and replies:
                last_reply = replies[-1]
                next_cursor = self._encode_cursor(last_reply.created_at, last_reply.id)
            
            # 转换为响应模型
            reply_responses = []
            for reply in replies:
                reply_dict = {
                    "id": reply.id,
                    "page": reply.page,
                    "email_hash": reply.email_hash,
                    "username": reply.username,
                    "content": reply.content,
                    "parent_id": reply.parent_id,
                    "created_at": reply.created_at.isoformat() if reply.created_at else None,
                    "updated_at": reply.updated_at.isoformat() if reply.updated_at else None,
                    "system_type": reply.system_type,
                    "location": reply.location,
                    "reply_count": 0  # 回复不可再嵌套，所以回复计数为0
                }
                reply_responses.append(reply_dict)
            
            result = {
                "comments": reply_responses,
                "has_next": has_next,
                "next_cursor": next_cursor
            }
            
            # 缓存结果
            await self._set_cache(cache_key, result, settings.CACHE_TTL)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get replies: {e}")
            raise DatabaseException("获取回复失败")

    async def get_comment_by_id(self, comment_id: int) -> Optional[Comment]:
        """根据ID获取评论"""
        try:
            comment = self.db.query(Comment).filter(
                Comment.id == comment_id,
                Comment.is_deleted == False
            ).first()
            return comment
        except Exception as e:
            logger.error(f"Failed to get comment by id: {e}")
            raise DatabaseException("获取评论失败")

    async def update_comment(self, comment_id: int, update_data: CommentUpdate) -> Comment:
        """更新评论（管理员功能）"""
        try:
            comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
            if not comment:
                raise NotFoundError("评论不存在")
            
            # 更新字段
            if update_data.content is not None:
                # 使用原生SQL更新来避免类型问题
                self.db.execute(
                    "UPDATE comments SET content = :content WHERE id = :id",
                    {"content": SecurityUtils.sanitize_content(update_data.content), "id": comment_id}
                )
            
            if update_data.is_deleted is not None:
                self.db.execute(
                    "UPDATE comments SET is_deleted = :is_deleted WHERE id = :id",
                    {"is_deleted": update_data.is_deleted, "id": comment_id}
                )
            
            self.db.commit()
            self.db.refresh(comment)
            
            # 清除相关缓存
            await self._clear_page_cache(comment.page)
            
            return comment
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, NotFoundError):
                raise
            logger.error(f"Failed to update comment: {e}")
            raise DatabaseException("更新评论失败")

    async def delete_comment(self, comment_id: int) -> bool:
        """软删除评论"""
        try:
            comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
            if not comment:
                raise NotFoundError("评论不存在")
            
            # 使用原生SQL进行软删除
            self.db.execute(
                "UPDATE comments SET is_deleted = true WHERE id = :id",
                {"id": comment_id}
            )
            self.db.commit()
            
            # 清除缓存
            await self._clear_page_cache(comment.page)
            
            logger.info(f"Comment deleted: {comment_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, NotFoundError):
                raise
            logger.error(f"Failed to delete comment: {e}")
            raise DatabaseException("删除评论失败")

    async def get_page_stats(self, page: str) -> Dict[str, int]:
        """获取页面统计信息"""
        try:
            # 尝试从缓存获取
            cache_key = f"page_stats:{page}"
            cached_result = await self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # 统计总评论数
            total_comments = self.db.query(Comment).filter(
                Comment.page == page,
                Comment.is_deleted == False
            ).count()
            
            # 统计顶级评论数
            top_level_comments = self.db.query(Comment).filter(
                Comment.page == page,
                Comment.parent_id.is_(None),
                Comment.is_deleted == False
            ).count()
            
            # 计算回复数
            replies = total_comments - top_level_comments
            
            result = {
                "total_comments": total_comments,
                "top_level_comments": top_level_comments,
                "replies": replies
            }
            
            # 缓存结果
            await self._set_cache(cache_key, result, 600)  # 缓存10分钟
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get page stats: {e}")
            raise DatabaseException("获取统计信息失败")


def get_comment_service(db: Session) -> SimplifiedCommentService:
    """获取评论服务实例"""
    return SimplifiedCommentService(db)