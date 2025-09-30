from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc, func
from app.models.comment import Comment
from app.schemas.comment import CommentCreate, CommentUpdate, CommentQuery
from app.core.exceptions import NotFoundError, ValidationException, DatabaseException
from app.utils.helpers import SecurityUtils, CacheUtils, PaginationUtils
from app.utils.user_info import system_detector, location_service
from app.utils.rate_limiter import check_email_rate_limit_for_comment
from app.core.database import get_redis
from app.core.config import settings
from typing import List, Optional, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


class CommentService:
    """评论服务类"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = get_redis()
    
    async def create_comment(
        self, 
        comment_data: CommentCreate, 
        ip_address: str, 
        user_agent: str
    ) -> Comment:
        """
        创建评论
        
        Args:
            comment_data: 评论数据
            ip_address: 用户IP地址
            user_agent: 用户代理
            
        Returns:
            创建的评论对象
        """
        try:
            # 检查邮箱限流
            await check_email_rate_limit_for_comment(comment_data.email)
            
            # 验证父评论是否存在
            if comment_data.parent_id:
                parent_comment = self.db.query(Comment).filter(
                    and_(
                        Comment.id == comment_data.parent_id,
                        Comment.is_deleted == False
                    )
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
        获取评论列表
        
        Args:
            query: 查询参数
            
        Returns:
            评论列表和分页信息
        """
        try:
            # 尝试从缓存获取
            cache_key = CacheUtils.generate_cache_key(
                "comments", query.page, query.page_num, query.page_size, query.sort, query.order
            )
            
            cached_result = await self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # 构建查询
            base_query = self.db.query(Comment).filter(
                and_(
                    Comment.page == query.page,
                    Comment.is_deleted == False
                )
            )
            
            # 获取总数
            total = base_query.count()
            
            # 排序
            order_column = getattr(Comment, query.sort, Comment.created_at)
            if query.order == "asc":
                base_query = base_query.order_by(asc(order_column))
            else:
                base_query = base_query.order_by(desc(order_column))
            
            # 分页
            offset, limit = PaginationUtils.get_offset_limit(query.page_num, query.page_size)
            comments = base_query.offset(offset).limit(limit).all()
            
            # 构建评论树
            comment_tree = self._build_comment_tree(comments)
            
            # 分页信息
            pagination = PaginationUtils.calculate_pagination(total, query.page_num, query.page_size)
            
            result = {
                "comments": comment_tree,
                **pagination
            }
            
            # 缓存结果
            await self._set_cache(cache_key, result, settings.CACHE_TTL)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get comments: {e}")
            raise DatabaseException("获取评论失败")
    
    async def delete_comment(self, comment_id: int) -> bool:
        """
        软删除评论
        
        Args:
            comment_id: 评论ID
            
        Returns:
            是否删除成功
        """
        try:
            comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
            if not comment:
                raise NotFoundError("评论不存在")
            
            # 软删除
            comment.is_deleted = True
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
    
    async def update_comment(self, comment_id: int, update_data: CommentUpdate) -> Comment:
        """
        更新评论
        
        Args:
            comment_id: 评论ID
            update_data: 更新数据
            
        Returns:
            更新后的评论对象
        """
        try:
            comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
            if not comment:
                raise NotFoundError("评论不存在")
            
            # 更新字段
            if update_data.content is not None:
                comment.content = SecurityUtils.sanitize_content(update_data.content)
            
            if update_data.is_deleted is not None:
                comment.is_deleted = update_data.is_deleted
            
            self.db.commit()
            self.db.refresh(comment)
            
            # 清除缓存
            await self._clear_page_cache(comment.page)
            
            logger.info(f"Comment updated: {comment_id}")
            return comment
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, NotFoundError):
                raise
            logger.error(f"Failed to update comment: {e}")
            raise DatabaseException("更新评论失败")
    
    async def get_comment_by_id(self, comment_id: int) -> Optional[Comment]:
        """
        根据ID获取评论
        
        Args:
            comment_id: 评论ID
            
        Returns:
            评论对象或None
        """
        try:
            return self.db.query(Comment).filter(
                and_(
                    Comment.id == comment_id,
                    Comment.is_deleted == False
                )
            ).first()
        except Exception as e:
            logger.error(f"Failed to get comment by id: {e}")
            return None
    
    async def get_page_stats(self, page: str) -> Dict[str, int]:
        """
        获取页面评论统计
        
        Args:
            page: 页面标识
            
        Returns:
            统计信息
        """
        try:
            cache_key = CacheUtils.generate_cache_key("page_stats", page)
            cached_stats = await self._get_from_cache(cache_key)
            if cached_stats:
                return cached_stats
            
            total_comments = self.db.query(Comment).filter(
                and_(
                    Comment.page == page,
                    Comment.is_deleted == False
                )
            ).count()
            
            top_level_comments = self.db.query(Comment).filter(
                and_(
                    Comment.page == page,
                    Comment.parent_id == None,
                    Comment.is_deleted == False
                )
            ).count()
            
            stats = {
                "total_comments": total_comments,
                "top_level_comments": top_level_comments,
                "replies": total_comments - top_level_comments
            }
            
            # 缓存统计信息
            await self._set_cache(cache_key, stats, settings.CACHE_TTL)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get page stats: {e}")
            return {"total_comments": 0, "top_level_comments": 0, "replies": 0}
    
    def _build_comment_tree(self, comments: List[Comment]) -> List[Dict]:
        """
        构建评论树结构
        
        Args:
            comments: 评论列表
            
        Returns:
            评论树结构
        """
        # 将评论按ID索引
        comment_map = {comment.id: comment.to_dict() for comment in comments}
        
        # 构建树结构
        tree = []
        for comment in comments:
            comment_dict = comment_map[comment.id]
            
            if comment.parent_id and comment.parent_id in comment_map:
                # 添加到父评论的children中
                parent = comment_map[comment.parent_id]
                if "children" not in parent:
                    parent["children"] = []
                parent["children"].append(comment_dict)
            else:
                # 顶级评论
                tree.append(comment_dict)
        
        return tree
    
    async def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        try:
            cached_data = self.redis_client.get(key)
            if cached_data:
                return CacheUtils.deserialize_from_cache(cached_data)
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
        return None
    
    async def _set_cache(self, key: str, data: Any, ttl: int) -> None:
        """设置缓存数据"""
        try:
            serialized_data = CacheUtils.serialize_for_cache(data)
            if serialized_data:
                self.redis_client.setex(key, ttl, serialized_data)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
    
    async def _clear_page_cache(self, page: str) -> None:
        """清除页面相关缓存"""
        try:
            # 清除评论列表缓存
            pattern = f"comments:{page}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            # 清除页面统计缓存
            stats_key = CacheUtils.generate_cache_key("page_stats", page)
            self.redis_client.delete(stats_key)
            
        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")


def get_comment_service(db: Session) -> CommentService:
    """获取评论服务实例"""
    return CommentService(db)