"""
ADB控制客户端
封装所有ADB操作，提供统一的设备控制接口
"""

import re
import time
import subprocess
import shlex
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
from .device_manager import DeviceManager, Device, DeviceStatus


@dataclass
class Point:
    """坐标点"""
    x: int
    y: int

    def __str__(self):
        return f"{self.x},{self.y}"

    @classmethod
    def from_string(cls, s: str) -> "Point":
        """从字符串解析坐标"""
        parts = s.replace(" ", "").split(",")
        if len(parts) != 2:
            raise ValueError(f"无效的坐标格式: {s}")
        return cls(int(parts[0]), int(parts[1]))


@dataclass
class SwipeGesture:
    """滑动手势"""
    start: Point
    end: Point
    duration: int = 300  # 毫秒


class ADBClient:
    """
    ADB控制客户端
    封装所有与ADB设备的交互操作
    """

    # 按键映射表
    KEY_CODES = {
        # 导航键
        "home": "KEYCODE_HOME",
        "back": "KEYCODE_BACK",
        "menu": "KEYCODE_MENU",
        "app_switch": "KEYCODE_APP_SWITCH",
        # 电源键
        "power": "KEYCODE_POWER",
        "wake": "KEYCODE_WAKEUP",
        "sleep": "KEYCODE_SLEEP",
        # 音量键
        "volume_up": "KEYCODE_VOLUME_UP",
        "volume_down": "KEYCODE_VOLUME_DOWN",
        "mute": "KEYCODE_VOLUME_MUTE",
        # 媒体键
        "play_pause": "KEYCODE_MEDIA_PLAY_PAUSE",
        "stop": "KEYCODE_MEDIA_STOP",
        "next": "KEYCODE_MEDIA_NEXT",
        "previous": "KEYCODE_MEDIA_PREVIOUS",
        # 方向键
        "up": "KEYCODE_DPAD_UP",
        "down": "KEYCODE_DPAD_DOWN",
        "left": "KEYCODE_DPAD_LEFT",
        "right": "KEYCODE_DPAD_RIGHT",
        "center": "KEYCODE_DPAD_CENTER",
        # 功能键
        "search": "KEYCODE_SEARCH",
        "camera": "KEYCODE_CAMERA",
        "call": "KEYCODE_CALL",
        "end_call": "KEYCODE_ENDCALL",
        "del": "KEYCODE_DEL",
        "enter": "KEYCODE_ENTER",
        "space": "KEYCODE_SPACE",
        "tab": "KEYCODE_TAB",
        "escape": "KEYCODE_ESCAPE",
        "caps_lock": "KEYCODE_CAPS_LOCK",
        "scroll_lock": "KEYCODE_SCROLL_LOCK",
        "num_lock": "KEYCODE_NUM_LOCK",
        "break": "KEYCODE_BREAK",
        "sysrq": "KEYCODE_SYSRQ",
    }

    def __init__(self, device_manager: DeviceManager, device_id: Optional[str] = None):
        """
        初始化ADB客户端

        Args:
            device_manager: 设备管理器实例
            device_id: 默认设备ID，如果不指定则使用第一个可用设备
        """
        self.device_manager = device_manager
        self.default_device_id = device_id

    def _get_device_id(self, device_id: Optional[str] = None) -> str:
        """
        获取要操作的设备ID

        Args:
            device_id: 指定的设备ID

        Returns:
            设备ID

        Raises:
            ValueError: 没有可用的设备
        """
        if device_id:
            return device_id
        if self.default_device_id:
            return self.default_device_id

        # 获取第一个已连接的设备
        devices = self.device_manager.list_devices(refresh=True)
        for device in devices:
            if device.status == DeviceStatus.CONNECTED:
                return device.device_id

        raise ValueError("没有可用的设备，请先连接设备")

    def _run_shell(self, command_args: List[str], device_id: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        在设备上执行shell命令（安全版本，使用列表参数避免注入）

        Args:
            command_args: shell命令参数列表
            device_id: 设备ID

        Returns:
            (success, stdout, stderr)
        """
        try:
            device_id = self._get_device_id(device_id)
            cmd = ["adb", "-s", device_id, "shell"] + command_args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                shell=False
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)

    def _validate_coordinate(self, value: int) -> int:
        """验证坐标值"""
        if not isinstance(value, int):
            raise ValueError("坐标必须是整数")
        if value < 0 or value > 10000:
            raise ValueError("坐标值超出合理范围")
        return value

    def click(self, x: int, y: int, device_id: Optional[str] = None) -> bool:
        """
        在指定坐标点击

        Args:
            x: X坐标
            y: Y坐标
            device_id: 设备ID

        Returns:
            是否成功
        """
        try:
            x = self._validate_coordinate(x)
            y = self._validate_coordinate(y)
            success, _, stderr = self._run_shell(["input", "tap", str(x), str(y)], device_id)
            if not success:
                print(f"点击失败: {stderr}")
            return success
        except ValueError as e:
            print(f"参数验证失败: {e}")
            return False

    def click_point(self, point: Union[Point, str], device_id: Optional[str] = None) -> bool:
        """
        在指定坐标点击（支持Point对象或字符串）

        Args:
            point: 坐标点(Point对象或"x,y"格式的字符串)
            device_id: 设备ID

        Returns:
            是否成功
        """
        if isinstance(point, str):
            point = Point.from_string(point)
        return self.click(point.x, point.y, device_id)

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: int = 300,
        device_id: Optional[str] = None
    ) -> bool:
        """
        滑动操作

        Args:
            start_x: 起始X坐标
            start_y: 起始Y坐标
            end_x: 结束X坐标
            end_y: 结束Y坐标
            duration: 滑动持续时间(毫秒)
            device_id: 设备ID

        Returns:
            是否成功
        """
        try:
            start_x = self._validate_coordinate(start_x)
            start_y = self._validate_coordinate(start_y)
            end_x = self._validate_coordinate(end_x)
            end_y = self._validate_coordinate(end_y)
            duration = max(100, min(5000, duration))
            
            success, _, stderr = self._run_shell(
                ["input", "swipe", str(start_x), str(start_y), str(end_x), str(end_y), str(duration)],
                device_id
            )
            if not success:
                print(f"滑动失败: {stderr}")
            return success
        except ValueError as e:
            print(f"参数验证失败: {e}")
            return False

    def swipe_gesture(self, gesture: SwipeGesture, device_id: Optional[str] = None) -> bool:
        """
        使用SwipeGesture对象进行滑动

        Args:
            gesture: 滑动手势
            device_id: 设备ID

        Returns:
            是否成功
        """
        return self.swipe(
            gesture.start.x, gesture.start.y,
            gesture.end.x, gesture.end.y,
            gesture.duration,
            device_id
        )

    def input_text(self, text: str, device_id: Optional[str] = None) -> bool:
        """
        输入文字

        Args:
            text: 要输入的文字
            device_id: 设备ID

        Returns:
            是否成功
        """
        try:
            # 限制输入长度
            if len(text) > 1000:
                print("输入文字过长")
                return False
                
            # 使用ADB的input text命令，注意文字中的空格需要特殊处理
            # ADB input text对空格处理特殊，我们可以通过多次调用或使用其他方法
            # 这里使用简单的空格替换为%s（ADB的方式）
            safe_text = text.replace(" ", "%s")
            
            success, _, stderr = self._run_shell(
                ["input", "text", safe_text],
                device_id
            )
            if not success:
                print(f"输入文字失败: {stderr}")
            return success
        except Exception as e:
            print(f"输入文字异常: {e}")
            return False

    def press_key(self, key: str, device_id: Optional[str] = None) -> bool:
        """
        按下按键

        Args:
            key: 按键名称或按键码
            device_id: 设备ID

        Returns:
            是否成功
        """
        try:
            # 验证key参数
            if not key or len(key) > 100:
                print("无效的按键参数")
                return False
                
            # 检查是否是预定义的按键名称
            key_code = self.KEY_CODES.get(key.lower(), key)
            
            # 确保key_code只包含字母、数字和下划线
            if not re.match(r'^[A-Za-z0-9_]+$', key_code):
                print("按键代码格式无效")
                return False

            success, _, stderr = self._run_shell(
                ["input", "keyevent", key_code],
                device_id
            )
            if not success:
                print(f"按键失败: {stderr}")
            return success
        except Exception as e:
            print(f"按键操作异常: {e}")
            return False

    def start_app(self, package_name: str, activity: Optional[str] = None, device_id: Optional[str] = None) -> bool:
        """
        启动应用

        Args:
            package_name: 应用包名
            activity: 启动的Activity(可选，默认启动主Activity)
            device_id: 设备ID

        Returns:
            是否成功
        """
        try:
            # 验证包名格式
            if not re.match(r'^[a-zA-Z0-9_.]+$', package_name):
                print("无效的包名格式")
                return False
                
            if activity:
                if not re.match(r'^[a-zA-Z0-9_.]+$', activity):
                    print("无效的Activity格式")
                    return False
                cmd_args = ["am", "start", "-n", f"{package_name}/{activity}"]
            else:
                cmd_args = ["monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"]

            success, stdout, stderr = self._run_shell(cmd_args, device_id)
            if not success:
                print(f"启动应用失败: {stderr}")
                return False

            # 检查是否有错误信息
            if "Error" in stdout or "Exception" in stdout:
                print(f"启动应用出错: {stdout}")
                return False

            return True
        except Exception as e:
            print(f"启动应用异常: {e}")
            return False

    def stop_app(self, package_name: str, device_id: Optional[str] = None) -> bool:
        """
        停止应用

        Args:
            package_name: 应用包名
            device_id: 设备ID

        Returns:
            是否成功
        """
        try:
            # 验证包名格式
            if not re.match(r'^[a-zA-Z0-9_.]+$', package_name):
                print("无效的包名格式")
                return False
                
            success, _, stderr = self._run_shell(
                ["am", "force-stop", package_name],
                device_id
            )
            if not success:
                print(f"停止应用失败: {stderr}")
            return success
        except Exception as e:
            print(f"停止应用异常: {e}")
            return False

    def list_apps(self, system_apps: bool = False, device_id: Optional[str] = None) -> List[Dict]:
        """
        获取已安装应用列表

        Args:
            system_apps: 是否包含系统应用
            device_id: 设备ID

        Returns:
            应用列表，每个应用包含包名和名称
        """
        # 获取第三方应用
        success, stdout, stderr = self._run_shell(
            ["pm", "list", "packages", "-3"],
            device_id
        )

        apps = []
        if success:
            for line in stdout.strip().split("\n"):
                match = re.search(r"package:(.+)", line)
                if match:
                    package = match.group(1)
                    apps.append({
                        "package": package,
                        "name": package,  # 名称需要额外获取
                        "is_system": False
                    })

        # 如果需要系统应用
        if system_apps:
            success, stdout, stderr = self._run_shell(
                ["pm", "list", "packages", "-s"],
                device_id
            )
            if success:
                for line in stdout.strip().split("\n"):
                    match = re.search(r"package:(.+)", line)
                    if match:
                        package = match.group(1)
                        # 检查是否已存在
                        if not any(a["package"] == package for a in apps):
                            apps.append({
                                "package": package,
                                "name": package,
                                "is_system": True
                            })

        return apps

    def get_screen_size(self, device_id: Optional[str] = None) -> Optional[Tuple[int, int]]:
        """
        获取屏幕尺寸

        Args:
            device_id: 设备ID

        Returns:
            (宽度, 高度) 或 None
        """
        success, stdout, stderr = self._run_shell(
            ["wm", "size"],
            device_id
        )
        if not success:
            return None

        # 解析输出: Physical size: 1080x1920
        match = re.search(r"(\d+)x(\d+)", stdout)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return None

    def get_android_version(self, device_id: Optional[str] = None) -> Optional[str]:
        """
        获取Android版本

        Args:
            device_id: 设备ID

        Returns:
            Android版本号或None
        """
        success, stdout, stderr = self._run_shell(
            ["getprop", "ro.build.version.release"],
            device_id
        )
        if success:
            return stdout.strip()
        return None


# 便捷函数
def get_adb_client(device_manager: DeviceManager, device_id: Optional[str] = None) -> ADBClient:
    """
    获取ADB客户端实例

    Args:
        device_manager: 设备管理器实例
        device_id: 默认设备ID

    Returns:
        ADBClient实例
    """
    return ADBClient(device_manager, device_id)


if __name__ == "__main__":
    # 简单测试
    from device_manager import get_device_manager

    manager = get_device_manager()
    client = get_adb_client(manager)

    # 获取屏幕尺寸
    size = client.get_screen_size()
    if size:
        print(f"屏幕尺寸: {size[0]}x{size[1]}")

    # 获取Android版本
    version = client.get_android_version()
    if version:
        print(f"Android版本: {version}")
