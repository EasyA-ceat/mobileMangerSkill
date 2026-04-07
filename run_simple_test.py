
"""
简单测试脚本 - 验证核心模块功能
"""

import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("手机控制技能项目 - 简单测试")
print("=" * 60)

test_results = []

def test_passed(name):
    print(f"[✓] {name}")
    test_results.append((name, True))

def test_failed(name, error):
    print(f"[✗] {name} - {error}")
    test_results.append((name, False))

# ==================== 测试1: 导入测试 ====================
print("\n1. 模块导入测试")
print("-" * 40)
try:
    from src.device_manager import DeviceManager, Device, DeviceStatus, DeviceType
    test_passed("device_manager 模块导入")
except Exception as e:
    test_failed("device_manager 模块导入", str(e))

try:
    from src.adb_client import ADBClient, Point, SwipeGesture
    test_passed("adb_client 模块导入")
except Exception as e:
    test_failed("adb_client 模块导入", str(e))

try:
    from src.screen import TextMatch, ScreenController
    test_passed("screen 模块导入")
except Exception as e:
    test_failed("screen 模块导入", str(e))

try:
    from src.script_runner import ScriptRunner, ActionType, ActionResult
    test_passed("script_runner 模块导入")
except Exception as e:
    test_failed("script_runner 模块导入", str(e))

try:
    from src.command_handler import CommandHandler, CommandType, ParsedCommand
    test_passed("command_handler 模块导入")
except Exception as e:
    test_failed("command_handler 模块导入", str(e))

# ==================== 测试2: 基础功能测试 ====================
print("\n2. 基础功能测试")
print("-" * 40)

try:
    from src.device_manager import DeviceManager
    manager = DeviceManager(adb_path="adb")
    test_passed("DeviceManager 初始化")
except Exception as e:
    test_failed("DeviceManager 初始化", str(e))

try:
    from src.adb_client import Point
    point = Point.from_string("100,200")
    assert point.x == 100
    assert point.y == 200
    test_passed("Point 坐标解析")
except Exception as e:
    test_failed("Point 坐标解析", str(e))

try:
    from src.screen import TextMatch
    match = TextMatch(text="测试", x=100, y=200, width=300, height=50, confidence=0.95)
    assert match.center == (250, 225)
    test_passed("TextMatch 创建")
except Exception as e:
    test_failed("TextMatch 创建", str(e))

try:
    from src.command_handler import CommandHandler
    handler = CommandHandler()
    result = handler.parse("点击 500,1000")
    assert result.command_type == CommandType.CLICK
    test_passed("CommandHandler 指令解析")
except Exception as e:
    test_failed("CommandHandler 指令解析", str(e))

try:
    from src.script_runner import ScriptRunner
    manager = Mock()
    runner = ScriptRunner(manager)
    script = [
        {"action": "click", "params": {"target": "100,200"}},
        {"action": "sleep", "params": {"seconds": 1}}
    ]
    is_valid, message = runner.validate_script(script)
    assert is_valid is True
    test_passed("ScriptRunner 脚本验证")
except Exception as e:
    test_failed("ScriptRunner 脚本验证", str(e))

# ==================== 测试3: FastAPI应用导入 ====================
print("\n3. FastAPI应用测试")
print("-" * 40)
try:
    import main
    test_passed("main.py 模块导入")
    assert hasattr(main, 'app')
    test_passed("FastAPI app 创建")
except Exception as e:
    test_failed("FastAPI应用测试", str(e))

# ==================== 测试4: 代码质量检查 ====================
print("\n4. 代码完整性检查")
print("-" * 40)

required_files = [
    "src/__init__.py",
    "src/device_manager.py",
    "src/adb_client.py",
    "src/screen.py",
    "src/script_runner.py",
    "src/command_handler.py",
    "main.py",
    "manifest.json",
    "requirements.txt",
    "SKILL.md"
]

for f in required_files:
    if os.path.exists(f):
        test_passed(f"文件存在: {f}")
    else:
        test_failed(f"文件存在: {f}", "文件缺失")

# ==================== 总结 ====================
print("\n" + "=" * 60)
print("测试结果总结")
print("=" * 60)

passed = sum(1 for _, ok in test_results if ok)
total = len(test_results)

print(f"总测试数: {total}")
print(f"通过: {passed}")
print(f"失败: {total - passed}")
print(f"通过率: {passed/total*100:.1f}%")

print("\n详细结果:")
for name, ok in test_results:
    status = "✓" if ok else "✗"
    print(f"  {status} {name}")

if passed == total:
    print("\n🎉 所有测试通过！")
else:
    print(f"\n⚠️  有 {total - passed} 个测试失败")

sys.exit(0 if passed == total else 1)

