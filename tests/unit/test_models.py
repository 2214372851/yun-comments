import pytest
from app.models.comment import Comment
from app.utils.helpers import SecurityUtils


class TestComment:
    """评论模型测试"""
    
    def test_comment_creation(self, db_session):
        """测试评论创建"""
        comment = Comment(
            page="test-page",
            email="test@example.com",
            username="测试用户",
            content="测试评论内容",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Test Browser)",
            system_type="Windows",
            location="北京"
        )
        
        db_session.add(comment)
        db_session.commit()
        
        assert comment.id is not None
        assert comment.email_hash == Comment.generate_email_hash("test@example.com")
        assert comment.is_deleted is False
        assert comment.created_at is not None
    
    def test_email_hash_generation(self):
        """测试邮箱哈希生成"""
        email = "test@example.com"
        hash1 = Comment.generate_email_hash(email)
        hash2 = Comment.generate_email_hash(email.upper())  # 测试大小写
        hash3 = Comment.generate_email_hash(f" {email} ")  # 测试空格
        
        assert hash1 == hash2 == hash3
        assert len(hash1) == 32  # MD5哈希长度
    
    def test_comment_to_dict(self, db_session):
        """测试评论转字典"""
        comment = Comment(
            page="test-page",
            email="test@example.com",
            username="测试用户",
            content="测试评论内容",
            system_type="Windows",
            location="北京"
        )
        
        db_session.add(comment)
        db_session.commit()
        
        data = comment.to_dict()
        
        assert data["page"] == "test-page"
        assert data["username"] == "测试用户"
        assert data["content"] == "测试评论内容"
        assert data["email_hash"] is not None
        assert "children" not in data  # 默认不包含子评论
    
    def test_comment_with_children(self, db_session):
        """测试带子评论的评论转换"""
        # 创建父评论
        parent = Comment(
            page="test-page",
            email="parent@example.com",
            username="父评论用户",
            content="父评论内容"
        )
        db_session.add(parent)
        db_session.commit()
        
        # 创建子评论
        child = Comment(
            page="test-page",
            email="child@example.com",
            username="子评论用户",
            content="子评论内容",
            parent_id=parent.id
        )
        db_session.add(child)
        db_session.commit()
        
        # 刷新父评论以获取关联关系
        db_session.refresh(parent)
        
        data = parent.to_dict(include_children=True)
        
        assert "children" in data
        assert len(data["children"]) == 1
        assert data["children"][0]["content"] == "子评论内容"
    
    def test_soft_delete(self, db_session):
        """测试软删除"""
        comment = Comment(
            page="test-page",
            email="test@example.com",
            username="测试用户",
            content="测试评论内容"
        )
        
        db_session.add(comment)
        db_session.commit()
        
        # 软删除
        comment.is_deleted = True
        db_session.commit()
        
        # 验证软删除状态
        assert comment.is_deleted is True
        
        # 测试转换字典时不包含已删除的子评论
        parent_data = comment.to_dict(include_children=True)
        assert parent_data["children"] == []