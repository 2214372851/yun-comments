from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from app.core.config import settings
from app.core.exceptions import CommentException
from app.utils.user_info import IPHelper, system_detector
import logging
import time
import uuid
from typing import Callable

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 生成请求ID
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 获取客户端信息
        client_ip = IPHelper.extract_real_ip(dict(request.headers)) or request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        # 记录请求开始
        logger.info(
            f"Request started - ID: {request_id} | "
            f"Method: {request.method} | "
            f"URL: {request.url} | "
            f"IP: {client_ip} | "
            f"User-Agent: {user_agent}"
        )
        
        # 将请求信息添加到状态中
        request.state.request_id = request_id
        request.state.client_ip = client_ip
        request.state.user_agent = user_agent
        request.state.start_time = start_time
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录请求完成
            logger.info(
                f"Request completed - ID: {request_id} | "
                f"Status: {response.status_code} | "
                f"Time: {process_time:.3f}s"
            )
            
            # 安全地添加响应头，避免 Content-Length 问题
            if "content-length" not in response.headers:
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录错误
            logger.error(
                f"Request failed - ID: {request_id} | "
                f"Error: {str(e)} | "
                f"Time: {process_time:.3f}s"
            )
            raise


class UserInfoMiddleware(BaseHTTPMiddleware):
    """用户信息检测中间件"""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 获取用户环境信息
        client_ip = getattr(request.state, 'client_ip', request.client.host)
        user_agent = getattr(request.state, 'user_agent', request.headers.get("user-agent", ""))
        
        # 检测系统类型
        system_type = system_detector.detect_system(user_agent)
        
        # 将信息添加到请求状态
        request.state.system_type = system_type
        
        # 继续处理请求
        response = await call_next(request)
        
        # 安全地添加系统信息到响应头（可选）
        if settings.DEBUG and "content-length" not in response.headers:
            response.headers["X-Client-System"] = system_type
        
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 处理请求
        response = await call_next(request)
        
        # 安全地添加安全响应头
        if "content-length" not in response.headers:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            # 在生产环境中添加HSTS
            if not settings.DEBUG:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件"""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except CommentException:
            # CommentException已经被全局异常处理器处理
            raise
        except Exception as e:
            # 记录未处理的异常
            request_id = getattr(request.state, 'request_id', 'unknown')
            logger.error(
                f"Unhandled exception - Request ID: {request_id} | "
                f"Error: {str(e)} | "
                f"Path: {request.url.path}",
                exc_info=True
            )
            
            # 重新抛出异常，让FastAPI的异常处理器处理
            raise


def setup_cors_middleware(app):
    """设置CORS中间件"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-Process-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ]
    )


def setup_middlewares(app):
    """设置所有中间件"""
    # 按照执行顺序添加中间件（后添加的先执行）
    
    # 异常处理中间件（最后执行，最先处理异常）
    app.add_middleware(ExceptionHandlingMiddleware)
    
    # 安全中间件
    app.add_middleware(SecurityMiddleware)
    
    # 用户信息检测中间件
    app.add_middleware(UserInfoMiddleware)
    
    # 日志中间件（最先执行，最后记录）
    app.add_middleware(LoggingMiddleware)
    
    # CORS中间件
    setup_cors_middleware(app)