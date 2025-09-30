import pytest
from app.utils.user_info import SystemDetector, LocationService, IPHelper
from app.utils.helpers import SecurityUtils, ValidationUtils
from unittest.mock import patch, MagicMock


class TestSystemDetector:
    """系统检测器测试"""
    
    def test_detect_windows(self):
        """测试Windows系统检测"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36"
        ]
        
        for ua in user_agents:
            assert SystemDetector.detect_system(ua) == "Windows"
    
    def test_detect_macos(self):
        """测试macOS系统检测"""
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:87.0) Gecko/20100101"
        ]
        
        for ua in user_agents:
            assert SystemDetector.detect_system(ua) == "macOS"
    
    def test_detect_linux(self):
        """测试Linux系统检测"""
        user_agents = [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101"
        ]
        
        for ua in user_agents:
            assert SystemDetector.detect_system(ua) == "Linux"
    
    def test_detect_ios(self):
        """测试iOS系统检测"""
        user_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15",
            "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15"
        ]
        
        for ua in user_agents:
            assert SystemDetector.detect_system(ua) == "iOS"
    
    def test_detect_android(self):
        """测试Android系统检测"""
        user_agents = [
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36",
            "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36"
        ]
        
        for ua in user_agents:
            assert SystemDetector.detect_system(ua) == "Android"
    
    def test_detect_unknown(self):
        """测试未知系统检测"""
        assert SystemDetector.detect_system("") == "未知"
        assert SystemDetector.detect_system(None) == "未知"
        assert SystemDetector.detect_system("Unknown Browser") == "其他"


class TestLocationService:
    """地区信息服务测试"""
    
    @pytest.fixture
    def location_service(self):
        return LocationService()
    
    @pytest.mark.asyncio
    async def test_get_local_location(self, location_service):
        """测试本地IP地址"""
        local_ips = ["127.0.0.1", "localhost", "::1"]
        
        for ip in local_ips:
            location = await location_service.get_location(ip)
            assert location == "本地"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_get_location_success(self, mock_get, location_service):
        """测试成功获取地区信息"""
        # 模拟API响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "info": {
                "country": "中国",
                "region": "北京",
                "city": "北京"
            }
        }
        mock_get.return_value = mock_response
        
        location = await location_service.get_location("8.8.8.8")
        assert "中国" in location
        assert "北京" in location
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_get_location_api_failure(self, mock_get, location_service):
        """测试API调用失败"""
        # 模拟API失败
        mock_get.side_effect = Exception("API Error")
        
        location = await location_service.get_location("8.8.8.8")
        assert location == "未知"
    
    def test_parse_location_response(self, location_service):
        """测试地区响应解析"""
        # 测试成功响应
        data = {
            "success": True,
            "info": {
                "country": "中国",
                "region": "广东",
                "city": "深圳"
            }
        }
        location = location_service._parse_location_response(data)
        assert location == "中国 广东 深圳"
        
        # 测试失败响应
        data = {"success": False}
        location = location_service._parse_location_response(data)
        assert location == "未知"


class TestIPHelper:
    """IP助手测试"""
    
    def test_is_private_ip(self):
        """测试私有IP检测"""
        private_ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1"]
        public_ips = ["8.8.8.8", "1.1.1.1", "114.114.114.114"]
        
        for ip in private_ips:
            assert IPHelper.is_private_ip(ip) is True
        
        for ip in public_ips:
            assert IPHelper.is_private_ip(ip) is False
    
    def test_is_local_ip(self):
        """测试本地IP检测"""
        local_ips = ["127.0.0.1", "localhost", "::1", "0.0.0.0"]
        non_local_ips = ["8.8.8.8", "192.168.1.1"]
        
        for ip in local_ips:
            assert IPHelper.is_local_ip(ip) is True
        
        for ip in non_local_ips:
            assert IPHelper.is_local_ip(ip) is False
    
    def test_extract_real_ip(self):
        """测试真实IP提取"""
        headers = {
            "x-forwarded-for": "203.0.113.195, 70.41.3.18, 150.172.238.178",
            "x-real-ip": "203.0.113.195"
        }
        
        real_ip = IPHelper.extract_real_ip(headers)
        assert real_ip == "203.0.113.195"
        
        # 测试没有头部的情况
        empty_headers = {}
        real_ip = IPHelper.extract_real_ip(empty_headers)
        assert real_ip is None


class TestSecurityUtils:
    """安全工具测试"""
    
    def test_generate_email_hash(self):
        """测试邮箱哈希生成"""
        email = "test@example.com"
        hash1 = SecurityUtils.generate_email_hash(email)
        hash2 = SecurityUtils.generate_email_hash(email.upper())
        hash3 = SecurityUtils.generate_email_hash(f" {email} ")
        
        assert hash1 == hash2 == hash3
        assert len(hash1) == 32
    
    def test_sanitize_content(self):
        """测试内容清理"""
        content = "<script>alert('xss')</script>Hello World"
        sanitized = SecurityUtils.sanitize_content(content)
        
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized
        assert "Hello World" in sanitized
    
    def test_check_spam_content(self):
        """测试垃圾内容检测"""
        # 正常内容
        normal_content = "这是一条正常的评论内容"
        assert SecurityUtils.check_spam_content(normal_content) is False
        
        # 垃圾内容
        spam_content = "点击这里获取免费广告推广服务"
        assert SecurityUtils.check_spam_content(spam_content) is True


class TestValidationUtils:
    """验证工具测试"""
    
    def test_is_valid_email(self):
        """测试邮箱验证"""
        valid_emails = ["test@example.com", "user.name@domain.co.uk", "user+tag@example.org"]
        invalid_emails = ["invalid", "@domain.com", "user@", "user@domain"]
        
        for email in valid_emails:
            assert ValidationUtils.is_valid_email(email) is True
        
        for email in invalid_emails:
            assert ValidationUtils.is_valid_email(email) is False
    
    def test_is_valid_username(self):
        """测试用户名验证"""
        valid_usernames = ["用户名", "username", "用户123", "user_name"]
        invalid_usernames = ["", "a", "user<name>", "user'name", "user\"name"]
        
        for username in valid_usernames:
            assert ValidationUtils.is_valid_username(username) is True
        
        for username in invalid_usernames:
            assert ValidationUtils.is_valid_username(username) is False
    
    def test_is_valid_content_length(self):
        """测试内容长度验证"""
        # 正常长度
        valid_content = "这是一条测试评论内容，长度适中。"
        assert ValidationUtils.is_valid_content_length(valid_content) is True
        
        # 太短
        short_content = "太短"
        assert ValidationUtils.is_valid_content_length(short_content) is False
        
        # 太长
        long_content = "a" * 2001
        assert ValidationUtils.is_valid_content_length(long_content) is False