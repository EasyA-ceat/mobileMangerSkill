"""
手机控制技能包 - FastAPI接口层
提供RESTful API接口，符合OpenClaw技能规范
"""

import os
import sys
import json
import base64
import traceback
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.device_manager import DeviceManager, get_device_manager, DeviceStatus
from src.adb_client import ADBClient, Point, get_adb_client
from src.screen import ScreenController, get_screen_controller
from src.script_runner import ScriptRunner, get_script_runner, ActionType


# ==================== 数据模型定义 ====================

class ResponseModel(BaseModel):
    """统一响应模型"""
    code: int = Field(..., description="响应码，0表示成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")


class DeviceInfo(BaseModel):
    """设备信息"""
    device_id: str
    status: str
    type: str
    model: Optional[str] = None
    android_version: Optional[str] = None


class DeviceListRequest(BaseModel):
    """设备列表请求"""
    refresh: bool = Field(True, description="是否刷新设备列表")


class DeviceConnectRequest(BaseModel):
    """设备连接请求"""
    device_id: str = Field(..., description="设备ID")
    wireless: bool = Field(False, description="是否使用无线连接")


class DeviceDisconnectRequest(BaseModel):
    """设备断开请求"""
    device_id: str = Field(..., description="设备ID")


class ClickRequest(BaseModel):
    """点击请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    target: str = Field(..., description="点击目标(坐标或文字)")


class SwipeRequest(BaseModel):
    """滑动请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    start: str = Field(..., description="起始位置(格式: x,y)")
    end: str = Field(..., description="结束位置(格式: x,y)")
    duration: int = Field(500, description="滑动时长(毫秒)", ge=100, le=5000)


class InputRequest(BaseModel):
    """输入文字请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    text: str = Field(..., description="要输入的文字")


class KeyRequest(BaseModel):
    """按键请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    key: str = Field(..., description="按键名称")


class AppRequest(BaseModel):
    """应用管理请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    action: str = Field(..., description="操作类型(start/stop/list)")
    package_name: Optional[str] = Field(None, description="应用包名")


class ScreenshotRequest(BaseModel):
    """截图请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    save_path: Optional[str] = Field(None, description="保存路径(可选)")


class ScriptRunRequest(BaseModel):
    """脚本执行请求"""
    device_id: Optional[str] = Field(None, description="设备ID")
    script: Union[str, List[Dict[str, Any]]] = Field(..., description="脚本内容")


# ==================== FastAPI应用 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    print("手机控制技能包启动中...")
    yield
    # 关闭时清理
    print("手机控制技能包已停止")


