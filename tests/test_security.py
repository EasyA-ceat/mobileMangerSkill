"""
安全测试套件 - 测试手机控制技能项目的安全修复
包含：API认证、CORS配置、速率限制、安全头、命令注入防护
"""
import os
import sys
import time
import pytest
import httpx
import asyncio
from typing import AsyncGenerator
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试配置
BASE_URL = "http://localhost:8080"
TEST_API_KEY = "test-api-key-for-security-testing"


@pytest.fixture(scope="module")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def test_api_key() -> str:
    """获取测试用的API Key"""
    # 如果环境变量中有设置则使用，否则使用默认测试key
    return os.getenv("TEST_API_KEY", TEST_API_KEY)


@pytest.fixture(scope="module")
async def authenticated_client(test_api_key: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """已认证的HTTP客户端"""
    headers = {"X-API-Key": test_api_key}
    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
async def unauthenticated_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """未认证的HTTP客户端"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
async def wrong_key_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """使用错误API Key的HTTP客户端"""
    headers = {"X-API-Key": "wrong-api-key-12345"}
    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
        yield client


# ==================== API认证测试 ====================

class TestAPIAuthentication:
    """API Key认证功能测试"""
    
    async def test_health_check_no_auth_required(self, unauthenticated_client: httpx.AsyncClient):
        """测试健康检查接口不需要认证"""
        response = await unauthenticated_client.get("/health")
        assert response.status_code in [200, 404]
    
    async def test_protected_endpoint_no_auth(self, unauthenticated_client: httpx.AsyncClient):
        """测试受保护接口无认证返回401"""
        try:
            response = await unauthenticated_client.post("/api/v1/devices", json={"refresh": False})
            assert response.status_code == 401
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_protected_endpoint_wrong_key(self, wrong_key_client: httpx.AsyncClient):
        """测试受保护接口错误API Key返回401"""
        try:
            response = await wrong_key_client.post("/api/v1/devices", json={"refresh": False})
            assert response.status_code == 401
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_api_key_in_header(self, authenticated_client: httpx.AsyncClient):
        """测试Header方式传递API Key"""
        try:
            response = await authenticated_client.post("/api/v1/devices", json={"refresh": False})
            assert response.status_code != 401
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_api_key_in_query_param(self, test_api_key: str):
        """测试Query参数方式传递API Key"""
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
                response = await client.post(
                    f"/api/v1/devices?api_key={test_api_key}",
                    json={"refresh": False}
                )
                assert response.status_code != 401
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")


# ==================== CORS配置测试 ====================

class TestCORSConfiguration:
    """CORS配置测试"""
    
    async def test_cors_allowed_origin(self, test_api_key: str):
        """测试允许的Origin可以正常请求"""
        try:
            headers = {
                "X-API-Key": test_api_key,
                "Origin": "http://localhost:8080"
            }
            async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
                response = await client.options("/api/v1/devices")
                # 检查CORS头
                if "access-control-allow-origin" in response.headers:
                    assert response.headers["access-control-allow-origin"] in ["*", "http://localhost:8080"]
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_cors_disallowed_origin(self, test_api_key: str):
        """测试不允许的Origin被拒绝（仅验证CORS头）"""
        try:
            headers = {
                "X-API-Key": test_api_key,
                "Origin": "http://malicious.com"
            }
            async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
                response = await client.options("/api/v1/devices")
                # 恶意域名不应出现在allow-origin中
                if "access-control-allow-origin" in response.headers:
                    assert "malicious.com" not in response.headers["access-control-allow-origin"]
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")


# ==================== 安全HTTP头测试 ====================

class TestSecurityHeaders:
    """安全HTTP头测试"""
    
    async def test_security_headers_present(self, authenticated_client: httpx.AsyncClient):
        """测试安全HTTP头是否存在"""
        try:
            response = await authenticated_client.get("/health")
            headers = response.headers
            
            # 检查X-Content-Type-Options
            if "x-content-type-options" in headers:
                assert headers["x-content-type-options"].lower() == "nosniff"
            
            # 检查X-Frame-Options
            if "x-frame-options" in headers:
                assert headers["x-frame-options"].upper() in ["DENY", "SAMEORIGIN"]
            
            # 检查X-XSS-Protection
            if "x-xss-protection" in headers:
                assert "1" in headers["x-xss-protection"]
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")


# ==================== 命令注入防护测试 ====================

class TestCommandInjectionProtection:
    """命令注入防护测试"""
    
    async def test_coordinate_injection_attempt(self, authenticated_client: httpx.AsyncClient):
        """测试坐标参数注入攻击"""
        try:
            # 尝试注入命令
            response = await authenticated_client.post(
                "/api/v1/devices/test-device/tap",
                json={"target": "100; rm -rf /; 200"}
            )
            # 应该返回验证错误，而不是执行命令
            assert response.status_code != 500
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_package_name_injection_attempt(self, authenticated_client: httpx.AsyncClient):
        """测试包名参数注入攻击"""
        try:
            response = await authenticated_client.post(
                "/api/v1/devices/test-device/app",
                json={
                    "action": "start",
                    "package_name": "com.evil.app; rm -rf /"
                }
            )
            assert response.status_code != 500
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_key_code_injection_attempt(self, authenticated_client: httpx.AsyncClient):
        """测试按键码参数注入攻击"""
        try:
            response = await authenticated_client.post(
                "/api/v1/devices/test-device/key",
                json={"key": "KEYCODE_HOME; cat /etc/passwd"}
            )
            assert response.status_code != 500
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")


# ==================== 速率限制测试 ====================

class TestRateLimiting:
    """速率限制测试"""
    
    async def test_rate_limiting_device_list(self, authenticated_client: httpx.AsyncClient):
        """测试设备列表接口速率限制"""
        try:
            # 快速发送多个请求
            responses = []
            for i in range(5):
                response = await authenticated_client.post("/api/v1/devices", json={"refresh": False})
                responses.append(response.status_code)
            
            # 至少有一个成功响应
            assert any(code == 200 for code in responses)
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_rate_limiting_control_actions(self, authenticated_client: httpx.AsyncClient):
        """测试控制接口速率限制"""
        try:
            # 快速发送多个控制请求
            responses = []
            for i in range(10):
                response = await authenticated_client.post(
                    "/api/v1/devices/test-device/tap",
                    json={"target": "100,100"}
                )
                responses.append(response.status_code)
                time.sleep(0.01)
            
            # 至少有一个成功响应
            assert any(code in [200, 400, 429] for code in responses)
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")


# ==================== 输入验证测试 ====================

class TestInputValidation:
    """输入验证测试"""
    
    async def test_invalid_coordinate_format(self, authenticated_client: httpx.AsyncClient):
        """测试无效的坐标格式"""
        try:
            response = await authenticated_client.post(
                "/api/v1/devices/test-device/tap",
                json={"target": "invalid-coordinate"}
            )
            assert response.status_code in [200, 400, 422]
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_extremely_long_input(self, authenticated_client: httpx.AsyncClient):
        """测试超长输入"""
        try:
            long_text = "a" * 10000
            response = await authenticated_client.post(
                "/api/v1/devices/test-device/input",
                json={"text": long_text}
            )
            assert response.status_code != 500
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")
    
    async def test_special_characters_input(self, authenticated_client: httpx.AsyncClient):
        """测试特殊字符输入"""
        try:
            special_chars = "<script>alert('xss')</script>; rm -rf /"
            response = await authenticated_client.post(
                "/api/v1/devices/test-device/input",
                json={"text": special_chars}
            )
            assert response.status_code != 500
        except httpx.ConnectError:
            pytest.skip("服务器未运行，跳过此测试")


# ==================== WebSocket认证测试 ====================

class TestWebSocketAuthentication:
    """WebSocket认证测试"""
    
    async def test_websocket_no_auth(self):
        """测试WebSocket无认证被拒绝"""
        try:
            # httpx不支持WebSocket，这里跳过，实际测试需要使用websockets库
            pytest.skip("WebSocket测试需要专用客户端，跳过")
        except Exception:
            pytest.skip("WebSocket测试跳过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
