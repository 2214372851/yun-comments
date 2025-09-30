from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """应用配置类"""
    
    # 基础配置
    APP_NAME: str = "评论系统后端"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 数据库配置
    DATABASE_URL: str = "postgresql://comment_user:comment_pass@localhost:5432/comment_db"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://www.yhnotes.com"]
    
    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    
    # IP限流配置
    IP_RATE_LIMIT: int = 10  # 每分钟请求数
    
    # 地区API配置
    VORE_API_URL: str = "https://api.vore.top/api/IP"
    VORE_API_TIMEOUT: int = 3
    VORE_API_CACHE_TTL: int = 86400  # 24小时
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # 内容验证配置
    MIN_CONTENT_LENGTH: int = 10
    MAX_CONTENT_LENGTH: int = 2000
    MIN_USERNAME_LENGTH: int = 2
    MAX_USERNAME_LENGTH: int = 100
    MAX_EMAIL_LENGTH: int = 255
    MAX_PAGE_LENGTH: int = 200
    
    # 缓存配置
    CACHE_TTL: int = 300  # 5分钟
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略未知的环境变量


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings