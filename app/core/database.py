from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.core.config import settings
import redis
from typing import Generator

# SQLAlchemy 配置
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Redis 连接
redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_redis() -> redis.Redis:
    """获取Redis客户端"""
    return redis_client


async def init_db():
    """初始化数据库"""
    # 导入所有模型以确保它们被注册到Base.metadata
    from app.models import comment  # noqa
    
    # 在生产环境中，应该使用Alembic进行数据库迁移
    # 这里只是为了开发方便
    if settings.DEBUG:
        Base.metadata.create_all(bind=engine)


async def close_db():
    """关闭数据库连接"""
    engine.dispose()


async def check_db_connection() -> bool:
    """检查数据库连接状态"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception:
        return False


async def check_redis_connection() -> bool:
    """检查Redis连接状态"""
    try:
        redis_client.ping()
        return True
    except Exception:
        return False