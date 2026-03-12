"""
Scrcpy客户端模块
提供屏幕镜像和控制功能
"""

import os
import re
import socket
import struct
import subprocess
import threading
import time
from typing import Optional, Tuple, List, Dict, Callable, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import numpy as np


class ScrcpyEventType(Enum):
    """Scrcpy事件类型"""
    KEY = 0
    TEXT = 1
    TOUCH = 2
    SCROLL = 3
    BACK_OR_SCREEN_ON = 4
    EXPAND_NOTIFICATION_PANEL = 5
    EXPAND_SETTINGS_PANEL = 6
    COLLAPSE_PANELS = 7
    GET_CLIPBOARD = 8
    SET_CLIPBOARD = 9
    SET_SCREEN_POWER_MODE = 10
    ROTATE_DEVICE = 11


@dataclass
class ScrcpyConfig:
    """Scrcpy配置"""
    max_size: int = 0  # 最大分辨率，0表示不限制
    bit_rate: int = 8000000  # 比特率
    max_fps: int = 0  # 最大帧率，0表示不限制
    orientation: int = 0  # 方向
    crop: Optional[str] = None  # 裁剪区域
    display_id: int = 0  # 显示ID
    show_touches: bool = False  # 显示触摸
    stay_awake: bool = True  # 保持唤醒


