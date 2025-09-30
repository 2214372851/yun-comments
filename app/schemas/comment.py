from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
import re


class CommentBase(BaseModel):
    """评论基础模型"""
    page: str = Field(..., min_length=1, max_length=200, description="页面唯一标识")
    username: str = Field(..., min_length=2, max_length=100, description="用户显示名称")
    content: str = Field(..., min_length=10, max_length=2000, description="评论内容")
    parent_id: Optional[int] = Field(None, description="父评论ID，null表示顶级评论")
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名格式"""
        if not v.strip():
            raise ValueError("用户名不能为空")
        
        # 检查是否包含特殊字符
        if re.search(r'[<>"\'/\\]', v):
            raise ValueError("用户名不能包含特殊字符")
        
        return v.strip()
    
    @validator('content')
    def validate_content(cls, v):
        """验证评论内容"""
        if not v.strip():
            raise ValueError("评论内容不能为空")
        
        # 简单的垃圾内容检测
        spam_keywords = ['广告', '推广', 'spam', '色情', '赌博']
        content_lower = v.lower()
        for keyword in spam_keywords:
            if keyword in content_lower:
                raise ValueError("评论内容包含不当内容")
        
        return v.strip()
    
    @validator('page')
    def validate_page(cls, v):
        """验证页面标识"""
        if not v.strip():
            raise ValueError("页面标识不能为空")
        return v.strip()


class CommentCreate(CommentBase):
    """创建评论请求模型"""
    email: EmailStr = Field(..., description="用户邮箱")


class CommentUpdate(BaseModel):
    """更新评论请求模型（管理员用）"""
    content: Optional[str] = Field(None, min_length=10, max_length=2000, description="评论内容")
    is_deleted: Optional[bool] = Field(None, description="软删除标记")


class CommentResponse(BaseModel):
    """评论响应模型"""
    id: int
    page: str
    email_hash: str
    username: str
    content: str
    parent_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    system_type: Optional[str]
    location: Optional[str]
    children: List['CommentResponse'] = []
    
    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """评论列表响应模型"""
    comments: List[CommentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CommentQuery(BaseModel):
    """评论查询参数模型"""
    page: str = Field(..., description="页面标识")
    page_num: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    sort: str = Field("created_at", description="排序字段")
    order: str = Field("desc", pattern="^(asc|desc)$", description="排序方向")


class HealthCheck(BaseModel):
    """健康检查响应模型"""
    status: str
    timestamp: datetime
    database: bool
    redis: bool
    version: str


class ErrorResponse(BaseModel):
    """错误响应模型"""
    detail: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class RateLimitInfo(BaseModel):
    """限流信息模型"""
    limit: int
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None


# 解决循环引用问题
CommentResponse.model_rebuild()