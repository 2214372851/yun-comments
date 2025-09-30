# 博客评论系统

一个基于FastAPI的高性能评论系统，专为静态博客设计。

## 🚀 核心特性

- **高性能**: 使用FastAPI + PostgreSQL + Redis
- **游标分页**: 支持大数据量评论加载
- **分层设计**: 顶级评论与回复分离，按需加载
- **IP限流**: 智能防刷机制
- **容器化**: 支持Docker一键部署

## 📋 系统要求

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (可选)

## 🛠️ 快速开始

### 方式一：Docker 部署 (推荐)

```bash
# 克隆项目
git clone <repository-url>
cd yun-comments

# 配置环境变量
cp .env.example .env
vim .env  # 修改数据库配置

# 启动服务
docker-compose up -d
```

### 方式二：本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
vim .env

# 数据库迁移
alembic upgrade head

# 启动服务
python -m uvicorn app.main:app --reload
```

## 🔧 环境配置

复制 `.env.example` 为 `.env` 并配置：

```env
# 数据库配置
DATABASE_URL=postgresql://username:password@localhost:5432/dbname

# Redis配置
REDIS_URL=redis://localhost:6379/0

# 应用配置
SECRET_KEY=your-secret-key
ENVIRONMENT=production
```

## 📡 API 接口

### 获取评论列表
```http
GET /api/comments?page=blog-post-1&limit=20
```

### 获取评论回复
```http
GET /api/comments/{id}/replies?limit=10
```

### 创建评论
```http
POST /api/comments
Content-Type: application/json

{
  "page": "blog-post-1",
  "username": "张三",
  "email": "zhangsan@example.com",
  "content": "这是一条评论",
  "parent_id": null
}
```

### 健康检查
```http
GET /api/health
```

## 🗂️ 项目结构

```
yun-comments/
├── app/                    # 应用代码
│   ├── api/               # API路由
│   ├── core/              # 核心配置
│   ├── models/            # 数据模型
│   ├── schemas/           # 数据验证
│   ├── services/          # 业务逻辑
│   ├── middleware/        # 中间件
│   ├── utils/             # 工具函数
│   └── main.py            # 应用入口
├── alembic/               # 数据库迁移
├── docker-compose.yml     # Docker编排
├── Dockerfile             # Docker镜像
├── nginx.conf             # Nginx配置
├── requirements.txt       # Python依赖
└── README.md              # 项目文档
```

## 🔐 安全特性

- IP限流：5分钟内最多3次评论
- 内容过滤：防止XSS和垃圾评论
- 输入验证：严格的数据验证
- 环境隔离：生产环境安全配置

## 📊 性能优化

- **游标分页**: 替代传统OFFSET分页，性能更优
- **Redis缓存**: 热点数据缓存，减少数据库压力
- **分层加载**: 顶级评论优先，回复按需加载
- **数据库索引**: 优化查询性能

## 🐛 故障排除

### 数据库连接失败
```bash
# 检查PostgreSQL服务
sudo systemctl status postgresql

# 检查连接配置
psql -h localhost -U username -d dbname
```

### Redis连接失败
```bash
# 检查Redis服务
sudo systemctl status redis

# 测试连接
redis-cli ping
```

### 容器启动失败
```bash
# 查看日志
docker-compose logs -f

# 重建容器
docker-compose down
docker-compose up --build
```

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！