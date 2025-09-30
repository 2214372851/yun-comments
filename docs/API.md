# API 使用文档

## 概述

评论系统API提供了完整的评论管理功能，专为静态博客网站（如 https://www.yhnotes.com/ ）设计。系统支持创建、查询、更新和删除评论，具备智能用户信息检测、地理位置识别、多维度限流保护等高级功能。所有API端点都支持CORS跨域访问。

## 基础信息

- **Base URL**: `http://your-domain.com/api` 或 `https://your-domain.com/api`
- **协议**: HTTP/HTTPS
- **数据格式**: JSON
- **字符编码**: UTF-8

## 认证

大部分API端点无需认证，但删除和更新评论需要管理员权限（此功能在当前版本中暂未实现完整的认证机制）。

## 限流规则

本系统采用多层次限流策略，确保服务稳定性和防止滥用：

| 限流类型 | 限制 | 时间窗口 | 说明 |
|----------|------|----------|------|
| **IP限流** | 10次/分钟 | 60秒 | 基于真实IP地址限制 |
| **用户限流** | 5次/分钟 | 60秒 | 基于用户标识限制 |
| **邮箱限流** | 3次/5分钟 | 300秒 | 专门针对评论提交的严格限制 |
| **全局限流** | 1000次/分钟 | 60秒 | 系统整体请求限制 |

> **注意**：邮箱限流是最严格的限制，旨在防止恶意评论和垃圾信息。用户在5分钟内最多只能提交3条评论。

## API端点

### 1. 获取评论列表

获取指定页面的评论列表，支持分页和排序。

**请求**
```http
GET /api/comments?page={页面标识}&page_num={页码}&page_size={每页数量}&sort={排序字段}&order={排序方向}
```

**参数说明**
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | string | 是 | - | 页面唯一标识 |
| page_num | integer | 否 | 1 | 页码，从1开始 |
| page_size | integer | 否 | 20 | 每页数量，最大100 |
| sort | string | 否 | created_at | 排序字段 |
| order | string | 否 | desc | 排序方向，asc或desc |

**响应示例**
```json
{
  "comments": [
    {
      "id": 1,
      "page": "blog-post-1",
      "email_hash": "d41d8cd98f00b204e9800998ecf8427e",
      "username": "张三",
      "content": "这是一条很好的文章评论。",
      "parent_id": null,
      "created_at": "2023-12-01T12:00:00Z",
      "updated_at": "2023-12-01T12:00:00Z",
      "system_type": "Windows",
      "location": "北京",
      "children": [
        {
          "id": 2,
          "page": "blog-post-1",
          "email_hash": "098f6bcd4621d373cade4e832627b4f6",
          "username": "李四",
          "content": "我也觉得很不错！",
          "parent_id": 1,
          "created_at": "2023-12-01T12:05:00Z",
          "updated_at": "2023-12-01T12:05:00Z",
          "system_type": "macOS",
          "location": "上海",
          "children": []
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### 2. 创建评论

创建新评论或回复现有评论。系统会自动检测用户的操作系统类型、地理位置等信息，并对评论提交进行严格的限流控制。

**重要提醒**：每个邮箱在5分钟内最多只能提交3条评论。

**请求**
```http
POST /api/comments
Content-Type: application/json

{
  "page": "blog-post-1",
  "email": "user@example.com",
  "username": "用户名",
  "content": "评论内容，至少10个字符",
  "parent_id": null
}
```

**参数说明**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| page | string | 是 | 页面唯一标识，最长200字符 |
| email | string | 是 | 用户邮箱，用于生成头像哈希 |
| username | string | 是 | 用户显示名称，2-100字符 |
| content | string | 是 | 评论内容，10-2000字符 |
| parent_id | integer | 否 | 父评论ID，null表示顶级评论 |

**响应示例**
```json
{
  "id": 3,
  "page": "blog-post-1",
  "email_hash": "5d41402abc4b2a76b9719d911017c592",
  "username": "新用户",
  "content": "这是我的第一条评论！",
  "parent_id": null,
  "created_at": "2023-12-01T13:00:00Z",
  "updated_at": "2023-12-01T13:00:00Z",
  "system_type": "iOS",
  "location": "广州",
  "children": []
}
```

### 3. 获取单个评论

根据ID获取指定评论的详细信息。

**请求**
```http
GET /api/comments/{comment_id}
```

**响应示例**
```json
{
  "id": 1,
  "page": "blog-post-1",
  "email_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "username": "张三",
  "content": "这是一条很好的文章评论。",
  "parent_id": null,
  "created_at": "2023-12-01T12:00:00Z",
  "updated_at": "2023-12-01T12:00:00Z",
  "system_type": "Windows",
  "location": "北京",
  "children": []
}
```

### 4. 删除评论（管理员）

软删除指定评论。

**请求**
```http
DELETE /api/comments/{comment_id}
```

**响应示例**
```json
{
  "success": true,
  "message": "评论删除成功",
  "timestamp": "abc12345"
}
```

### 5. 更新评论（管理员）

更新指定评论的内容或状态。

**请求**
```http
PUT /api/comments/{comment_id}
Content-Type: application/json

{
  "content": "更新后的评论内容",
  "is_deleted": false
}
```

**响应示例**
```json
{
  "id": 1,
  "page": "blog-post-1",
  "email_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "username": "张三",
  "content": "更新后的评论内容",
  "parent_id": null,
  "created_at": "2023-12-01T12:00:00Z",
  "updated_at": "2023-12-01T13:30:00Z",
  "system_type": "Windows",
  "location": "北京",
  "children": []
}
```

### 6. 获取页面统计

获取指定页面的评论统计信息。

**请求**
```http
GET /api/stats/{page}
```

**响应示例**
```json
{
  "success": true,
  "message": "获取统计信息成功",
  "data": {
    "total_comments": 15,
    "top_level_comments": 8,
    "replies": 7
  },
  "timestamp": "def67890"
}
```

### 7. 健康检查

检查系统各组件的运行状态。

**请求**
```http
GET /api/health
```

**响应示例**
```json
{
  "status": "healthy",
  "timestamp": "2023-12-01T14:00:00Z",
  "database": true,
  "redis": true,
  "version": "1.0.0"
}
```

## 错误处理

API使用标准HTTP状态码表示请求结果：

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 422 | 数据验证失败 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |

**错误响应格式**
```json
{
  "detail": "错误描述",
  "code": "ERROR_CODE",
  "timestamp": "2023-12-01T14:00:00Z"
}
```

**常见错误码**
| 错误码 | 说明 |
|--------|------|
| VALIDATION_ERROR | 数据验证失败 |
| RATE_LIMIT_EXCEEDED | 超过限流限制 |
| EMAIL_RATE_LIMIT_EXCEEDED | 邮箱提交频率过高（5分钟内超过3次） |
| IP_RATE_LIMIT_EXCEEDED | IP访问频率过高 |
| RESOURCE_NOT_FOUND | 资源不存在 |
| INTERNAL_SERVER_ERROR | 服务器内部错误 |

## 响应头

API响应包含以下有用的响应头：

| 响应头 | 说明 |
|--------|------|
| X-Request-ID | 请求唯一标识 |
| X-Process-Time | 请求处理时间（秒） |
| X-RateLimit-Limit | 限流限制 |
| X-RateLimit-Remaining | 剩余请求次数 |
| X-RateLimit-Reset | 限流重置时间戳 |

## 使用示例

### JavaScript (Fetch API)

```javascript
// 获取评论列表
async function getComments(page) {
  const response = await fetch(`/api/comments?page=${page}`);
  const data = await response.json();
  return data;
}

