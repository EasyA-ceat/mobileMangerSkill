"""
脚本录制器模块
提供脚本录制功能，记录用户操作并生成JSON脚本
"""

import json
import time
import threading
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from .device_manager import DeviceManager, DeviceStatus
from .adb_client import ADBClient, get_adb_client


class RecordActionType(Enum):
    """录制动作类型"""
    CLICK = "click"
    SWIPE = "swipe"
    KEY = "key"
    INPUT = "input"
    SLEEP = "sleep"


@dataclass
class RecordedAction:
    """录制的动作"""
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "action": self.action,
            "params": self.params,
            "timestamp": self.timestamp
        }
        if self.description:
            result["description"] = self.description
        return result


class ScriptRecorder:
    """
    脚本录制器
    记录用户在设备上的操作，生成可回放的JSON脚本
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        device_id: Optional[str] = None
    ):
        """
        初始化脚本录制器

        Args:
            device_manager: 设备管理器实例
            device_id: 默认设备ID
        """
        self.device_manager = device_manager
        self.device_id = device_id
        self.adb_client = get_adb_client(device_manager, device_id)

        # 录制状态
        self._is_recording = False
        self._recorded_actions: List[RecordedAction] = []
        self._start_time: Optional[float] = None
        self._last_action_time: Optional[float] = None
        self._lock = threading.Lock()

        # 录制配置
        self.auto_sleep_threshold: float = 1.0  # 自动添加sleep的阈值(秒)
        self.min_sleep_duration: float = 0.5  # 最小sleep时长(秒)

    @property
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self._is_recording

    @property
    def recorded_actions(self) -> List[RecordedAction]:
        """已录制的动作列表"""
        with self._lock:
            return list(self._recorded_actions)

    def start_recording(self, device_id: Optional[str] = None) -> bool:
        """
        开始录制

        Args:
            device_id: 设备ID(覆盖默认设备)

        Returns:
            是否成功开始录制
        """
        with self._lock:
            if self._is_recording:
                return False

            # 设置设备
            current_device = device_id or self.device_id
            if current_device:
                self.adb_client = get_adb_client(self.device_manager, current_device)

            # 重置录制状态
            self._recorded_actions = []
            self._start_time = time.time()
            self._last_action_time = self._start_time
            self._is_recording = True

            return True

    def stop_recording(self) -> List[RecordedAction]:
        """
        停止录制

        Returns:
            已录制的动作列表
        """
        with self._lock:
            if not self._is_recording:
                return []

            self._is_recording = False
            return list(self._recorded_actions)

    def pause_recording(self) -> bool:
        """
        暂停录制

        Returns:
            是否成功暂停
        """
        with self._lock:
            if not self._is_recording:
                return False

            self._is_recording = False
            return True

    def resume_recording(self) -> bool:
        """
        恢复录制

        Returns:
            是否成功恢复
        """
        with self._lock:
            if self._is_recording:
                return False

            self._last_action_time = time.time()
            self._is_recording = True
            return True

    def _add_action(self, action: RecordedAction):
        """
        添加动作到录制列表

        Args:
            action: 要添加的动作
        """
        with self._lock:
            if not self._is_recording:
                return

            current_time = time.time()

            # 如果距离上次动作的时间超过阈值，自动添加sleep
            if self._last_action_time and self.auto_sleep_threshold > 0:
                time_diff = current_time - self._last_action_time
                if time_diff > self.auto_sleep_threshold:
                    sleep_duration = max(time_diff, self.min_sleep_duration)
                    sleep_action = RecordedAction(
                        action=RecordActionType.SLEEP.value,
                        params={"seconds": round(sleep_duration, 2)},
                        timestamp=current_time
                    )
                    self._recorded_actions.append(sleep_action)

            # 添加实际动作
            self._recorded_actions.append(action)
            self._last_action_time = current_time

    def record_click(self, x: int, y: int, description: Optional[str] = None) -> bool:
        """
        记录点击动作

        Args:
            x: X坐标
            y: Y坐标
            description: 动作描述

        Returns:
            是否成功记录
        """
        action = RecordedAction(
            action=RecordActionType.CLICK.value,
            params={"target": f"{x},{y}"},
            timestamp=time.time(),
            description=description
        )
        self._add_action(action)
        return True

    def record_swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: int = 300,
        description: Optional[str] = None
    ) -> bool:
        """
        记录滑动动作

        Args:
            start_x: 起始X坐标
            start_y: 起始Y坐标
            end_x: 结束X坐标
            end_y: 结束Y坐标
            duration: 滑动时长(毫秒)
            description: 动作描述

        Returns:
            是否成功记录
        """
        action = RecordedAction(
            action=RecordActionType.SWIPE.value,
            params={
                "start": f"{start_x},{start_y}",
                "end": f"{end_x},{end_y}",
                "duration": duration
            },
            timestamp=time.time(),
            description=description
        )
        self._add_action(action)
        return True

    def record_key(self, key: str, description: Optional[str] = None) -> bool:
        """
        记录按键动作

        Args:
            key: 按键名称
            description: 动作描述

        Returns:
            是否成功记录
        """
        action = RecordedAction(
            action=RecordActionType.KEY.value,
            params={"key": key},
            timestamp=time.time(),
            description=description
        )
        self._add_action(action)
        return True

    def record_input(self, text: str, description: Optional[str] = None) -> bool:
        """
        记录输入文字动作

        Args:
            text: 输入的文字
            description: 动作描述

        Returns:
            是否成功记录
        """
        action = RecordedAction(
            action=RecordActionType.INPUT.value,
            params={"text": text},
            timestamp=time.time(),
            description=description
        )
        self._add_action(action)
        return True

    def record_sleep(self, seconds: float, description: Optional[str] = None) -> bool:
        """
        记录等待动作

        Args:
            seconds: 等待秒数
            description: 动作描述

        Returns:
            是否成功记录
        """
        action = RecordedAction(
            action=RecordActionType.SLEEP.value,
            params={"seconds": seconds},
            timestamp=time.time(),
            description=description
        )
        self._add_action(action)
        return True

    def add_custom_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        description: Optional[str] = None
    ) -> bool:
        """
        添加自定义动作

        Args:
            action_type: 动作类型
            params: 动作参数
            description: 动作描述

        Returns:
            是否成功添加
        """
        action = RecordedAction(
            action=action_type,
            params=params,
            timestamp=time.time(),
            description=description
        )
        self._add_action(action)
        return True

    def get_script_json(self, include_timestamps: bool = False) -> str:
        """
        获取录制的脚本JSON

        Args:
            include_timestamps: 是否包含时间戳

        Returns:
            JSON格式的脚本字符串
        """
        with self._lock:
            actions = []
            for action in self._recorded_actions:
                action_dict = action.to_dict()
                if not include_timestamps:
                    action_dict.pop("timestamp", None)
                actions.append(action_dict)

        return json.dumps(actions, ensure_ascii=False, indent=2)

    def get_script_actions(self, include_timestamps: bool = False) -> List[Dict[str, Any]]:
        """
        获取录制的脚本动作列表

        Args:
            include_timestamps: 是否包含时间戳

        Returns:
            动作列表
        """
        with self._lock:
            actions = []
            for action in self._recorded_actions:
                action_dict = action.to_dict()
                if not include_timestamps:
                    action_dict.pop("timestamp", None)
                actions.append(action_dict)
            return actions

    def get_recording_status(self) -> Dict[str, Any]:
        """
        获取录制状态

        Returns:
            状态信息字典
        """
        with self._lock:
            duration = 0.0
            if self._start_time:
                duration = time.time() - self._start_time

            return {
                "is_recording": self._is_recording,
                "action_count": len(self._recorded_actions),
                "duration": round(duration, 2),
                "start_time": self._start_time
            }

    def clear_recording(self):
        """清除录制内容"""
        with self._lock:
            self._recorded_actions = []
            self._start_time = None
            self._last_action_time = None


# 便捷函数
def get_script_recorder(
    device_manager: DeviceManager,
    device_id: Optional[str] = None
) -> ScriptRecorder:
    """
    获取脚本录制器实例

    Args:
        device_manager: 设备管理器实例
        device_id: 默认设备ID

    Returns:
        ScriptRecorder实例
    """
    return ScriptRecorder(device_manager, device_id)