class ScrcpyClient:
    """
    Scrcpy客户端
    提供屏幕镜像和控制功能
    """

    def __init__(
        self,
        device_id: str,
        config: Optional[ScrcpyConfig] = None,
        scrcpy_path: str = "scrcpy"
    ):
        """
        初始化Scrcpy客户端

        Args:
            device_id: 设备ID
            config: Scrcpy配置
            scrcpy_path: scrcpy可执行文件路径
        """
        self.device_id = device_id
        self.config = config or ScrcpyConfig()
        self.scrcpy_path = scrcpy_path

        # 进程和连接
        self._process: Optional[subprocess.Popen] = None
        self._video_socket: Optional[socket.socket] = None
        self._control_socket: Optional[socket.socket] = None
        self._is_running = False
        self._lock = threading.Lock()

        # 视频流处理
        self._frame_callback: Optional[Callable[[np.ndarray], None]] = None
        self._video_thread: Optional[threading.Thread] = None
        self._current_frame: Optional[np.ndarray] = None

    def start(self, timeout: int = 30) -> bool:
        """
        启动Scrcpy连接

        Args:
            timeout: 超时时间(秒)

        Returns:
            是否成功
        """
        with self._lock:
            if self._is_running:
                return True

            try:
                # 启动scrcpy进程
                cmd = self._build_command()
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # 等待连接建立
                time.sleep(2)

                # 连接视频socket
                if not self._connect_video_socket(timeout):
                    self.stop()
                    return False

                # 连接控制socket
                if not self._connect_control_socket(timeout):
                    self.stop()
                    return False

                # 启动视频接收线程
                self._is_running = True
                self._video_thread = threading.Thread(target=self._video_loop)
                self._video_thread.daemon = True
                self._video_thread.start()

                return True

            except Exception as e:
                print(f"启动Scrcpy失败: {e}")
                self.stop()
                return False

    def _build_command(self) -> List[str]:
        """构建scrcpy命令"""
        cmd = [
            self.scrcpy_path,
            "-s", self.device_id,
            "--tunnel-forward",  # 使用本地转发
        ]

        # 添加配置参数
        if self.config.max_size > 0:
            cmd.extend(["--max-size", str(self.config.max_size)])

        if self.config.bit_rate > 0:
            cmd.extend(["--bit-rate", str(self.config.bit_rate)])

        if self.config.max_fps > 0:
            cmd.extend(["--max-fps", str(self.config.max_fps)])

        if self.config.crop:
            cmd.extend(["--crop", self.config.crop])

        if self.config.show_touches:
            cmd.append("--show-touches")

        if self.config.stay_awake:
            cmd.append("--stay-awake")

        # 不显示窗口，我们通过socket获取视频流
        cmd.append("--no-display")
        cmd.append("--record-format=raw")

        return cmd

    def _connect_video_socket(self, timeout: int) -> bool:
        """连接视频socket"""
        try:
            # Scrcpy默认使用27183端口
            self._video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._video_socket.settimeout(timeout)
            self._video_socket.connect(("localhost", 27183))

            # 接收设备信息头
            header = self._video_socket.recv(2)
            if len(header) < 2:
                return False

            return True

        except Exception as e:
            print(f"连接视频socket失败: {e}")
            return False

    def _connect_control_socket(self, timeout: int) -> bool:
        """连接控制socket"""
        try:
            # Scrcpy控制socket使用27184端口
            self._control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._control_socket.settimeout(timeout)
            self._control_socket.connect(("localhost", 27184))
            return True

        except Exception as e:
            print(f"连接控制socket失败: {e}")
            # 控制socket是可选的
            return True

    def _video_loop(self):
        """视频接收循环"""
        while self._is_running:
            try:
                # 读取帧数据(简化处理，实际需要解析h.264流)
                # 这里使用OpenCV直接读取作为替代方案
                pass

            except Exception as e:
                if self._is_running:
                    print(f"视频接收错误: {e}")
                break

    def stop(self):
        """停止Scrcpy连接"""
        with self._lock:
            self._is_running = False

            # 关闭socket
            if self._video_socket:
                try:
                    self._video_socket.close()
                except:
                    pass
                self._video_socket = None

            if self._control_socket:
                try:
                    self._control_socket.close()
                except:
                    pass
                self._control_socket = None

            # 终止进程
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except:
                    try:
                        self._process.kill()
                    except:
                        pass
                self._process = None

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._is_running

    def inject_event(self, event_type: ScrcpyEventType, data: bytes) -> bool:
        """
        注入控制事件

        Args:
            event_type: 事件类型
            data: 事件数据

        Returns:
            是否成功
        """
        if not self._control_socket:
            return False

        try:
            # 构建事件数据包
            packet = struct.pack("<B", event_type.value) + data
            self._control_socket.sendall(packet)
            return True
        except Exception as e:
            print(f"注入事件失败: {e}")
            return False

    def inject_key(self, keycode: int, action: int = 0, meta_state: int = 0) -> bool:
        """
        注入按键事件

        Args:
            keycode: 按键码
            action: 动作(0=按下, 1=抬起)
            meta_state: 元状态

        Returns:
            是否成功
        """
        data = struct.pack("<iiI", keycode, action, meta_state)
        return self.inject_event(ScrcpyEventType.KEY, data)

    def inject_text(self, text: str) -> bool:
        """
        注入文本事件

        Args:
            text: 要输入的文本

        Returns:
            是否成功
        """
        text_bytes = text.encode("utf-8")
        data = struct.pack("<i", len(text_bytes)) + text_bytes
        return self.inject_event(ScrcpyEventType.TEXT, data)

    def inject_touch(
        self,
        action: int,
        pointer_id: int,
        x: int,
        y: int,
        screen_width: int,
        screen_height: int,
        pressure: int = 0xFFFF,
        buttons_state: int = 0
    ) -> bool:
        """
        注入触摸事件

        Args:
            action: 动作类型
            pointer_id: 指针ID
            x: X坐标
            y: Y坐标
            screen_width: 屏幕宽度
            screen_height: 屏幕高度
            pressure: 压力值
            buttons_state: 按钮状态

        Returns:
            是否成功
        """
        # 将坐标转换为定点数格式
        x_fixed = int(x * 0x10000 / screen_width) if screen_width > 0 else 0
        y_fixed = int(y * 0x10000 / screen_height) if screen_height > 0 else 0

        data = struct.pack(
            "<BHHIiiHH",
            action,
            pointer_id,
            x_fixed >> 16,
            x_fixed & 0xFFFF,
            y_fixed >> 16,
            y_fixed & 0xFFFF,
            screen_width,
            screen_height
        )

        return self.inject_event(ScrcpyEventType.TOUCH, data)


# 便捷函数
def get_scrcpy_client(
    device_id: str,
    config: Optional[ScrcpyConfig] = None,
    scrcpy_path: str = "scrcpy"
) -> ScrcpyClient:
    """
    获取Scrcpy客户端实例

    Args:
        device_id: 设备ID
        config: Scrcpy配置
        scrcpy_path: scrcpy可执行文件路径

    Returns:
        ScrcpyClient实例
    """
    return ScrcpyClient(device_id, config, scrcpy_path)


if __name__ == "__main__":
    # 简单测试
    print("ScrcpyClient模块已加载")
    print("注意: ScrcpyClient需要在有实际设备连接时才能正常工作")