app = FastAPI(
    title="手机控制技能包",
    description="OpenClaw技能包 - 通过ADB远程控制Android设备",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    traceback_str = traceback.format_exc()
    print(f"发生错误:\n{traceback_str}")

    return JSONResponse(
        status_code=500,
        content={
            "code": 5000,
            "message": f"内部错误: {str(exc)}",
            "data": None
        }
    )


# ==================== 响应辅助函数 ====================

def success_response(data: Any = None, message: str = "success") -> Dict:
    """成功响应"""
    return {
        "code": 0,
        "message": message,
        "data": data
    }


def error_response(code: int, message: str, data: Any = None) -> Dict:
    """错误响应"""
    return {
        "code": code,
        "message": message,
        "data": data
    }


# ==================== API路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "手机控制技能包",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return success_response({"status": "healthy"})


# ----- 设备管理接口 -----

@app.post("/api/phone-control/v1/device/list", response_model=ResponseModel)
async def list_devices(request: DeviceListRequest):
    """获取设备列表"""
    try:
        manager = get_device_manager()
        devices = manager.list_devices(refresh=request.refresh)

        device_list = []
        for d in devices:
            device_list.append({
                "device_id": d.device_id,
                "status": d.status.value,
                "type": d.type.value,
                "model": d.model,
                "android_version": d.android_version
            })

        return success_response({"devices": device_list})

    except Exception as e:
        return error_response(1003, f"获取设备列表失败: {str(e)}")


@app.post("/api/phone-control/v1/device/connect", response_model=ResponseModel)
async def connect_device(request: DeviceConnectRequest):
    """连接设备"""
    try:
        manager = get_device_manager()
        success = manager.connect_device(request.device_id, wireless=request.wireless)

        if success:
            return success_response(None, f"设备 {request.device_id} 连接成功")
        else:
            return error_response(1002, f"设备 {request.device_id} 连接失败")

    except Exception as e:
        return error_response(1002, f"连接设备失败: {str(e)}")


@app.post("/api/phone-control/v1/device/disconnect", response_model=ResponseModel)
async def disconnect_device(request: DeviceDisconnectRequest):
    """断开设备"""
    try:
        manager = get_device_manager()
        success = manager.disconnect_device(request.device_id)

        if success:
            return success_response(None, f"设备 {request.device_id} 断开成功")
        else:
            return error_response(1003, f"设备 {request.device_id} 断开失败")

    except Exception as e:
        return error_response(1003, f"断开设备失败: {str(e)}")


# ----- 控制接口 -----

@app.post("/api/phone-control/v1/control/click", response_model=ResponseModel)
async def click(request: ClickRequest):
    """点击操作"""
    try:
        client = get_adb_client(get_device_manager(), request.device_id)

        # 判断是坐标还是文字
        target = request.target.strip()
        if ',' in target and all(part.strip().isdigit() or part.strip().lstrip('-').isdigit() for part in target.split(',')):
            # 坐标点击
            parts = target.split(',')
            x, y = int(parts[0]), int(parts[1])
            success = client.click(x, y)
            if success:
                return success_response(None, f"点击坐标 ({x}, {y}) 成功")
            else:
                return error_response(1003, "点击失败")
        else:
            # 文字点击 (需要OCR)
            screen = get_screen_controller(get_device_manager())
            success = screen.click_by_text(target, request.device_id)
            if success:
                return success_response(None, f"点击文字 '{target}' 成功")
            else:
                return error_response(1004, f"未找到文字 '{target}'")

    except Exception as e:
        return error_response(1003, f"点击操作失败: {str(e)}")


@app.post("/api/phone-control/v1/control/swipe", response_model=ResponseModel)
async def swipe(request: SwipeRequest):
    """滑动操作"""
    try:
        client = get_adb_client(get_device_manager(), request.device_id)

        # 解析起始位置
        start_parts = request.start.split(',')
        end_parts = request.end.split(',')

        if len(start_parts) != 2 or len(end_parts) != 2:
            return error_response(2001, "坐标格式错误，应为 'x,y'")

        start_x, start_y = int(start_parts[0]), int(start_parts[1])
        end_x, end_y = int(end_parts[0]), int(end_parts[1])

        success = client.swipe(start_x, start_y, end_x, end_y, request.duration)

        if success:
            return success_response(
                None,
                f"滑动从 ({start_x}, {start_y}) 到 ({end_x}, {end_y}) 成功"
            )
        else:
            return error_response(1003, "滑动操作失败")

    except ValueError:
        return error_response(2001, "坐标格式错误")
    except Exception as e:
        return error_response(1003, f"滑动操作失败: {str(e)}")


@app.post("/api/phone-control/v1/control/input", response_model=ResponseModel)
async def input_text(request: InputRequest):
    """输入文字"""
    try:
        client = get_adb_client(get_device_manager(), request.device_id)
        success = client.input_text(request.text)

        if success:
            return success_response(None, f"输入文字 '{request.text}' 成功")
        else:
            return error_response(1003, "输入文字失败")

    except Exception as e:
        return error_response(1003, f"输入文字失败: {str(e)}")


@app.post("/api/phone-control/v1/control/key", response_model=ResponseModel)
async def press_key(request: KeyRequest):
    """按键操作"""
    try:
        client = get_adb_client(get_device_manager(), request.device_id)
        success = client.press_key(request.key)

        if success:
            return success_response(None, f"按键 '{request.key}' 成功")
        else:
            return error_response(1003, "按键操作失败")

    except Exception as e:
        return error_response(1003, f"按键操作失败: {str(e)}")


@app.post("/api/phone-control/v1/control/app", response_model=ResponseModel)
async def manage_app(request: AppRequest):
    """应用管理"""
    try:
        client = get_adb_client(get_device_manager(), request.device_id)

        if request.action == "start":
            if not request.package_name:
                return error_response(2001, "缺少应用包名")
            success = client.start_app(request.package_name)
            if success:
                return success_response(None, f"启动应用 '{request.package_name}' 成功")
            else:
                return error_response(1003, "启动应用失败")

        elif request.action == "stop":
            if not request.package_name:
                return error_response(2001, "缺少应用包名")
            success = client.stop_app(request.package_name)
            if success:
                return success_response(None, f"停止应用 '{request.package_name}' 成功")
            else:
                return error_response(1003, "停止应用失败")

        elif request.action == "list":
            apps = client.list_apps()
            return success_response({"apps": apps})

        else:
            return error_response(2001, f"未知的操作类型: {request.action}")

    except Exception as e:
        return error_response(1003, f"应用管理失败: {str(e)}")


# ----- 屏幕接口 -----

@app.post("/api/phone-control/v1/screen/screenshot", response_model=ResponseModel)
async def take_screenshot(request: ScreenshotRequest):
    """截取屏幕"""
    try:
        screen = get_screen_controller(get_device_manager())

        # 截图
        image = screen.screenshot(request.device_id, request.save_path)

        if image is not None:
            # 转换为base64
            img_base64 = screen.screenshot_to_base64(request.device_id)

            response_data = {
                "size": {
                    "width": image.shape[1],
                    "height": image.shape[0]
                }
            }

            if img_base64:
                response_data["image_base64"] = img_base64

            if request.save_path:
                response_data["save_path"] = request.save_path

            return success_response(response_data, "截图成功")
        else:
            return error_response(1003, "截图失败")

    except Exception as e:
        return error_response(1003, f"截图失败: {str(e)}")


# ----- 脚本接口 -----

@app.post("/api/phone-control/v1/script/run", response_model=ResponseModel)
async def run_script(request: ScriptRunRequest):
    """执行脚本"""
    try:
        runner = get_script_runner(get_device_manager(), request.device_id)

        # 验证脚本
        is_valid, message = runner.validate_script(request.script)
        if not is_valid:
            return error_response(2001, f"脚本验证失败: {message}")

        # 执行脚本
        results = runner.execute_script(request.script, request.device_id)

        # 汇总结果
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        return success_response({
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": [
                {
                    "success": r.success,
                    "action_type": r.action_type,
                    "message": r.message,
                    "data": r.data,
                    "execution_time": r.execution_time
                }
                for r in results
            ]
        }, f"脚本执行完成，成功{successful}个，失败{failed}个")

    except Exception as e:
        return error_response(1003, f"脚本执行失败: {str(e)}")


# ----- 主入口 -----

if __name__ == "__main__":
    import uvicorn

    # 获取配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8080))

    print(f"启动手机控制技能包服务...")
    print(f"API文档: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port)
