# 部署文档

## 部署方式

本项目支持多种部署方式，推荐使用Docker进行部署。

## 1. Docker部署（推荐）

### 1.1 环境要求

- Docker 20.0+
- Docker Compose 2.0+
- 可用的域名（生产环境）

### 1.2 快速部署

1. **克隆项目**
```bash
git clone <repository-url>
cd yun-comments
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑.env文件，修改以下配置：
# - 数据库密码
# - Redis配置  
# - JWT密钥
# - CORS域名
```

3. **启动服务**
```bash
docker-compose up -d
```

4. **检查状态**
```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f comment_api

# 健康检查
curl http://localhost:8000/api/health
```

### 1.3 生产环境配置

#### 修改docker-compose.yml

```yaml
# 生产环境配置示例
services:
  comment_api:
    build: .
    environment:
      - DATABASE_URL=postgresql://comment_user:your_strong_password@postgres:5432/comment_db
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-production-secret-key-at-least-32-characters
      - CORS_ORIGINS=["https://your-domain.com"]
      - DEBUG=false
      - LOG_LEVEL=WARNING
    restart: always
    
  postgres:
    environment:
      - POSTGRES_PASSWORD=your_strong_password
    volumes:
      - /opt/comment-system/postgres:/var/lib/postgresql/data
    restart: always
    
  redis:
    volumes:
      - /opt/comment-system/redis:/data
    restart: always
```

#### SSL证书配置

1. **获取SSL证书**
```bash
# 使用Let's Encrypt
certbot certonly --standalone -d your-domain.com
```

2. **配置Nginx**
```bash
# 将证书复制到ssl目录
mkdir -p ssl
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
```

3. **更新nginx.conf**
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # 其他配置...
}
```

## 2. 手动部署

### 2.1 环境要求

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Nginx（可选）

### 2.2 部署步骤

1. **安装系统依赖**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv postgresql redis-server nginx

# CentOS/RHEL
sudo yum install python3 python3-pip postgresql-server redis nginx
```

2. **创建数据库**
```bash
sudo -u postgres psql
CREATE DATABASE comment_db;
CREATE USER comment_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE comment_db TO comment_user;
\q
```

3. **配置Redis**
```bash
# 编辑配置文件
sudo nano /etc/redis/redis.conf
# 设置：
# maxmemory 512mb
# maxmemory-policy allkeys-lru

# 启动Redis
sudo systemctl start redis
sudo systemctl enable redis
```

4. **部署应用**
```bash
# 创建应用目录
sudo mkdir -p /opt/comment-system
cd /opt/comment-system

# 克隆代码
git clone <repository-url> .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env
```

5. **运行数据库迁移**
```bash
# 如果使用Alembic
alembic upgrade head

# 或者让应用自动创建表（开发模式）
python -c "from app.main import app; from app.core.database import init_db; import asyncio; asyncio.run(init_db())"
```

6. **配置系统服务**
```bash
# 创建systemd服务文件
sudo nano /etc/systemd/system/comment-api.service
```

```ini
[Unit]
Description=Comment System API
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/opt/comment-system
Environment=PATH=/opt/comment-system/venv/bin
ExecStart=/opt/comment-system/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

7. **启动服务**
```bash
sudo systemctl daemon-reload
sudo systemctl start comment-api
sudo systemctl enable comment-api

# 检查状态
sudo systemctl status comment-api
```

## 3. Nginx反向代理配置

### 3.1 基本配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:8000/api/health;
        access_log off;
    }
}
```

### 3.2 SSL配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # SSL优化配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    
    # 其他配置...
}
```

## 4. 监控和日志

### 4.1 日志配置

应用日志默认输出到`logs/app.log`，可通过环境变量配置：

```bash
# .env文件
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### 4.2 健康检查

设置定期健康检查：

```bash
# 添加到crontab
*/5 * * * * curl -f http://localhost:8000/api/health > /dev/null 2>&1 || echo "API health check failed" | mail -s "Alert" admin@example.com
```

### 4.3 日志轮转

配置logrotate：

```bash
sudo nano /etc/logrotate.d/comment-system
```

```
/opt/comment-system/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload comment-api
    endscript
}
```

## 5. 性能优化

### 5.1 数据库优化

```sql
-- 创建额外索引
CREATE INDEX CONCURRENTLY idx_comments_page_created ON comments(page, created_at DESC);
CREATE INDEX CONCURRENTLY idx_comments_active ON comments(page, is_deleted, created_at DESC) WHERE is_deleted = false;

-- 配置PostgreSQL
-- 编辑postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

### 5.2 Redis优化

```bash
# redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
tcp-keepalive 300
timeout 0
```

### 5.3 应用优化

```bash
# 使用Gunicorn (生产环境推荐)
pip install gunicorn

# 启动命令
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 6. 备份策略

### 6.1 数据库备份

```bash
# 创建备份脚本
#!/bin/bash
BACKUP_DIR="/backup/postgres"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
pg_dump -h localhost -U comment_user comment_db > $BACKUP_DIR/comment_db_$DATE.sql
gzip $BACKUP_DIR/comment_db_$DATE.sql

# 保留30天备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### 6.2 Redis备份

```bash
# Redis自动备份
echo "save 900 1" >> /etc/redis/redis.conf
echo "save 300 10" >> /etc/redis/redis.conf
echo "save 60 10000" >> /etc/redis/redis.conf
```

## 7. 安全配置

### 7.1 防火墙设置

```bash
# UFW (Ubuntu)
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw deny 5432  # 禁止外部访问数据库
sudo ufw deny 6379  # 禁止外部访问Redis
sudo ufw enable
```

### 7.2 SSL/TLS配置

```nginx
# 强化SSL配置
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-CHACHA20-POLY1305;
ssl_prefer_server_ciphers off;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:50m;
ssl_stapling on;
ssl_stapling_verify on;

# HSTS
add_header Strict-Transport-Security "max-age=63072000" always;
```

## 8. 故障排除

### 8.1 常见问题

**问题：API返回500错误**
```bash
# 检查应用日志
docker-compose logs comment_api
# 或
sudo journalctl -u comment-api -f
```

**问题：数据库连接失败**
```bash
# 检查数据库状态
docker-compose exec postgres psql -U comment_user -d comment_db -c "SELECT 1;"

# 检查连接字符串
echo $DATABASE_URL
```

**问题：Redis连接失败**
```bash
# 检查Redis状态
docker-compose exec redis redis-cli ping

# 检查连接配置
echo $REDIS_URL
```

### 8.2 性能问题诊断

```bash
# 监控资源使用
docker stats

# 查看慢查询
docker-compose exec postgres psql -U comment_user -d comment_db -c "SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# 监控Redis
docker-compose exec redis redis-cli info stats
```

## 9. 更新和维护

### 9.1 应用更新

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker-compose build comment_api

# 滚动更新
docker-compose up -d comment_api
```

### 9.2 数据库迁移

```bash
# 使用Alembic进行迁移
docker-compose exec comment_api alembic upgrade head
```

### 9.3 定期维护

```bash
# 清理Docker
docker system prune -f

# 优化数据库
docker-compose exec postgres psql -U comment_user -d comment_db -c "VACUUM ANALYZE;"

# 检查磁盘空间
df -h
```

这个部署文档涵盖了从开发到生产环境的完整部署流程，包括性能优化、安全配置和故障排除等重要内容。