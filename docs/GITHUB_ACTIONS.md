# GitHub Actions 设置指南

## 🚀 自动化Docker镜像构建和发布

本项目包含了两个GitHub Actions工作流，用于自动构建和发布Docker镜像到GitHub Container Registry。

## 📁 工作流文件

### 1. 简化版本 (.github/workflows/docker-simple.yml)
- **触发条件**: 推送版本标签、手动触发
- **功能**: 构建多架构镜像(amd64/arm64)并推送到ghcr.io
- **特点**: 支持自定义标签和构建平台选择
- **推荐**: 生产环境使用

### 2. 完整版本 (.github/workflows/docker-publish.yml)  
- **触发条件**: 推送版本标签、手动触发
- **功能**: 包含安全扫描、镜像签名等高级功能
- **特点**: 可选择性启用安全扫描和签名功能
- **推荐**: 企业级项目使用

## ⚙️ 设置步骤

### 1. 启用GitHub Packages

1. 进入你的GitHub仓库
2. 点击 `Settings` → `Actions` → `General`
3. 确保 `Actions permissions` 设置为允许所有操作
4. 在 `Workflow permissions` 中，选择 `Read and write permissions`

### 2. 更新配置文件

在以下文件中将 `yourusername` 替换为你的GitHub用户名：

#### 📝 需要更新的文件：
- `.github/workflows/docker-simple.yml`
- `.github/workflows/docker-publish.yml` 
- `docker-compose.prod.yml`
- `docs/DOCKER.md`
- `README.md`

```bash
# 使用sed命令批量替换 (Linux/Mac)
find . -type f \( -name "*.yml" -o -name "*.md" \) -exec sed -i 's/yourusername/your-actual-username/g' {} +

# Windows PowerShell
Get-ChildItem -Recurse -Include *.yml,*.md | ForEach-Object { (Get-Content $_) -replace 'yourusername', 'your-actual-username' | Set-Content $_ }
```

### 3. 推送代码触发构建

#### 方式一：创建版本标签
```bash
# 创建版本标签触发构建
git tag v1.0.0
git push origin v1.0.0

# 支持的标签格式
git tag v1.0.0        # 正式版本
git tag v1.0.0-beta   # 预发布版本
git tag v1.0.0-rc.1   # 发布候选
```

#### 方式二：手动触发
1. 进入GitHub仓库
2. 点击 `Actions` 标签
3. 选择 `发布Docker镜像` 工作流
4. 点击 `Run workflow`
5. 填写参数：
   - **自定义标签**: 默认为 `manual`，可自定义
   - **构建平台**: 选择要构建的架构

## 📦 镜像访问

构建完成后，你的Docker镜像将可以通过以下方式访问：

```bash
# 拉取最新版本
docker pull ghcr.io/your-username/yun-comments:latest

# 拉取特定版本
docker pull ghcr.io/your-username/yun-comments:v1.0.0
```

## 🔍 查看构建状态

1. 进入你的GitHub仓库
2. 点击 `Actions` 标签
3. 查看工作流运行状态
4. 点击 `Packages` 查看发布的镜像

## 🛠️ 自定义配置

### 修改触发条件

编辑 `.github/workflows/docker-simple.yml` 文件的 `on` 部分：

```yaml
on:
  push:
    tags: 
      - 'v*.*.*'        # 版本标签
      - 'release-*'     # 发布标签
  
  # 手动触发设置
  workflow_dispatch:
    inputs:
      tag:
        description: '自定义镜像标签'
        required: false
        default: 'manual'
        type: string
      platforms:
        description: '构建平台'
        required: false
        default: 'linux/amd64,linux/arm64'
        type: choice
        options:
        - 'linux/amd64,linux/arm64'
        - 'linux/amd64'
        - 'linux/arm64'
  
  # 定时构建 (每天凌晨2点)
  schedule:
    - cron: '0 2 * * *'
```

### 添加自定义构建参数

在 `docker-simple.yml` 的构建步骤中添加：

```yaml
- name: 构建并推送Docker镜像
  uses: docker/build-push-action@v5
  with:
    # ... 其他配置
    build-args: |
      VERSION=${{ github.ref_name }}
      BUILD_DATE=${{ fromJSON(steps.meta.outputs.json).labels['org.opencontainers.image.created'] }}
      CUSTOM_ARG=value
```

## 🔒 安全建议

1. **私有仓库**: 如果项目包含敏感信息，考虑使用私有镜像仓库
2. **密钥管理**: 敏感信息使用GitHub Secrets存储
3. **权限控制**: 定期检查Actions权限设置
4. **镜像扫描**: 启用Trivy安全扫描（完整版工作流已包含）

## 🆘 故障排除

### 常见问题：

**1. 权限错误**
```
Error: denied: permission_denied
```
解决：检查仓库的Actions权限设置

**2. 镜像推送失败**
```
Error: failed to push to registry
```
解决：确保GitHub Token有packages:write权限

**3. 多架构构建失败**
```
Error: failed to build for platform linux/arm64
```
解决：移除arm64架构或使用emulation

## 📚 相关文档

- [GitHub Packages 文档](https://docs.github.com/en/packages)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker构建文档](https://docs.docker.com/build/)

## 🎯 下一步

1. 设置自动化测试
2. 配置安全扫描
3. 添加多环境部署
4. 设置监控和告警