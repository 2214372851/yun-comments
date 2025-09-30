import pytest
from fastapi.testclient import TestClient
from app.schemas.comment import CommentCreate


class TestCommentAPI:
    """评论API集成测试"""
    
    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
    
    def test_create_comment_success(self, client, sample_comment_data):
        """测试成功创建评论"""
        response = client.post("/api/comments", json=sample_comment_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["page"] == sample_comment_data["page"]
        assert data["username"] == sample_comment_data["username"]
        assert data["content"] == sample_comment_data["content"]
        assert data["email_hash"] is not None  # 不返回原始邮箱
        assert data["id"] is not None
        assert data["created_at"] is not None
    
    def test_create_comment_validation_error(self, client):
        """测试评论创建验证错误"""
        invalid_data = {
            "page": "",  # 空页面标识
            "email": "invalid-email",  # 无效邮箱
            "username": "a",  # 用户名太短
            "content": "短"  # 内容太短
        }
        
        response = client.post("/api/comments", json=invalid_data)
        assert response.status_code == 422
    
    def test_get_comments_empty(self, client):
        """测试获取空评论列表"""
        response = client.get("/api/comments?page=empty-page")
        assert response.status_code == 200
        
        data = response.json()
        assert data["comments"] == []
        assert data["total"] == 0
        assert data["page"] == 1
    
    def test_get_comments_with_data(self, client, sample_comment_data):
        """测试获取包含数据的评论列表"""
        # 先创建一条评论
        create_response = client.post("/api/comments", json=sample_comment_data)
        assert create_response.status_code == 201
        
        # 获取评论列表
        response = client.get(f"/api/comments?page={sample_comment_data['page']}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 1
        assert len(data["comments"]) == 1
        assert data["comments"][0]["username"] == sample_comment_data["username"]
    
    def test_create_reply(self, client, sample_comment_data, sample_reply_data):
        """测试创建回复"""
        # 先创建一条父评论
        parent_response = client.post("/api/comments", json=sample_comment_data)
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["id"]
        
        # 创建回复
        sample_reply_data["parent_id"] = parent_id
        reply_response = client.post("/api/comments", json=sample_reply_data)
        assert reply_response.status_code == 201
        
        reply_data = reply_response.json()
        assert reply_data["parent_id"] == parent_id
    
    def test_get_comment_by_id(self, client, sample_comment_data):
        """测试根据ID获取评论"""
        # 创建评论
        create_response = client.post("/api/comments", json=sample_comment_data)
        comment_id = create_response.json()["id"]
        
        # 获取评论
        response = client.get(f"/api/comments/{comment_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == comment_id
        assert data["username"] == sample_comment_data["username"]
    
    def test_get_nonexistent_comment(self, client):
        """测试获取不存在的评论"""
        response = client.get("/api/comments/999999")
        assert response.status_code == 404
    
    def test_delete_comment(self, client, sample_comment_data):
        """测试删除评论"""
        # 创建评论
        create_response = client.post("/api/comments", json=sample_comment_data)
        comment_id = create_response.json()["id"]
        
        # 删除评论
        response = client.delete(f"/api/comments/{comment_id}")
        assert response.status_code == 200
        
        # 验证评论已被软删除（无法再获取）
        get_response = client.get(f"/api/comments/{comment_id}")
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_comment(self, client):
        """测试删除不存在的评论"""
        response = client.delete("/api/comments/999999")
        assert response.status_code == 404
    
    def test_get_page_stats(self, client, sample_comment_data):
        """测试获取页面统计"""
        # 创建几条评论
        for i in range(3):
            comment_data = sample_comment_data.copy()
            comment_data["email"] = f"test{i}@example.com"
            client.post("/api/comments", json=comment_data)
        
        # 获取统计信息
        response = client.get(f"/api/stats/{sample_comment_data['page']}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["total_comments"] == 3
    
    def test_pagination(self, client, sample_comment_data):
        """测试分页功能"""
        # 创建多条评论
        for i in range(5):
            comment_data = sample_comment_data.copy()
            comment_data["email"] = f"test{i}@example.com"
            comment_data["content"] = f"测试评论内容 {i} - 长度超过10个字符"
            client.post("/api/comments", json=comment_data)
        
        # 测试第一页
        response = client.get(
            f"/api/comments?page={sample_comment_data['page']}&page_num=1&page_size=2"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 5
        assert len(data["comments"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3
    
    def test_sorting(self, client, sample_comment_data):
        """测试排序功能"""
        # 创建评论
        client.post("/api/comments", json=sample_comment_data)
        
        # 测试按创建时间倒序（默认）
        response = client.get(
            f"/api/comments?page={sample_comment_data['page']}&sort=created_at&order=desc"
        )
        assert response.status_code == 200
        
        # 测试按创建时间正序
        response = client.get(
            f"/api/comments?page={sample_comment_data['page']}&sort=created_at&order=asc"
        )
        assert response.status_code == 200


class TestRateLimiting:
    """限流测试"""
    
    @pytest.mark.skip(reason="需要Redis支持，集成测试时启用")
    def test_rate_limiting(self, client, sample_comment_data):
        """测试限流机制"""
        # 快速发送多个请求
        responses = []
        for i in range(10):
            comment_data = sample_comment_data.copy()
            comment_data["email"] = f"test{i}@example.com"
            response = client.post("/api/comments", json=comment_data)
            responses.append(response)
        
        # 检查是否有请求被限流
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes  # 应该有请求被限流


class TestErrorHandling:
    """错误处理测试"""
    
    def test_invalid_json(self, client):
        """测试无效JSON"""
        response = client.post(
            "/api/comments",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_missing_required_fields(self, client):
        """测试缺少必需字段"""
        incomplete_data = {
            "page": "test-page"
            # 缺少其他必需字段
        }
        
        response = client.post("/api/comments", json=incomplete_data)
        assert response.status_code == 422
    
    def test_invalid_page_parameter(self, client):
        """测试无效页面参数"""
        response = client.get("/api/comments?page=&page_num=abc")
        assert response.status_code == 422