// 创建评论
async function createComment(commentData) {
  const response = await fetch('/api/comments', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(commentData)
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return await response.json();
}

// 使用示例
const commentData = {
  page: 'blog-post-1',
  email: 'user@example.com',
  username: '访客',
  content: '这是一条测试评论，内容足够长。'
};

createComment(commentData)
  .then(comment => console.log('评论创建成功:', comment))
  .catch(error => console.error('创建失败:', error));
```

### Python (requests)

```python
import requests

# 获取评论列表
def get_comments(page):
    response = requests.get(f'/api/comments?page={page}')
    response.raise_for_status()
    return response.json()

# 创建评论
def create_comment(comment_data):
    response = requests.post('/api/comments', json=comment_data)
    response.raise_for_status()
    return response.json()

# 使用示例
comment_data = {
    'page': 'blog-post-1',
    'email': 'user@example.com',
    'username': '访客',
    'content': '这是一条测试评论，内容足够长。'
}

try:
    comment = create_comment(comment_data)
    print(f'评论创建成功: {comment["id"]}')
except requests.RequestException as e:
    print(f'创建失败: {e}')
```

### cURL

```bash
# 获取评论列表
curl -X GET "http://localhost:8000/api/comments?page=blog-post-1" \
  -H "Accept: application/json"

# 创建评论
curl -X POST "http://localhost:8000/api/comments" \
  -H "Content-Type: application/json" \
  -d '{
    "page": "blog-post-1",
    "email": "user@example.com",
    "username": "访客",
    "content": "这是一条测试评论，内容足够长。"
  }'

# 获取页面统计
curl -X GET "http://localhost:8000/api/stats/blog-post-1" \
  -H "Accept: application/json"
```

## 最佳实践

### 1. 错误处理
始终检查HTTP状态码和响应中的错误信息：

```javascript
async function handleApiCall() {
  try {
    const response = await fetch('/api/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(commentData)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '请求失败');
    }
    
    return await response.json();
  } catch (error) {
    console.error('API调用失败:', error.message);
    throw error;
  }
}
```

### 2. 限流处理
遇到429错误时，检查Retry-After头并适当延迟重试：

```javascript
async function createCommentWithRetry(commentData, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch('/api/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(commentData)
      });
      
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After');
        if (retryAfter && i < maxRetries - 1) {
          await new Promise(resolve => setTimeout(resolve, parseInt(retryAfter) * 1000));
          continue;
        }
      }
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
    }
  }
}
```

### 3. 数据验证
在发送请求前进行客户端验证：

```javascript
function validateComment(data) {
  const errors = [];
  
  if (!data.page || data.page.length > 200) {
    errors.push('页面标识无效');
  }
  
  if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    errors.push('邮箱格式无效');
  }
  
  if (!data.username || data.username.length < 2 || data.username.length > 100) {
    errors.push('用户名长度应在2-100字符之间');
  }
  
  if (!data.content || data.content.length < 10 || data.content.length > 2000) {
    errors.push('评论内容长度应在10-2000字符之间');
  }
  
  return errors;
}
```

## 常见问题

### Q: 为什么不返回用户的真实邮箱？
A: 为了保护用户隐私，API只返回邮箱的MD5哈希值，可用于显示Gravatar头像。

### Q: 如何实现实时评论更新？
A: 当前版本不支持WebSocket，建议使用轮询方式定期获取最新评论。

### Q: 评论的嵌套层级有限制吗？
A: 没有技术限制，但建议UI层面限制嵌套深度以保证用户体验。

### Q: 如何处理垃圾评论？
A: 系统内置了多层防护机制：
- 严格的邮箱限流（5分钟内最多3条评论）
- IP地址限流保护
- 内容长度和格式验证
- 管理员可通过删除API移除不当评论

### Q: 系统如何获取用户地理位置？
A: 系统通过第三方IP地理位置服务自动识别用户所在地区，结果会缓存24小时以提高性能。

### Q: 限流触发后多久可以重新提交？
A: 邮箱限流触发后需要等待5分钟，IP限流触发后需要等待1分钟。系统会在响应头中提供准确的重试时间。

### Q: 限流触发后多久可以重新提交？
A: 邮箱限流触发后需要等待5分钟，IP限流触发后需要等待1分钟。系统会在响应头中提供准确的重试时间。

### Q: 支持富文本评论吗？
A: 当前版本只支持纯文本，HTML标签会被转义处理。