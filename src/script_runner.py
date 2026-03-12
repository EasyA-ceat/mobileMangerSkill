"""
脚本执行引擎
解析和执行JSON格式的自动化操作脚本
"""

import json
import time
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

from .device_manager import DeviceManager
from .adb_client import ADBClient, Point, get_adb_client
from .screen import ScreenController, get_screen_controller


class ActionType(Enum):
    """动作类型枚举"""
    CLICK = "click"
    SWIPE = "swipe"
    INPUT = "input"
    KEY = "key"
    SLEEP = "sleep"
    APP = "app"
    SCREENSHOT = "screenshot"
    OCR = "ocr"
    FIND_TEXT = "find_text"
    IF = "if"
    WHILE = "while"


@dataclass
class ActionResult:
    """动作执行结果"""
    success: bool
    action_type: str
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


class ScriptRunner:
    """
    脚本执行引擎
    解析和执行JSON格式的操作脚本
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        device_id: Optional[str] = None
    ):
        """
        初始化脚本执行引擎

        Args:
            device_manager: 设备管理器实例
            device_id: 默认设备ID
        """
        self.device_manager = device_manager
        self.device_id = device_id
        self.adb_client = get_adb_client(device_manager, device_id)
        self.screen_controller = get_screen_controller(device_manager)

        # 执行统计
        self.execution_history: List[ActionResult] = []
        self.variables: Dict[str, Any] = {}  # 变量存储

    def validate_script(self, script: Union[str, List[Dict]]) -> Tuple[bool, str]:
        """
        验证脚本格式是否正确

        Args:
            script: JSON字符串或动作列表

        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 如果是字符串，先解析JSON
            if isinstance(script, str):
                actions = json.loads(script)
            else:
                actions = script

            # 检查是否是列表
            if not isinstance(actions, list):
                return False, "脚本必须是动作列表"

            # 检查每个动作的格式
            for i, action in enumerate(actions):
                if not isinstance(action, dict):
                    return False, f"第{i+1}个动作必须是对象"

                if "action" not in action:
                    return False, f"第{i+1}个动作缺少'action'字段"

                action_type = action["action"]
                if action_type not in [t.value for t in ActionType]:
                    return False, f"第{i+1}个动作类型'{action_type}'无效"

                # 检查参数
                if "params" not in action:
                    return False, f"第{i+1}个动作缺少'params'字段"

            return True, "脚本格式有效"

        except json.JSONDecodeError as e:
            return False, f"JSON解析错误: {e}"
        except Exception as e:
            return False, f"验证错误: {e}"

    def execute_script(
        self,
        script: Union[str, List[Dict]],
        device_id: Optional[str] = None
    ) -> List[ActionResult]:
        """
        执行脚本

        Args:
            script: JSON字符串或动作列表
            device_id: 设备ID(覆盖默认设备)

        Returns:
            执行结果列表
        """
        # 验证脚本
        is_valid, message = self.validate_script(script)
        if not is_valid:
            return [ActionResult(
                success=False,
                action_type="validate",
                message=message
            )]

        # 解析脚本
        if isinstance(script, str):
            actions = json.loads(script)
        else:
            actions = script

        # 设置设备ID
        current_device = device_id or self.device_id

        # 清空历史
        self.execution_history = []

        # 执行每个动作
        for action in actions:
            result = self._execute_action(action, current_device)
            self.execution_history.append(result)

            # 如果动作失败且设置了"stop_on_error"，则停止执行
            if not result.success and action.get("stop_on_error", True):
                break

        return self.execution_history

    def _execute_action(
        self,
        action: Dict[str, Any],
        device_id: Optional[str] = None
    ) -> ActionResult:
        """
        执行单个动作

        Args:
            action: 动作定义
            device_id: 设备ID

        Returns:
            执行结果
        """
        start_time = time.time()
        action_type = action.get("action", "")
        params = action.get("params", {})

        try:
            # 根据动作类型执行
            if action_type == ActionType.CLICK.value:
                return self._execute_click(params, device_id, start_time)

            elif action_type == ActionType.SWIPE.value:
                return self._execute_swipe(params, device_id, start_time)

            elif action_type == ActionType.INPUT.value:
                return self._execute_input(params, device_id, start_time)

            elif action_type == ActionType.KEY.value:
                return self._execute_key(params, device_id, start_time)

            elif action_type == ActionType.SLEEP.value:
                return self._execute_sleep(params, start_time)

            elif action_type == ActionType.APP.value:
                return self._execute_app(params, device_id, start_time)

            elif action_type == ActionType.SCREENSHOT.value:
                return self._execute_screenshot(params, device_id, start_time)

            elif action_type == ActionType.OCR.value:
                return self._execute_ocr(params, device_id, start_time)

            elif action_type == ActionType.FIND_TEXT.value:
                return self._execute_find_text(params, device_id, start_time)

            else:
                return ActionResult(
                    success=False,
                    action_type=action_type,
                    message=f"未知的动作类型: {action_type}",
                    execution_time=time.time() - start_time
                )

        except Exception as e:
            return ActionResult(
                success=False,
                action_type=action_type,
                message=f"执行出错: {str(e)}",
                execution_time=time.time() - start_time
            )

    def _execute_click(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行点击动作"""
        target = params.get("target", "")

        if not target:
            return ActionResult(
                success=False,
                action_type=ActionType.CLICK.value,
                message="缺少target参数",
                execution_time=time.time() - start_time
            )

        # 判断是坐标还是文字
        if re.match(r"^\d+,\d+$", target.replace(" ", "")):
            # 坐标点击
            x, y = map(int, target.replace(" ", "").split(","))
            success = self.adb_client.click(x, y, device_id)
            if success:
                return ActionResult(
                    success=True,
                    action_type=ActionType.CLICK.value,
                    message=f"点击坐标 ({x}, {y}) 成功",
                    data={"x": x, "y": y},
                    execution_time=time.time() - start_time
                )
            else:
                return ActionResult(
                    success=False,
                    action_type=ActionType.CLICK.value,
                    message=f"点击坐标 ({x}, {y}) 失败",
                    execution_time=time.time() - start_time
                )
        else:
            # 文字点击
            success = self.screen_controller.click_by_text(target, device_id)
            if success:
                return ActionResult(
                    success=True,
                    action_type=ActionType.CLICK.value,
                    message=f"点击文字 '{target}' 成功",
                    data={"text": target},
                    execution_time=time.time() - start_time
                )
            else:
                return ActionResult(
                    success=False,
                    action_type=ActionType.CLICK.value,
                    message=f"未找到文字 '{target}' 或点击失败",
                    execution_time=time.time() - start_time
                )

    def _execute_swipe(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行滑动手势"""
        start = params.get("start", "")
        end = params.get("end", "")
        duration = params.get("duration", 500)

        if not start or not end:
            return ActionResult(
                success=False,
                action_type=ActionType.SWIPE.value,
                message="缺少start或end参数",
                execution_time=time.time() - start_time
            )

        try:
            start_point = Point.from_string(start)
            end_point = Point.from_string(end)
        except ValueError as e:
            return ActionResult(
                success=False,
                action_type=ActionType.SWIPE.value,
                message=f"坐标格式错误: {e}",
                execution_time=time.time() - start_time
            )

        success = self.adb_client.swipe(
            start_point.x, start_point.y,
            end_point.x, end_point.y,
            duration, device_id
        )

        if success:
            return ActionResult(
                success=True,
                action_type=ActionType.SWIPE.value,
                message=f"滑动从 ({start_point.x}, {start_point.y}) 到 ({end_point.x}, {end_point.y}) 成功",
                data={
                    "start": {"x": start_point.x, "y": start_point.y},
                    "end": {"x": end_point.x, "y": end_point.y},
                    "duration": duration
                },
                execution_time=time.time() - start_time
            )
        else:
            return ActionResult(
                success=False,
                action_type=ActionType.SWIPE.value,
                message="滑动失败",
                execution_time=time.time() - start_time
            )

    def _execute_input(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行输入文字动作"""
        text = params.get("text", "")

        if not text:
            return ActionResult(
                success=False,
                action_type=ActionType.INPUT.value,
                message="缺少text参数",
                execution_time=time.time() - start_time
            )

        success = self.adb_client.input_text(text, device_id)

        if success:
            return ActionResult(
                success=True,
                action_type=ActionType.INPUT.value,
                message=f"输入文字 '{text}' 成功",
                data={"text": text},
                execution_time=time.time() - start_time
            )
        else:
            return ActionResult(
                success=False,
                action_type=ActionType.INPUT.value,
                message=f"输入文字 '{text}' 失败",
                execution_time=time.time() - start_time
            )

    def _execute_key(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行按键动作"""
        key = params.get("key", "")

        if not key:
            return ActionResult(
                success=False,
                action_type=ActionType.KEY.value,
                message="缺少key参数",
                execution_time=time.time() - start_time
            )

        success = self.adb_client.press_key(key, device_id)

        if success:
            return ActionResult(
                success=True,
                action_type=ActionType.KEY.value,
                message=f"按键 '{key}' 成功",
                data={"key": key},
                execution_time=time.time() - start_time
            )
        else:
            return ActionResult(
                success=False,
                action_type=ActionType.KEY.value,
                message=f"按键 '{key}' 失败",
                execution_time=time.time() - start_time
            )

    def _execute_sleep(
        self,
        params: Dict[str, Any],
        start_time: float
    ) -> ActionResult:
        """执行等待动作"""
        seconds = params.get("seconds", 1)

        try:
            time.sleep(seconds)
            return ActionResult(
                success=True,
                action_type=ActionType.SLEEP.value,
                message=f"等待 {seconds} 秒完成",
                data={"seconds": seconds},
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.SLEEP.value,
                message=f"等待出错: {e}",
                execution_time=time.time() - start_time
            )

    def _execute_app(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行应用管理动作"""
        action = params.get("action", "")
        package = params.get("package", "")

        if not action or not package:
            return ActionResult(
                success=False,
                action_type=ActionType.APP.value,
                message="缺少action或package参数",
                execution_time=time.time() - start_time
            )

        if action == "start":
            success = self.adb_client.start_app(package, device_id=device_id)
            if success:
                return ActionResult(
                    success=True,
                    action_type=ActionType.APP.value,
                    message=f"启动应用 '{package}' 成功",
                    data={"package": package, "action": action},
                    execution_time=time.time() - start_time
                )
            else:
                return ActionResult(
                    success=False,
                    action_type=ActionType.APP.value,
                    message=f"启动应用 '{package}' 失败",
                    execution_time=time.time() - start_time
                )

        elif action == "stop":
            success = self.adb_client.stop_app(package, device_id)
            if success:
                return ActionResult(
                    success=True,
                    action_type=ActionType.APP.value,
                    message=f"停止应用 '{package}' 成功",
                    data={"package": package, "action": action},
                    execution_time=time.time() - start_time
                )
            else:
                return ActionResult(
                    success=False,
                    action_type=ActionType.APP.value,
                    message=f"停止应用 '{package}' 失败",
                    execution_time=time.time() - start_time
                )

        else:
            return ActionResult(
                success=False,
                action_type=ActionType.APP.value,
                message=f"未知的应用操作: {action}",
                execution_time=time.time() - start_time
            )

    def _execute_screenshot(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行截图动作"""
        save_path = params.get("save_path", None)

        image = self.screen_controller.screenshot(device_id, save_path)

        if image is not None:
            return ActionResult(
                success=True,
                action_type=ActionType.SCREENSHOT.value,
                message="截图成功",
                data={
                    "save_path": save_path,
                    "size": {
                        "width": image.shape[1],
                        "height": image.shape[0]
                    }
                },
                execution_time=time.time() - start_time
            )
        else:
            return ActionResult(
                success=False,
                action_type=ActionType.SCREENSHOT.value,
                message="截图失败",
                execution_time=time.time() - start_time
            )

    def _execute_ocr(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行OCR识别动作"""
        results = self.screen_controller.ocr_text(device_id)

        texts = [r.text for r in results]

        return ActionResult(
            success=True,
            action_type=ActionType.OCR.value,
            message=f"OCR识别完成，共识别 {len(results)} 个文字区域",
            data={
                "texts": texts,
                "matches": [
                    {
                        "text": r.text,
                        "x": r.x,
                        "y": r.y,
                        "width": r.width,
                        "height": r.height,
                        "confidence": r.confidence
                    }
                    for r in results
                ]
            },
            execution_time=time.time() - start_time
        )

    def _execute_find_text(
        self,
        params: Dict[str, Any],
        device_id: Optional[str],
        start_time: float
    ) -> ActionResult:
        """执行查找文字动作"""
        text = params.get("text", "")
        partial_match = params.get("partial_match", True)
        click = params.get("click", False)

        if not text:
            return ActionResult(
                success=False,
                action_type=ActionType.FIND_TEXT.value,
                message="缺少text参数",
                execution_time=time.time() - start_time
            )

        match = self.screen_controller.find_text_position(
            text, device_id, partial_match=partial_match
        )

        if match:
            result_data = {
                "found": True,
                "text": match.text,
                "position": {
                    "x": match.x,
                    "y": match.y,
                    "width": match.width,
                    "height": match.height
                },
                "center": {
                    "x": match.center[0],
                    "y": match.center[1]
                },
                "confidence": match.confidence
            }

            # 如果需要点击
            if click:
                click_success = self.screen_controller.click_by_text(
                    text, device_id, partial_match
                )
                result_data["clicked"] = click_success

            return ActionResult(
                success=True,
                action_type=ActionType.FIND_TEXT.value,
                message=f"找到文字 '{match.text}'",
                data=result_data,
                execution_time=time.time() - start_time
            )
        else:
            return ActionResult(
                success=False,
                action_type=ActionType.FIND_TEXT.value,
                message=f"未找到文字 '{text}'",
                data={"found": False, "text": text},
                execution_time=time.time() - start_time
            )

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要

        Returns:
            执行统计信息
        """
        total = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        failed = total - successful
        total_time = sum(r.execution_time for r in self.execution_history)

        return {
            "total_actions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "total_execution_time": total_time,
            "average_execution_time": total_time / total if total > 0 else 0
        }


def create_script_from_actions(actions: List[Dict[str, Any]]) -> str:
    """
    从动作列表创建JSON脚本

    Args:
        actions: 动作列表

    Returns:
        JSON格式的脚本字符串
    """
    return json.dumps(actions, ensure_ascii=False, indent=2)


def get_example_script() -> str:
    """
    获取示例脚本

    Returns:
        示例脚本JSON字符串
    """
    example = [
        {
            "action": "key",
            "params": {"key": "home"},
            "description": "回到主页"
        },
        {
            "action": "sleep",
            "params": {"seconds": 1}
        },
        {
            "action": "click",
            "params": {"target": "设置"},
            "description": "点击设置"
        },
        {
            "action": "sleep",
            "params": {"seconds": 2}
        },
        {
            "action": "swipe",
            "params": {
                "start": "500,1500",
                "end": "500,500",
                "duration": 500
            },
            "description": "向上滑动"
        },
        {
            "action": "screenshot",
            "params": {"save_path": "/tmp/result.png"}
        }
    ]

    return json.dumps(example, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 简单测试
    from device_manager import get_device_manager

    manager = get_device_manager()
    runner = ScriptRunner(manager)

    # 验证示例脚本
    example_script = get_example_script()
    is_valid, message = runner.validate_script(example_script)
    print(f"脚本验证: {message}")

    if is_valid:
        print("\n示例脚本内容:")
        print(example_script)
