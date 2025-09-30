import pytest
import asyncio
import httpx
from app.services.comment_service import CommentService
from app.schemas.comment import CommentCreate, CommentQuery
from app.models.comment import Comment
from unittest.mock import AsyncMock, patch


class TestCommentService:
    """评论服务测试"""
    
    @pytest.mark.asyncio
    async def test_create_comment_success(self, db_session):
        """测试成功创建评论"""
        service = CommentService(db_session)
        
        comment_data = CommentCreate(
            page="test-page",
            email="test@example.com",
            username="测试用户",
            content="这是一条测试评论，长度超过10个字符。"
        )
        
        with patch('app.services.comment_service.check_email_rate_limit_for_comment') as mock_rate_limit:
            mock_rate_limit.return_value = None  # 不触发限流
            
            with patch.object(service, '_clear_page_cache') as mock_clear_cache:
                comment = await service.create_comment(
                    comment_data=comment_data,
                    ip_address="192.168.1.1",
                    user_agent="Mozilla/5.0 (Test)"
                )
        
        assert comment.id is not None
        assert comment.page == "test-page"
        assert comment.username == "测试用户"
        assert comment.email_hash is not None
        assert comment.ip_address == "192.168.1.1"
        mock_clear_cache.assert_called_once_with("test-page")
    
    @pytest.mark.asyncio
    async def test_create_reply_success(self, db_session):
        """测试成功创建回复"""
        service = CommentService(db_session)
        
        # 先创建父评论
        parent = Comment(
            page="test-page",
            email="parent@example.com",
            username="父评论用户",
            content="父评论内容"
        )
        db_session.add(parent)
        db_session.commit()
        
        # 创建回复
        reply_data = CommentCreate(
            page="test-page",
            email="reply@example.com",
            username="回复用户",
            content="这是一条回复内容，长度超过10个字符。",
            parent_id=parent.id
        )
        
        with patch('app.services.comment_service.check_email_rate_limit_for_comment'):
            with patch.object(service, '_clear_page_cache'):
                reply = await service.create_comment(
                    comment_data=reply_data,
                    ip_address="192.168.1.1",
                    user_agent="Mozilla/5.0 (Test)"
                )
        
        assert reply.parent_id == parent.id
        assert reply.page == parent.page
    
    @pytest.mark.asyncio
    async def test_create_comment_with_spam_content(self, db_session):
        """测试创建包含垃圾内容的评论"""
        service = CommentService(db_session)
        
        spam_data = CommentCreate(
            page="test-page",
            email="spam@example.com",
            username="垃圾用户",
            content="点击这里获取免费广告推广服务，赚钱机会"
        )
        
        with patch('app.services.comment_service.check_email_rate_limit_for_comment'):
            with pytest.raises(Exception):  # 应该抛出验证异常
                await service.create_comment(
                    comment_data=spam_data,
                    ip_address="192.168.1.1",
                    user_agent="Mozilla/5.0 (Test)"
                )
    
    @pytest.mark.asyncio
    async def test_get_comments_success(self, db_session):
        """测试成功获取评论列表"""
        service = CommentService(db_session)
        
        # 创建测试数据
        comments = []
        for i in range(3):
            comment = Comment(
                page="test-page",
                email=f"test{i}@example.com",
                username=f"用户{i}",
                content=f"测试评论内容{i}"
            )
            comments.append(comment)
            db_session.add(comment)
        
        db_session.commit()
        
        # 查询评论
        query = CommentQuery(page="test-page")
        
        with patch.object(service, '_get_from_cache', return_value=None):
            with patch.object(service, '_set_cache') as mock_set_cache:
                result = await service.get_comments(query)
        
        assert result["total"] == 3
        assert len(result["comments"]) == 3
        assert result["page"] == 1
        mock_set_cache.assert_called_once()  # 应该缓存结果
    
    @pytest.mark.asyncio
    async def test_delete_comment_success(self, db_session):
        """测试成功删除评论"""
        service = CommentService(db_session)
        
        # 创建评论
        comment = Comment(
            page="test-page",
            email="test@example.com",
            username="测试用户",
            content="测试评论内容"
        )
        db_session.add(comment)
        db_session.commit()
        
        comment_id = comment.id
        
        with patch.object(service, '_clear_page_cache') as mock_clear_cache:
            success = await service.delete_comment(comment_id)
        
        assert success is True
        
        # 验证软删除
        deleted_comment = db_session.query(Comment).filter(Comment.id == comment_id).first()
        assert deleted_comment.is_deleted is True
        mock_clear_cache.assert_called_once_with("test-page")
    
    @pytest.mark.asyncio
    async def test_get_page_stats(self, db_session):
        """测试获取页面统计"""
        service = CommentService(db_session)
        
        # 创建测试数据
        # 2条顶级评论
        for i in range(2):
            comment = Comment(
                page="test-page",
                email=f"top{i}@example.com",
                username=f"顶级用户{i}",
                content=f"顶级评论{i}"
            )
            db_session.add(comment)
        
        db_session.commit()
        
        # 1条回复
        parent_id = db_session.query(Comment).first().id
        reply = Comment(
            page="test-page",
            email="reply@example.com",
            username="回复用户",
            content="回复内容",
            parent_id=parent_id
        )
        db_session.add(reply)
        db_session.commit()
        
        with patch.object(service, '_get_from_cache', return_value=None):
            with patch.object(service, '_set_cache'):
                stats = await service.get_page_stats("test-page")
        
        assert stats["total_comments"] == 3
        assert stats["top_level_comments"] == 2
        assert stats["replies"] == 1
    
    @pytest.mark.asyncio
    async def test_build_comment_tree(self, db_session):
        """测试构建评论树"""
        service = CommentService(db_session)
        
        # 创建父评论
        parent = Comment(
            page="test-page",
            email="parent@example.com",
            username="父用户",
            content="父评论"
        )
        db_session.add(parent)
        db_session.commit()
        
        # 创建子评论
        child1 = Comment(
            page="test-page",
            email="child1@example.com",
            username="子用户1",
            content="子评论1",
            parent_id=parent.id
        )
        child2 = Comment(
            page="test-page",
            email="child2@example.com",
            username="子用户2",
            content="子评论2",
            parent_id=parent.id
        )
        db_session.add_all([child1, child2])
        db_session.commit()
        
        # 构建评论树
        comments = [parent, child1, child2]
        tree = service._build_comment_tree(comments)
        
        assert len(tree) == 1  # 只有一个顶级评论
        assert len(tree[0]["children"]) == 2  # 有两个子评论
        assert tree[0]["username"] == "父用户"
        
        # 验证子评论
        children_usernames = [child["username"] for child in tree[0]["children"]]
        assert "子用户1" in children_usernames
        assert "子用户2" in children_usernames


class TestLocationServiceIntegration:
    """地区服务集成测试"""
    
    @pytest.mark.asyncio
    async def test_location_service_with_real_api(self):
        """测试真实API调用（可选）"""
        from app.utils.user_info import LocationService
        
        service = LocationService()
        
        # 使用公共DNS的IP进行测试
        location = await service.get_location("8.8.8.8")
        
        # 结果应该不是"未知"（除非API确实失败）
        assert isinstance(location, str)
        assert location != ""
    
    @pytest.mark.asyncio 
    async def test_location_service_caching(self):
        """测试地区服务缓存"""
        from app.utils.user_info import LocationService
        
        service = LocationService()
        
        with patch.object(service, '_fetch_location_from_api') as mock_fetch:
            mock_fetch.return_value = "测试地区"
            
            # 第一次调用
            location1 = await service.get_location("1.2.3.4")
            
            # 第二次调用应该使用缓存
            location2 = await service.get_location("1.2.3.4")
            
            assert location1 == location2 == "测试地区"
            # API只应该被调用一次（第二次使用缓存）
            assert mock_fetch.call_count <= 1