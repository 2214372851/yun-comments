from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import hashlib


class Comment(Base):
    """评论模型"""
    __tablename__ = "comments"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 页面标识
    page = Column(String(200), nullable=False, index=True, comment="页面唯一标识")
    
    # 用户信息
    email = Column(String(255), nullable=False, comment="用户邮箱")
    email_hash = Column(String(32), nullable=False, comment="邮箱MD5哈希")
    username = Column(String(100), nullable=False, comment="用户显示名称")
    
    # 评论内容
    content = Column(Text, nullable=False, comment="评论内容")
    
    # 回复关系
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True, comment="父评论ID")
    parent = relationship("Comment", remote_side=[id], backref="children")
    
    # 状态字段
    is_deleted = Column(Boolean, default=False, nullable=False, comment="软删除标记")
    
    # 时间字段
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 用户环境信息
    ip_address = Column(INET, nullable=True, comment="用户IP地址")
    user_agent = Column(Text, nullable=True, comment="用户代理信息")
    system_type = Column(String(50), nullable=True, comment="操作系统类型")
    location = Column(String(100), nullable=True, comment="用户地区信息")
    
    # 创建索引
    __table_args__ = (
        Index('idx_page', 'page'),
        Index('idx_parent_id', 'parent_id'),
        Index('idx_created_at', 'created_at'),
        Index('idx_email_ip', 'email', 'ip_address'),
        Index('idx_page_parent_deleted', 'page', 'parent_id', 'is_deleted'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 自动生成邮箱哈希
        if self.email and not self.email_hash:
            self.email_hash = self.generate_email_hash(self.email)
    
    @staticmethod
    def generate_email_hash(email: str) -> str:
        """生成邮箱MD5哈希"""
        return hashlib.md5(email.lower().strip().encode()).hexdigest()
    
    def to_dict(self, include_children: bool = False) -> dict:
        """转换为字典格式"""
        data = {
            "id": self.id,
            "page": self.page,
            "email_hash": self.email_hash,
            "username": self.username,
            "content": self.content,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "system_type": self.system_type,
            "location": self.location,
        }
        
        if include_children:
            data["children"] = [
                child.to_dict(include_children=True) 
                for child in self.children 
                if not child.is_deleted
            ]
        
        return data
    
    def __repr__(self):
        return f"<Comment(id={self.id}, page='{self.page}', username='{self.username}')>"