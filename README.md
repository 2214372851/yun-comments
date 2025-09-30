# 静态网站评论系统后端

# 评论系统后端

[![Docker Build](https://github.com/yourusername/yun-comments/actions/workflows/docker-simple.yml/badge.svg)](https://github.com/yourusername/yun-comments/actions/workflows/docker-simple.yml)
[![Docker Pulls](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/yourusername/yun-comments/pkgs/container/yun-comments)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

为静态网站提供评论功能的后端服务，支持嵌套回复、用户身份验证、限流保护等核心功能。

## 技术栈

- **后端框架**: FastAPI
- **数据库**: PostgreSQL
- **ORM**: SQLAlchemy
- **缓存**: Redis
- **限流**: slowapi
- **验证**: Pydantic

## 快速开始

### 环境要求

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Docker & Docker Compose (可选)

### 本地开发

1. 克隆项目
```bash
git clone <repository-url>
cd yun-comments
```

2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库和Redis连接
```

5. 运行数据库迁移
```bash
alembic upgrade head
```

6. 启动服务
```bash
uvicorn app.main:app --reload
```

### Docker 部署

#### 快速启动（开发环境）

```bash
# 使用本地构建
docker-compose up -d
```

#### 生产部署（使用GitHub Packages镜像）

```bash
# 从 GitHub Packages 拉取镜像
docker pull ghcr.io/yourusername/yun-comments:latest

# 使用生产配置启动
cp .env.production.example .env
# 编辑 .env 文件，配置生产环境参数
docker-compose -f docker-compose.prod.yml up -d
```

📝 **详细部署指南**: [docs/DOCKER.md](docs/DOCKER.md)

## API 文档

服务启动后访问：http://localhost:8000/docs

## 项目结构

```
app/
├── api/           # API路由
├── core/          # 核心配置
├── middleware/    # 中间件
├── models/        # 数据库模型
├── schemas/       # Pydantic模型
├── services/      # 业务逻辑
└── utils/         # 工具函数
tests/             # 测试文件
alembic/           # 数据库迁移
```

## 功能特性

- ✅ 嵌套评论回复
- ✅ 多层限流保护
- ✅ 自动获取用户地区信息
- ✅ 系统类型检测
- ✅ 垃圾评论过滤
- ✅ Redis缓存优化
- ✅ 完整的API文档
- ✅ 单元测试覆盖

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License