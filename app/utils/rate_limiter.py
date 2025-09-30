from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.core.database import get_redis
from app.core.config import settings
from app.core.exceptions import RateLimitException
from app.utils.user_info import IPHelper
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 创建限流器实例
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    enabled=settings.RATE_LIMIT_ENABLED
)


def get_client_ip(request: Request) -> str:
    """获取客户端真实IP地址"""
    # 首先尝试从头部获取真实IP
    real_ip = IPHelper.extract_real_ip(dict(request.headers))
    if real_ip:
        return real_ip
    
    # 回退到默认方法
    return get_remote_address(request)


def get_user_identifier(request: Request) -> str:
    """获取用户标识符（用于用户级限流）"""
    # 如果有用户邮箱，使用邮箱作为标识符
    if hasattr(request.state, 'user_email'):
        return f"user:{request.state.user_email}"
    
    # 否则使用IP地址
    return f"ip:{get_client_ip(request)}"


def get_email_identifier(email: str) -> str:
    """获取邮箱标识符（用于邮箱级限流）"""
    return f"email:{email}"


class CustomLimiter:
    """自定义限流器"""
    
    def __init__(self):
        self.redis_client = get_redis()
    
    def _get_rate_limit_key(self, identifier: str, limit_type: str) -> str:
        """生成限流键"""
        return f"rate_limit:{limit_type}:{identifier}"
    
    def _check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, dict]:
        """
        检查限流状态
        
        Args:
            key: 限流键
            limit: 限制次数
            window: 时间窗口（秒）
            
        Returns:
            (是否通过, 限流信息)
        """
        try:
            # 使用滑动窗口算法
            import time
            current_time = int(time.time())
            
            # 使用Redis的有序集合实现滑动窗口
            pipeline = self.redis_client.pipeline()
            
            # 移除过期的请求记录
            pipeline.zremrangebyscore(key, 0, current_time - window)
            
            # 添加当前请求
            pipeline.zadd(key, {str(current_time): current_time})
            
            # 获取当前窗口内的请求数
            pipeline.zcard(key)
            
            # 设置键的过期时间
            pipeline.expire(key, window)
            
            results = pipeline.execute()
            current_count = results[2]  # 当前请求数
            
            # 计算剩余次数和重置时间
            remaining = max(0, limit - current_count)
            reset_time = current_time + window
            
            rate_limit_info = {
                "limit": limit,
                "remaining": remaining,
                "reset_time": reset_time,
                "current_count": current_count
            }
            
            # 检查是否超过限制
            if current_count > limit:
                rate_limit_info["retry_after"] = window
                return False, rate_limit_info
            
            return True, rate_limit_info
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # 如果Redis出错，允许请求通过
            return True, {"limit": limit, "remaining": limit, "reset_time": 0}
    
    def check_ip_rate_limit(self, request: Request) -> tuple[bool, dict]:
        """检查IP限流"""
        ip = get_client_ip(request)
        key = self._get_rate_limit_key(ip, "ip")
        return self._check_rate_limit(key, settings.IP_RATE_LIMIT, 60)
    
    def check_user_rate_limit(self, request: Request) -> tuple[bool, dict]:
        """检查用户限流"""
        user_id = get_user_identifier(request)
        key = self._get_rate_limit_key(user_id, "user")
        return self._check_rate_limit(key, settings.USER_RATE_LIMIT, 60)
    
    def check_email_rate_limit(self, email: str) -> tuple[bool, dict]:
        """检查邮箱限流"""
        email_id = get_email_identifier(email)
        key = self._get_rate_limit_key(email_id, "email")
        return self._check_rate_limit(key, settings.EMAIL_RATE_LIMIT, 300)  # 5分钟
    
    def check_global_rate_limit(self, request: Request) -> tuple[bool, dict]:
        """检查全局限流"""
        key = self._get_rate_limit_key("global", "global")
        return self._check_rate_limit(key, settings.GLOBAL_RATE_LIMIT, 60)


# 全局限流器实例
custom_limiter = CustomLimiter()


def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """自定义限流异常处理器"""
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "请求过于频繁，请稍后再试",
            "code": "RATE_LIMIT_EXCEEDED",
            "retry_after": exc.retry_after
        }
    )
    response.headers["Retry-After"] = str(exc.retry_after)
    return response


def create_rate_limit_middleware():
    """创建限流中间件"""
    
    async def rate_limit_middleware(request: Request, call_next):
        """限流中间件"""
        try:
            # 跳过健康检查等端点
            if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
                response = await call_next(request)
                return response
            
            # 检查全局限流
            passed, global_info = custom_limiter.check_global_rate_limit(request)
            if not passed:
                raise RateLimitException("系统繁忙，请稍后再试")
            
            # 检查IP限流
            passed, ip_info = custom_limiter.check_ip_rate_limit(request)
            if not passed:
                raise RateLimitException("IP访问过于频繁，请稍后再试")
            
            # 检查用户限流
            passed, user_info = custom_limiter.check_user_rate_limit(request)
            if not passed:
                raise RateLimitException("用户访问过于频繁，请稍后再试")
            
            # 将限流信息存储到请求状态中
            request.state.rate_limit_info = {
                "global": global_info,
                "ip": ip_info,
                "user": user_info
            }
            
            # 继续处理请求
            response = await call_next(request)
            
            # 安全地添加限流信息到响应头
            if "content-length" not in response.headers:
                response.headers["X-RateLimit-Limit"] = str(ip_info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(ip_info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(ip_info["reset_time"])
            
            return response
            
        except RateLimitException:
            raise
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            # 如果中间件出错，继续处理请求
            response = await call_next(request)
            return response
    
    return rate_limit_middleware


async def check_email_rate_limit_for_comment(email: str) -> None:
    """检查邮箱评论限流"""
    passed, info = custom_limiter.check_email_rate_limit(email)
    if not passed:
        raise RateLimitException(
            f"该邮箱提交评论过于频繁，请 {info.get('retry_after', 300)} 秒后再试"
        )