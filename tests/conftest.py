import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
import os

# 测试数据库URL
TEST_DATABASE_URL = "sqlite:///./test.db"

# 创建测试数据库引擎
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """覆盖数据库依赖"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# 覆盖数据库依赖
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def setup_database():
    """设置测试数据库"""
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    yield
    # 清理数据库
    Base.metadata.drop_all(bind=engine)
    # 删除测试数据库文件
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture
def client(setup_database):
    """创建测试客户端"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    """获取数据库会话"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_comment_data():
    """示例评论数据"""
    return {
        "page": "test-page",
        "email": "test@example.com",
        "username": "测试用户",
        "content": "这是一条测试评论内容，长度超过10个字符。"
    }


@pytest.fixture
def sample_reply_data():
    """示例回复数据"""
    return {
        "page": "test-page",
        "email": "reply@example.com",
        "username": "回复用户",
        "content": "这是一条测试回复内容，长度超过10个字符。",
        "parent_id": 1
    }