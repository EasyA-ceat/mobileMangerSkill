"""
设备管理模块
负责扫描、连接、断开ADB设备，以及管理设备状态
"""

import subprocess
import re
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading


class DeviceStatus(Enum):
    """设备状态枚举"""
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    RECOVERY = "recovery"
    BOOTLOADER = "bootloader"


@dataclass
class Device:
    """设备数据类"""
    device_id: str
    name: str = ""
    status: DeviceStatus = DeviceStatus.UNKNOWN
    device_type: str = "unknown"  # usb, network
    properties: Dict = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "device_id": self.device_id,
            "name": self.name or self.device_id,
            "status": self.status.value,
            "type": self.device_type,
            "properties": self.properties,
            "last_seen": self.last_seen
        }


class DeviceManager:
    """
    设备管理器
    负责管理所有ADB设备的连接、断开和状态监控
    """

    def __init__(self, adb_path: str = "adb"):
        """
        初始化设备管理器

        Args:
            adb_path: ADB可执行文件路径，默认使用系统PATH中的adb
        """
        self.adb_path = adb_path
        self._devices: Dict[str, Device] = {}
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def _run_adb_command(self, args: List[str], timeout: int = 30) -> Tuple[bool, str, str]:
        """
        运行ADB命令

        Args:
            args: ADB命令参数列表
            timeout: 超时时间(秒)

        Returns:
            (success, stdout, stderr)
        """
        try:
            cmd = [self.adb_path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timeout"
        except Exception as e:
            return False, "", str(e)

    def _parse_device_line(self, line: str) -> Optional[Device]:
        """
        解析ADB设备列表中的一行

        Args:
            line: ADB devices输出的单行

        Returns:
            Device对象或None
        """
        parts = line.split()
        if len(parts) < 2:
            return None

        device_id = parts[0]
        status_str = parts[1].lower()

        # 确定设备类型
        if ":" in device_id:
            device_type = "network"
        else:
            device_type = "usb"

        # 解析状态
        status_map = {
            "device": DeviceStatus.CONNECTED,
            "offline": DeviceStatus.OFFLINE,
            "unauthorized": DeviceStatus.UNAUTHORIZED,
            "recovery": DeviceStatus.RECOVERY,
            "bootloader": DeviceStatus.BOOTLOADER,
        }
        status = status_map.get(status_str, DeviceStatus.UNKNOWN)

        # 尝试获取更多设备信息
        properties = {}
        if status == DeviceStatus.CONNECTED:
            success, stdout, _ = self._run_adb_command(
                ["-s", device_id, "shell", "getprop", "ro.product.model"]
            )
            if success:
                properties["model"] = stdout.strip()

        device = Device(
            device_id=device_id,
            name=properties.get("model", device_id),
            status=status,
            device_type=device_type,
            properties=properties
        )

        return device

    def list_devices(self, refresh: bool = True) -> List[Device]:
        """
        获取设备列表

        Args:
            refresh: 是否刷新设备列表

        Returns:
            设备列表
        """
        if refresh:
            success, stdout, stderr = self._run_adb_command(["devices", "-l"])

            if not success:
                print(f"获取设备列表失败: {stderr}")
                return list(self._devices.values())

            with self._lock:
                # 标记所有设备为待更新
                for device in self._devices.values():
                    device.last_seen = 0

                # 解析设备列表
                for line in stdout.strip().split("\n")[1:]:  # 跳过标题行
                    device = self._parse_device_line(line)
                    if device:
                        device.last_seen = time.time()
                        self._devices[device.device_id] = device

                # 清理长时间未见的设备
                current_time = time.time()
                expired_devices = [
                    did for did, d in self._devices.items()
                    if current_time - d.last_seen > 60  # 60秒未更新则移除
                ]
                for did in expired_devices:
                    del self._devices[did]

        with self._lock:
            return list(self._devices.values())

    def get_device(self, device_id: str) -> Optional[Device]:
        """
        获取指定设备

        Args:
            device_id: 设备ID

        Returns:
            Device对象或None
        """
        with self._lock:
            return self._devices.get(device_id)

    def connect_device(self, device_id: str, timeout: int = 30) -> Tuple[bool, str]:
        """
        连接设备

        Args:
            device_id: 设备ID (格式: IP:端口 或 序列号)
            timeout: 超时时间(秒)

        Returns:
            (是否成功, 消息)
        """
        # 如果是网络设备，先执行adb connect
        if ":" in device_id:
            success, stdout, stderr = self._run_adb_command(
                ["connect", device_id],
                timeout=timeout
            )
            if not success or "connected" not in stdout.lower():
                return False, f"连接失败: {stderr or stdout}"

        # 等待设备连接并授权
        success, stdout, stderr = self._run_adb_command(
            ["-s", device_id, "wait-for-device"],
            timeout=timeout
        )
        if not success:
            return False, f"等待设备超时: {stderr}"

        # 刷新设备列表
        self.list_devices(refresh=True)

        return True, "连接成功"

    def disconnect_device(self, device_id: str) -> Tuple[bool, str]:
        """
        断开设备连接

        Args:
            device_id: 设备ID

        Returns:
            (是否成功, 消息)
        """
        # 如果是网络设备，执行adb disconnect
        if ":" in device_id:
            success, stdout, stderr = self._run_adb_command(
                ["disconnect", device_id]
            )
            if not success:
                return False, f"断开失败: {stderr}"

        # 从设备列表中移除
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]

        return True, "断开成功"

    def start_monitor(self, interval: int = 5):
        """
        启动设备状态监控

        Args:
            interval: 检查间隔(秒)
        """
        if self._running:
            return

        self._running = True

        def monitor_loop():
            while self._running:
                self.list_devices(refresh=True)
                time.sleep(interval)

        self._monitor_thread = threading.Thread(target=monitor_loop)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def stop_monitor(self):
        """停止设备状态监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)

    def __enter__(self):
        """上下文管理器进入"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.stop_monitor()


# 便捷函数
def get_device_manager(adb_path: str = "adb") -> DeviceManager:
    """
    获取设备管理器实例

    Args:
        adb_path: ADB可执行文件路径

    Returns:
        DeviceManager实例
    """
    return DeviceManager(adb_path=adb_path)


if __name__ == "__main__":
    # 简单测试
    manager = get_device_manager()
    devices = manager.list_devices()
    print(f"发现 {len(devices)} 个设备:")
    for device in devices:
        print(f"  - {device.device_id} ({device.name}) - {device.status.value}")
