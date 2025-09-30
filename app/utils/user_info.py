import re
from typing import Optional
import httpx
import json
from app.core.config import settings
from app.core.database import get_redis
import logging

logger = logging.getLogger(__name__)


class SystemDetector:
    """系统类型检测器"""
    
    # 系统检测规则
    SYSTEM_PATTERNS = [
        (r'Windows NT|Windows', 'Windows'),
        (r'Macintosh|Mac OS X|macOS', 'macOS'),
        (r'Linux|Ubuntu|CentOS|Debian|Fedora', 'Linux'),
        (r'iPhone|iPad|iPod', 'iOS'),
        (r'Android', 'Android'),
    ]
    
    @classmethod
    def detect_system(cls, user_agent: str) -> str:
        """
        检测操作系统类型
        
        Args:
            user_agent: 用户代理字符串
            
        Returns:
            操作系统类型
        """
        if not user_agent:
            return "未知"
        
        for pattern, system_type in cls.SYSTEM_PATTERNS:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return system_type
        
        return "其他"


class LocationService:
    """地区信息获取服务"""
    
    def __init__(self):
        self.redis_client = get_redis()
        self.api_url = settings.VORE_API_URL
        self.timeout = settings.VORE_API_TIMEOUT
        self.cache_ttl = settings.VORE_API_CACHE_TTL
    
    def _get_cache_key(self, ip: str) -> str:
        """生成缓存键"""
        return f"location:{ip}"
    
    async def get_location(self, ip: str) -> str:
        """
        获取IP地址对应的地区信息
        
        Args:
            ip: IP地址
            
        Returns:
            地区信息字符串
        """
        if not ip or ip in ['127.0.0.1', 'localhost', '::1']:
            return "本地"
        
        # 检查缓存
        cache_key = self._get_cache_key(ip)
        try:
            cached_location = self.redis_client.get(cache_key)
            if cached_location:
                logger.debug(f"Cache hit for IP {ip}: {cached_location}")
                return cached_location
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")
        
        # 调用API获取地区信息
        location = await self._fetch_location_from_api(ip)
        
        # 缓存结果
        try:
            self.redis_client.setex(cache_key, self.cache_ttl, location)
            logger.debug(f"Cached location for IP {ip}: {location}")
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
        
        return location
    
    async def _fetch_location_from_api(self, ip: str) -> str:
        """
        从API获取地区信息
        
        Args:
            ip: IP地址
            
        Returns:
            地区信息
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 构建请求URL
                url = f"{self.api_url}?ip={ip}"
                
                # 发送请求，最多重试2次
                for attempt in range(3):
                    try:
                        response = await client.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            return self._parse_location_response(data)
                        else:
                            logger.warning(f"API request failed with status {response.status_code}")
                    except httpx.TimeoutException:
                        logger.warning(f"API request timeout (attempt {attempt + 1}/3)")
                        if attempt < 2:
                            continue
                        break
                    except Exception as e:
                        logger.warning(f"API request error (attempt {attempt + 1}/3): {e}")
                        if attempt < 2:
                            continue
                        break
        
        except Exception as e:
            logger.error(f"Failed to fetch location for IP {ip}: {e}")
        
        return "未知"
    
    def _parse_location_response(self, data: dict) -> str:
        """
        解析API响应数据
        
        Args:
            data: API响应数据
            
        Returns:
            格式化的地区信息
        """
        try:
            if data.get('success'):
                info = data.get('info', {})
                country = info.get('country', '')
                region = info.get('region', '')
                city = info.get('city', '')
                
                # 构建地区字符串
                parts = []
                if country and country != '未知':
                    parts.append(country)
                if region and region != '未知' and region != country:
                    parts.append(region)
                if city and city != '未知' and city != region:
                    parts.append(city)
                
                if parts:
                    return ' '.join(parts)
            
        except Exception as e:
            logger.error(f"Failed to parse location response: {e}")
        
        return "未知"


class IPHelper:
    """IP地址辅助工具"""
    
    @staticmethod
    def is_private_ip(ip: str) -> bool:
        """检查是否为私有IP地址"""
        try:
            import ipaddress
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private
        except Exception:
            return False
    
    @staticmethod
    def is_local_ip(ip: str) -> bool:
        """检查是否为本地IP地址"""
        local_ips = ['127.0.0.1', 'localhost', '::1', '0.0.0.0']
        return ip in local_ips
    
    @staticmethod
    def extract_real_ip(request_headers: dict) -> Optional[str]:
        """
        从请求头中提取真实IP地址
        
        Args:
            request_headers: 请求头字典
            
        Returns:
            真实IP地址
        """
        # 按优先级检查各种IP头
        ip_headers = [
            'x-forwarded-for',
            'x-real-ip',
            'cf-connecting-ip',  # Cloudflare
            'x-client-ip',
            'x-forwarded',
            'forwarded-for',
            'forwarded'
        ]
        
        for header in ip_headers:
            ip = request_headers.get(header)
            if ip:
                # X-Forwarded-For 可能包含多个IP，取第一个
                ip = ip.split(',')[0].strip()
                if ip and not IPHelper.is_private_ip(ip) and not IPHelper.is_local_ip(ip):
                    return ip
        
        return None


# 全局实例
system_detector = SystemDetector()
location_service = LocationService()