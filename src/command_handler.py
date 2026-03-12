"""
用户指令接口层
解析自然语言指令，映射到对应的API调用
"""

import re
import json
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """指令类型"""
    # 设备管理
    DEVICE_LIST = "device_list"
    DEVICE_CONNECT = "device_connect"
    DEVICE_DISCONNECT = "device_disconnect"

    # 控制操作
    CLICK = "click"
    SWIPE = "swipe"
    INPUT = "input"
    KEY = "key"
    APP = "app"

    # 屏幕操作
    SCREENSHOT = "screenshot"
    OCR = "ocr"
    FIND_TEXT = "find_text"

    # 脚本
    SCRIPT_RUN = "script_run"

    # 未知
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    """解析后的指令"""
    command_type: CommandType
    params: Dict[str, Any]
    original_text: str
    confidence: float = 1.0  # 置信度


class CommandHandler:
    """
    指令处理器
    解析自然语言指令并映射到API调用
    """

    # 指令模式定义
    PATTERNS = {
        # 设备管理
        CommandType.DEVICE_LIST: [
            r"(?:手机|设备)[列列][表表]",
            r"(?:list|show)\s*(?:devices?|phones?)",
            r"devices?",
        ],
        CommandType.DEVICE_CONNECT: [
            r"连[接接](?:手机|设备)?\s*(\S+)",
            r"connect\s*(?:to)?\s*(\S+)",
        ],
        CommandType.DEVICE_DISCONNECT: [
            r"断[开开](?:手机|设备)?\s*(\S+)",
            r"disconnect\s*(?:from)?\s*(\S+)",
        ],

        # 控制操作
        CommandType.CLICK: [
            r"点[击击]\s*(.+)",
            r"(?:click|tap)\s*(.+)",
            r"(?:按|press)\s*(.+)",
        ],
        CommandType.SWIPE: [
            r"滑[动动]\s*(\S+)\s*(\S+)(?:\s*(\d+))?",
            r"(?:swipe|slide)\s*(\S+)\s*(\S+)(?:\s*(\d+))?",
        ],
        CommandType.INPUT: [
            r"[输输][入入]\s*(.+)",
            r"(?:input|type|enter)\s*(.+)",
            r"(?:send|text)\s*(.+)",
        ],
        CommandType.KEY: [
            r"(?:按|press)?[键键]\s*(\w+)",
            r"key\s*(\w+)",
        ],
        CommandType.APP: [
            r"(?:打开|启动|open|start)\s*app\s*(\S+)",
            r"(?:关闭|停止|close|stop)\s*app\s*(\S+)",
        ],

        # 屏幕操作
        CommandType.SCREENSHOT: [
            r"(?:截|截图|screenshot|capture)(?:\s*(.+))?",
            r"(?:拍照|snapshot)",
        ],
        CommandType.OCR: [
            r"(?:ocr|识别|recognize)(?:\s*(.+))?",
        ],
        CommandType.FIND_TEXT: [
            r"(?:查找|find)\s*(.+)",
            r"(?:搜索|search)\s*(.+)",
        ],

        # 脚本
        CommandType.SCRIPT_RUN: [
            r"(?:执行|运行|run)\s*(?:脚本|script)?\s*(.+)",
        ],
    }

    def __init__(self):
        """初始化指令处理器"""
        self.compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[CommandType, List[re.Pattern]]:
        """编译正则表达式模式"""
        compiled = {}
        for cmd_type, patterns in self.PATTERNS.items():
            compiled[cmd_type] = [re.compile(p, re.IGNORECASE) for p in patterns]
        return compiled

    def parse(self, text: str) -> ParsedCommand:
        """
        解析自然语言指令

        Args:
            text: 用户输入的指令文本

        Returns:
            解析后的指令对象
        """
        text = text.strip()
        if not text:
            return ParsedCommand(
                command_type=CommandType.UNKNOWN,
                params={},
                original_text=text,
                confidence=0.0
            )

        # 尝试匹配每种指令类型
        for cmd_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                match = pattern.match(text)
                if match:
                    params = self._extract_params(cmd_type, match, text)
                    return ParsedCommand(
                        command_type=cmd_type,
                        params=params,
                        original_text=text,
                        confidence=1.0
                    )

        # 未匹配到任何指令
        return ParsedCommand(
            command_type=CommandType.UNKNOWN,
            params={},
            original_text=text,
            confidence=0.0
        )

    def _extract_params(
        self,
        cmd_type: CommandType,
        match: re.Match,
        text: str
    ) -> Dict[str, Any]:
        """
        提取参数

        Args:
            cmd_type: 指令类型
            match: 正则匹配结果
            text: 原始文本

        Returns:
            参数字典
        """
        groups = match.groups()

        params = {}

        if cmd_type == CommandType.DEVICE_CONNECT:
            params["device_id"] = groups[0] if groups else None

        elif cmd_type == CommandType.DEVICE_DISCONNECT:
            params["device_id"] = groups[0] if groups else None

        elif cmd_type == CommandType.CLICK:
            params["target"] = groups[0] if groups else text

        elif cmd_type == CommandType.SWIPE:
            if len(groups) >= 2:
                params["start"] = groups[0]
                params["end"] = groups[1]
                params["duration"] = int(groups[2]) if len(groups) > 2 and groups[2] else 500

        elif cmd_type == CommandType.INPUT:
            params["text"] = groups[0] if groups else ""

        elif cmd_type == CommandType.KEY:
            params["key"] = groups[0] if groups else ""

        elif cmd_type == CommandType.APP:
            if len(groups) >= 1:
                package = groups[0]
                # 判断是启动还是停止
                if any(word in text.lower() for word in ["打开", "启动", "open", "start"]):
                    params["action"] = "start"
                else:
                    params["action"] = "stop"
                params["package_name"] = package

        elif cmd_type == CommandType.SCREENSHOT:
            params["save_path"] = groups[0] if groups else None

        elif cmd_type == CommandType.FIND_TEXT:
            params["text"] = groups[0] if groups else ""

        elif cmd_type == CommandType.SCRIPT_RUN:
            params["script"] = groups[0] if groups else ""

        return params

    def to_api_request(self, parsed: ParsedCommand) -> Tuple[str, Dict]:
        """
        将解析后的指令转换为API请求

        Args:
            parsed: 解析后的指令

        Returns:
            (API端点, 请求体)
        """
        endpoint_map = {
            CommandType.DEVICE_LIST: "/api/phone-control/v1/device/list",
            CommandType.DEVICE_CONNECT: "/api/phone-control/v1/device/connect",
            CommandType.DEVICE_DISCONNECT: "/api/phone-control/v1/device/disconnect",
            CommandType.CLICK: "/api/phone-control/v1/control/click",
            CommandType.SWIPE: "/api/phone-control/v1/control/swipe",
            CommandType.INPUT: "/api/phone-control/v1/control/input",
            CommandType.KEY: "/api/phone-control/v1/control/key",
            CommandType.APP: "/api/phone-control/v1/control/app",
            CommandType.SCREENSHOT: "/api/phone-control/v1/screen/screenshot",
            CommandType.SCRIPT_RUN: "/api/phone-control/v1/script/run",
        }

        endpoint = endpoint_map.get(parsed.command_type, "")
        body = parsed.params

        return endpoint, body


# 便捷函数
def get_command_handler() -> CommandHandler:
    """获取指令处理器实例"""
    return CommandHandler()


def parse_command(text: str) -> ParsedCommand:
    """便捷函数：解析指令"""
    handler = get_command_handler()
    return handler.parse(text)


if __name__ == "__main__":
    # 测试指令解析
    handler = CommandHandler()

    test_commands = [
        "手机列表",
        "连接手机 192.168.1.100:5555",
        "点击 500,1000",
        "点击 设置",
        "滑动 100,500 100,1500 800",
        "输入 Hello World",
        "按键 back",
        "打开App com.example.app",
        "截屏",
        "执行脚本 [{"action": "click", "params": {"target": "500,1000"}}]"
    ]

    print("=== 指令解析测试 ===\n")
    for cmd in test_commands:
        result = handler.parse(cmd)
        endpoint, body = handler.to_api_request(result)
        print(f"输入: {cmd}")
        print(f"类型: {result.command_type.value}")
        print(f"参数: {result.params}")
        print(f"API: {endpoint}")
        print(f"置信度: {result.confidence}")
        print("-" * 50)
