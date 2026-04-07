"""
基础单元测试
测试核心模块的功能
"""

import os
import sys
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.device_manager import DeviceManager, Device, DeviceStatus, DeviceType
from src.adb_client import ADBClient, Point, SwipeGesture
from src.screen import TextMatch, ScreenController
from src.script_runner import ScriptRunner, ActionType, ActionResult
from src.command_handler import CommandHandler, CommandType, ParsedCommand


# ==================== 设备管理器测试 ====================

class TestDeviceManager:
    """设备管理器测试"""

    def test_device_creation(self):
        """测试设备对象创建"""
        manager = DeviceManager()
        assert manager is not None

    @patch('subprocess.run')
    def test_list_devices(self, mock_run):
        """测试获取设备列表"""
        # 模拟adb devices输出
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""List of devices attached
abc123	device
def456	unauthorized
ghi789	offline
192.168.1.100:5555	device
"""
        )

        manager = DeviceManager()
        devices = manager.list_devices(refresh=True)

        assert len(devices) == 4
        assert devices[0].device_id == "abc123"
        assert devices[0].status == DeviceStatus.CONNECTED
        assert devices[1].status == DeviceStatus.UNAUTHORIZED


# ==================== ADB客户端测试 ====================

class TestADBClient:
    """ADB客户端测试"""

    @patch('subprocess.run')
    def test_click(self, mock_run):
        """测试点击操作"""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager = Mock()
        client = ADBClient(manager, device_id="test_device")
        result = client.click(100, 200)

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "input tap 100 200" in " ".join(call_args)

    @patch('subprocess.run')
    def test_swipe(self, mock_run):
        """测试滑动操作"""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager = Mock()
        client = ADBClient(manager, device_id="test_device")
        result = client.swipe(100, 200, 300, 400, duration=500)

        assert result is True
        mock_run.assert_called_once()

    def test_point_from_string(self):
        """测试从字符串创建Point对象"""
        point = Point.from_string("100,200")
        assert point.x == 100
        assert point.y == 200

        point2 = Point.from_string("  300 ,  400  ")
        assert point2.x == 300
        assert point2.y == 400


# ==================== 屏幕控制器测试 ====================

class TestScreenController:
    """屏幕控制器测试"""

    @patch('subprocess.run')
    @patch('cv2.imdecode')
    def test_screenshot(self, mock_decode, mock_run):
        """测试截图功能"""
        # 模拟截图数据
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b"fake_image_data",
            stderr=""
        )
        mock_decode.return_value = MagicMock(shape=(1920, 1080, 3))

        manager = Mock()
        controller = ScreenController(manager)
        image = controller.screenshot(device_id="test_device")

        assert image is not None

    def test_text_match_creation(self):
        """测试文字匹配对象创建"""
        match = TextMatch(
            text="测试文字",
            x=100,
            y=200,
            width=300,
            height=50,
            confidence=0.95
        )

        assert match.center == (250, 225)
        assert match.text == "测试文字"


# ==================== 脚本执行引擎测试 ====================

class TestScriptRunner:
    """脚本执行引擎测试"""

    def test_validate_script_valid(self):
        """测试验证有效脚本"""
        script = [
            {"action": "click", "params": {"target": "100,200"}},
            {"action": "sleep", "params": {"seconds": 1}}
        ]

        manager = Mock()
        runner = ScriptRunner(manager)
        is_valid, message = runner.validate_script(script)

        assert is_valid is True
        assert "有效" in message

    def test_validate_script_invalid(self):
        """测试验证无效脚本"""
        script = [
            {"action": "invalid_action", "params": {}}
        ]

        manager = Mock()
        runner = ScriptRunner(manager)
        is_valid, message = runner.validate_script(script)

        assert is_valid is False
        assert "无效" in message or "invalid" in message.lower()

    def test_validate_script_not_list(self):
        """测试验证非列表脚本"""
        script = {"action": "click", "params": {}}

        manager = Mock()
        runner = ScriptRunner(manager)
        is_valid, message = runner.validate_script(script)

        assert is_valid is False


# ==================== 指令处理器测试 ====================

class TestCommandHandler:
    """指令处理器测试"""

    def test_parse_click_command(self):
        """测试解析点击指令"""
        handler = CommandHandler()
        result = handler.parse("点击 500,1000")

        assert result.command_type == CommandType.CLICK
        assert result.params.get("target") == "500,1000"

    def test_parse_click_by_text(self):
        """测试解析文字点击指令"""
        handler = CommandHandler()
        result = handler.parse("点击设置")

        assert result.command_type == CommandType.CLICK
        assert result.params.get("target") == "设置"

    def test_parse_swipe_command(self):
        """测试解析滑动指令"""
        handler = CommandHandler()
        result = handler.parse("滑动 100,200 100,800 500")

        assert result.command_type == CommandType.SWIPE
        assert result.params.get("start") == "100,200"
        assert result.params.get("end") == "100,800"
        assert result.params.get("duration") == "500"

    def test_parse_unknown_command(self):
        """测试解析未知指令"""
        handler = CommandHandler()
        result = handler.parse("这是一个未知的指令")

        assert result.command_type == CommandType.UNKNOWN

    def test_parse_english_click(self):
        """测试解析英文点击指令"""
        handler = CommandHandler()
        result = handler.parse("click 100,200")

        assert result.command_type == CommandType.CLICK
        assert result.params.get("target") == "100,200"

    def test_to_api_request(self):
        """测试转换为API请求"""
        handler = CommandHandler()
        parsed = ParsedCommand(
            command_type=CommandType.CLICK,
            params={"target": "500,1000"},
            original_text="点击 500,1000"
        )

        endpoint, body = handler.to_api_request(parsed)

        assert "/control/click" in endpoint
        assert body.get("target") == "500,1000"


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试"""

    def test_end_to_end_command_parsing(self):
        """测试端到端指令解析流程"""
        handler = CommandHandler()

        commands = [
            ("点击 100,200", CommandType.CLICK),
            ("滑动 100,200 300,400", CommandType.SWIPE),
            ("输入 Hello", CommandType.INPUT),
            ("按键 home", CommandType.KEY),
            ("截屏", CommandType.SCREENSHOT),
        ]

        for cmd_text, expected_type in commands:
            result = handler.parse(cmd_text)
            assert result.command_type == expected_type, f"命令 '{cmd_text}' 解析错误"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
