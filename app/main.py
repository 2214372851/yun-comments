from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.exceptions import CommentException
from app.middleware.middlewares import setup_middlewares
from app.utils.rate_limiter import limiter, rate_limit_handler, create_rate_limit_middleware
from app.api.comments import router as comments_router
from slowapi.errors import RateLimitExceeded


# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.LOG_FILE) if settings.LOG_FILE else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Application starting up...")
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # 关闭时执行
    logger.info("Application shutting down...")
    try:
        await close_db()
        logger.info("Database closed successfully")
    except Exception as e:
        logger.error(f"Failed to close database: {e}")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## 静态网站评论系统后端API
    
    为静态网站提供评论功能的后端服务，支持：
    
    * **嵌套回复**: 支持多层级评论回复
    * **用户信息**: 自动检测用户系统类型和地区
    * **限流保护**: 多层限流机制防止滥用
    * **垃圾过滤**: 自动检测和过滤垃圾评论
    * **缓存优化**: Redis缓存提升性能
    
    ### 使用说明
    
    1. 获取评论列表：`GET /api/comments?page={页面标识}`
    2. 提交评论：`POST /api/comments`
    3. 健康检查：`GET /api/health`
    
    ### 限流规则
    
    - IP限流：10次/分钟
    - 用户限流：5次/分钟  
    - 邮箱限流：3次/5分钟
    - 全局限流：1000次/分钟
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# 设置限流处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# 添加限流中间件
app.middleware("http")(create_rate_limit_middleware())

# 设置其他中间件
setup_middlewares(app)

# 注册路由
app.include_router(comments_router)


@app.exception_handler(CommentException)
async def comment_exception_handler(request: Request, exc: CommentException):
    """评论异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": type(exc).__name__,
            "timestamp": str(request.state.start_time) if hasattr(request.state, 'start_time') else None
        },
        headers=getattr(exc, 'headers', None)
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请求参数验证失败",
            "code": "VALIDATION_ERROR",
            "errors": exc.errors()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": "HTTP_ERROR"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.error(f"Unhandled exception - Request ID: {request_id}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误" if not settings.DEBUG else str(exc),
            "code": "INTERNAL_SERVER_ERROR",
            "request_id": request_id
        }
    )


@app.get("/", include_in_schema=False)
async def root():
    """根路径重定向到文档"""
    return {
        "message": "欢迎使用评论系统API",
        "docs": "/docs",
        "health": "/api/health",
        "version": settings.APP_VERSION
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Favicon处理"""
    return JSONResponse(status_code=204, content=None)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )