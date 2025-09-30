import hashlib
import hmac
import json
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SecurityUtils:
    """安全工具类"""
    
    @staticmethod
    def generate_hash(content: str, salt: str = "") -> str:
        """生成内容哈希"""
        combined = f"{content}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def verify_hash(content: str, hash_value: str, salt: str = "") -> bool:
        """验证哈希值"""
        return SecurityUtils.generate_hash(content, salt) == hash_value
    
    @staticmethod
    def generate_email_hash(email: str) -> str:
        """生成邮箱MD5哈希（用于Gravatar）"""
        return hashlib.md5(email.lower().strip().encode()).hexdigest()
    
    @staticmethod
    def sanitize_content(content: str) -> str:
        """清理内容，防止XSS攻击"""
        # 简单的HTML标签清理
        import html
        return html.escape(content.strip())
    
    @staticmethod
    def check_spam_content(content: str) -> bool:
        """检查是否为垃圾内容"""
        spam_keywords = [
            '广告', '推广', 'spam', '色情', '赌博', '借贷', '贷款',
            '微信', 'QQ', '加我', '联系我', 'http://', 'https://',
            '点击', '优惠', '打折', '免费', '赚钱'
        ]
        
        content_lower = content.lower()
        spam_count = sum(1 for keyword in spam_keywords if keyword in content_lower)
        
        # 如果包含多个垃圾关键词，认为是垃圾内容
        return spam_count >= 2


class CacheUtils:
    """缓存工具类"""
    
    @staticmethod
    def generate_cache_key(prefix: str, *args) -> str:
        """生成缓存键"""
        key_parts = [prefix] + [str(arg) for arg in args]
        return ":".join(key_parts)
    
    @staticmethod
    def serialize_for_cache(data: Any) -> str:
        """序列化数据用于缓存"""
        try:
            return json.dumps(data, default=str, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to serialize data for cache: {e}")
            return ""
    
    @staticmethod
    def deserialize_from_cache(data: str) -> Any:
        """从缓存反序列化数据"""
        try:
            return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to deserialize data from cache: {e}")
            return None


class ValidationUtils:
    """验证工具类"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def is_valid_username(username: str) -> bool:
        """验证用户名格式"""
        if not username or len(username.strip()) < 2:
            return False
        
        # 不允许的字符
        forbidden_chars = ['<', '>', '"', "'", '/', '\\', '&']
        return not any(char in username for char in forbidden_chars)
    
    @staticmethod
    def is_valid_content_length(content: str, min_length: int = 10, max_length: int = 2000) -> bool:
        """验证内容长度"""
        if not content:
            return False
        
        content_length = len(content.strip())
        return min_length <= content_length <= max_length


class ResponseUtils:
    """响应工具类"""
    
    @staticmethod
    def success_response(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
        """成功响应格式"""
        response = {
            "success": True,
            "message": message,
            "timestamp": SecurityUtils.generate_hash(str(hash(str(data))))[:8]
        }
        if data is not None:
            response["data"] = data
        return response
    
    @staticmethod
    def error_response(message: str, code: Optional[str] = None, details: Any = None) -> Dict[str, Any]:
        """错误响应格式"""
        response = {
            "success": False,
            "message": message,
            "timestamp": SecurityUtils.generate_hash(message)[:8]
        }
        if code:
            response["code"] = code
        if details:
            response["details"] = details
        return response


class PaginationUtils:
    """分页工具类"""
    
    @staticmethod
    def calculate_pagination(total: int, page: int, page_size: int) -> Dict[str, int]:
        """计算分页信息"""
        total_pages = (total + page_size - 1) // page_size
        has_prev = page > 1
        has_next = page < total_pages
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_prev": has_prev,
            "has_next": has_next
        }
    
    @staticmethod
    def get_offset_limit(page: int, page_size: int) -> tuple[int, int]:
        """获取数据库查询的offset和limit"""
        offset = (page - 1) * page_size
        return offset, page_size