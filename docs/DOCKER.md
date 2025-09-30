# Docker镜像使用指南

## 🐳 从GitHub Packages拉取镜像

本项目的Docker镜像自动构建并发布到GitHub Container Registry (ghcr.io)。

### 拉取最新镜像

```bash
# 拉取最新镜像
docker pull ghcr.io/yourusername/yun-comments:latest

# 或者拉取特定版本
docker pull ghcr.io/yourusername/yun-comments:v1.0.0
```

### 使用Docker Compose运行

```bash
# 克隆仓库
git clone https://github.com/yourusername/yun-comments.git
cd yun-comments

# 使用已发布的镜像运行
docker-compose -f docker-compose.prod.yml up -d
```

### 单独运行评论系统容器

```bash
# 运行评论系统API
docker run -d \
  --name comment-api \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@your-db:5432/comment_db" \
  -e REDIS_URL="redis://your-redis:6379/0" \
  -e SECRET_KEY="your-secret-key" \
  -e CORS_ORIGINS='["https://www.yhnotes.com"]' \
  ghcr.io/yourusername/yun-comments:latest
```

## 🏗️ 本地构建

如果你想本地构建镜像：

```bash
# 构建镜像
docker build -t yun-comments .

# 运行本地镜像
docker run -p 8000:8000 yun-comments
```

## 📋 环境变量配置

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| DATABASE_URL | 是 | - | PostgreSQL数据库连接URL |
| REDIS_URL | 是 | - | Redis缓存连接URL |
| SECRET_KEY | 是 | - | JWT密钥 |
| CORS_ORIGINS | 否 | [] | 允许的跨域源 |
| DEBUG | 否 | false | 调试模式 |
| LOG_LEVEL | 否 | INFO | 日志级别 |

## 🔧 生产部署建议

1. **使用反向代理**: 建议在评论系统前使用Nginx作为反向代理
2. **SSL证书**: 生产环境中配置HTTPS
3. **数据持久化**: 确保数据库和Redis数据持久化
4. **监控**: 配置日志和监控

## 📦 镜像标签说明

- `latest`: 最新的main分支构建
- `v*.*.*`: 版本标签发布
- `main-<sha>`: main分支的特定commit

## 🚀 自动化部署

GitHub Actions会在以下情况自动构建并推送镜像：

1. 推送到main分支
2. 创建新的版本标签 (v*.*.*)
3. 手动触发工作流

## 📝 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本更新信息。

## 🤝 贡献

欢迎提交Issues和Pull Requests！