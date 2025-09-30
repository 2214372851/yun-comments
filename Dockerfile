# 多阶段构建 - 生产环境优化
FROM python:3.11-alpine AS builder

# 安装构建依赖
RUN apk add --no-cache gcc musl-dev libffi-dev postgresql-dev

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖到临时目录
RUN pip install --no-cache-dir --user -r requirements.txt

# 生产阶段
FROM python:3.11-alpine

# 安装运行时依赖
RUN apk add --no-cache libpq curl && \
    rm -rf /var/cache/apk/*

# 创建非root用户
RUN addgroup -g 1001 -S appuser && \
    adduser -S -D -H -u 1001 -s /sbin/nologin -G appuser appuser

# 设置工作目录
WORKDIR /app

# 从构建阶段复制Python包
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY init.sql .

# 设置Python路径
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 设置文件权限
RUN chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
