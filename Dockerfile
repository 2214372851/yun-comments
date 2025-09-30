# 使用更小的Alpine镜像
FROM python:3.11-alpine AS builder

# 设置构建时环境变量
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# 安装构建依赖
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    postgresql-dev \
    libffi-dev \
    openssl-dev

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制并安装生产依赖
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 生产阶段
FROM python:3.11-alpine AS production

# 添加构建参数
ARG BUILDTIME
ARG VERSION
ARG REVISION

# 设置运行时环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# 添加元数据标签
LABEL org.opencontainers.image.title="评论系统后端" \
      org.opencontainers.image.description="为静态博客提供评论功能的FastAPI后端服务" \
      org.opencontainers.image.vendor="YunHai" \
      org.opencontainers.image.url="https://www.yhnotes.com" \
      org.opencontainers.image.created="${BUILDTIME}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

# 只安装运行时需要的依赖
RUN apk add --no-cache \
    libpq \
    curl \
    && adduser -D -u 1000 app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置工作目录
WORKDIR /app

# 只复制必要的应用文件
COPY --chown=app:app app/ ./app/
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app alembic.ini .

# 创建日志目录
RUN mkdir -p logs && chown app:app logs

# 切换到非root用户
USER app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]