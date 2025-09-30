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


class SimpleLimiter:
    """简化的IP限流器"""
    
    def __init__(self):
        self.redis_client = get_redis()
    
    def _get_rate_limit_key(self, ip: str, limit_type: str = "ip") -> str:
        """生成限流键"""
        return f"rate_limit:{limit_type}:{ip}"
    
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
    
    def check_ip_rate_limit(self, request: Request, limit: Optional[int] = None, window: int = 60) -> tuple[bool, dict]:
        """检查IP限流"""
        if not settings.RATE_LIMIT_ENABLED:
            return True, {"limit": limit or settings.IP_RATE_LIMIT, "remaining": limit or settings.IP_RATE_LIMIT, "reset_time": 0}
        ip = get_client_ip(request)
        key = self._get_rate_limit_key(ip, "ip")
        actual_limit = limit or settings.IP_RATE_LIMIT
        return self._check_rate_limit(key, actual_limit, window)


# 全局限流器实例
simple_limiter = SimpleLimiter()


def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """自定义限流异常处理器"""
    retry_after = getattr(exc, 'retry_after', 60)  # 默认60秒
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "请求过于频繁，请稍后再试",
            "code": "RATE_LIMIT_EXCEEDED",
            "retry_after": retry_after
        }
    )
    response.headers["Retry-After"] = str(retry_after)
    return response


def create_rate_limit_middleware():
    """创建简化的IP限流中间件"""
    
    async def rate_limit_middleware(request: Request, call_next):
        """IP限流中间件"""
        try:
            # 跳过健康检查等端点
            if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc", "/api/health"]:
                response = await call_next(request)
                return response
            
            # 只检查IP限流
            passed, ip_info = simple_limiter.check_ip_rate_limit(request)
            if not passed:
                raise RateLimitException("IP访问过于频繁，请稍后再试")
            
            # 将限流信息存储到请求状态中
            request.state.rate_limit_info = ip_info
            
            # 继续处理请求
            response = await call_next(request)
            
            # 添加限流信息到响应头
            try:
                response.headers["X-RateLimit-Limit"] = str(ip_info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(ip_info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(ip_info["reset_time"])
            except Exception:
                # 如果无法添加响应头，忽略错误
                pass
            
            return response
            
        except RateLimitException:
            raise
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            # 如果中间件出错，继续处理请求
            response = await call_next(request)
            return response
    
    return rate_limit_middleware


async def check_comment_rate_limit(request: Request) -> None:
    """检查评论提交的IP限流（5分钟内最多3次）"""
    passed, info = simple_limiter.check_ip_rate_limit(request, limit=3, window=300)  # 5分钟
    if not passed:
        raise RateLimitException(
            f"该IP提交评论过于频繁，请 {info.get('retry_after', 300)} 秒后再试"
        )