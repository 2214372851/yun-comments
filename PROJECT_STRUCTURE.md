# 项目结构说明

```
yun-comments/                           # 项目根目录
├── .env.example                       # 环境变量示例文件
├── .gitignore                         # Git忽略文件
├── Dockerfile                         # Docker镜像构建文件
├── README.md                          # 项目说明文档
├── alembic.ini                        # Alembic配置文件
├── docker-compose.yml                 # Docker Compose配置
├── init.sql                           # 数据库初始化脚本
├── nginx.conf                         # Nginx配置文件
├── pytest.ini                        # Pytest配置文件
├── requirements.txt                   # Python依赖包
│
├── alembic/                           # 数据库迁移
│   ├── env.py                         # Alembic环境配置
│   ├── script.py.mako                 # 迁移脚本模板
│   └── versions/                      # 迁移版本文件夹
│
├── app/                               # 应用主目录
│   ├── __init__.py                    # 包初始化文件
│   ├── main.py                        # FastAPI应用入口
│   │
│   ├── api/                           # API路由层
│   │   ├── __init__.py
│   │   └── comments.py                # 评论相关API
│   │
│   ├── core/                          # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py                  # 应用配置
│   │   ├── database.py                # 数据库连接配置
│   │   └── exceptions.py              # 自定义异常
│   │
│   ├── middleware/                    # 中间件
│   │   ├── __init__.py
│   │   └── middlewares.py             # 各种中间件实现
│   │
│   ├── models/                        # 数据模型
│   │   ├── __init__.py
│   │   └── comment.py                 # 评论数据模型
│   │
│   ├── schemas/                       # Pydantic模型
│   │   ├── __init__.py
│   │   └── comment.py                 # 请求响应模型
│   │
│   ├── services/                      # 业务逻辑层
│   │   ├── __init__.py
│   │   └── comment_service.py         # 评论业务逻辑
│   │
│   └── utils/                         # 工具函数
│       ├── __init__.py
│       ├── helpers.py                 # 通用辅助函数
│       ├── rate_limiter.py            # 限流相关工具
│       └── user_info.py               # 用户信息检测
│
├── docs/                              # 文档目录
│   ├── API.md                         # API使用文档
│   └── DEPLOYMENT.md                  # 部署文档
│
├── logs/                              # 日志目录（运行时创建）
│
└── tests/                             # 测试目录
    ├── __init__.py
    ├── conftest.py                    # 测试配置
    ├── integration/                   # 集成测试
    │   ├── test_api.py                # API集成测试
    │   └── test_services.py           # 服务集成测试
    └── unit/                          # 单元测试
        ├── test_models.py             # 模型单元测试
        └── test_utils.py              # 工具函数单元测试
```

## 主要功能模块

### 1. 核心层 (core/)
- **config.py**: 应用配置管理，包括数据库、Redis、限流等配置
- **database.py**: 数据库连接池、会话管理
- **exceptions.py**: 自定义异常类定义

### 2. 数据层 (models/)
- **comment.py**: 评论数据模型，包含完整的字段定义和关系

### 3. API层 (api/)
- **comments.py**: 评论CRUD API端点，包含参数验证和错误处理

### 4. 业务逻辑层 (services/)
- **comment_service.py**: 评论业务逻辑，包含缓存、验证、树结构构建等

### 5. 工具层 (utils/)
- **user_info.py**: 系统检测、地区信息获取
- **rate_limiter.py**: 多层限流机制实现
- **helpers.py**: 通用工具函数

### 6. 中间件层 (middleware/)
- **middlewares.py**: 日志、安全、用户信息检测等中间件

### 7. 数据验证层 (schemas/)
- **comment.py**: 请求响应数据模型，包含验证规则

## 技术特性

✅ **完整的评论系统**: 支持嵌套回复、软删除、分页查询
✅ **多层限流保护**: IP、用户、邮箱、全局四层限流
✅ **用户环境检测**: 自动检测操作系统和地区信息
✅ **缓存优化**: Redis缓存提升查询性能
✅ **安全防护**: XSS防护、SQL注入防护、垃圾内容过滤
✅ **完整测试**: 单元测试、集成测试覆盖主要功能
✅ **Docker部署**: 完整的Docker配置和Nginx反向代理
✅ **数据库迁移**: Alembic支持数据库版本管理
✅ **API文档**: 自动生成的Swagger文档
✅ **生产就绪**: 日志、监控、健康检查等生产环境必需功能

## 部署方式

1. **Docker部署** (推荐)
   ```bash
   docker-compose up -d
   ```

2. **手动部署**
   ```bash
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## 测试运行

```bash
# 安装测试依赖
pip install -r requirements.txt

# 运行所有测试
pytest

# 运行特定测试
pytest tests/unit/
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

这个项目结构遵循了现代Web应用的最佳实践，具有良好的可维护性和可扩展性。