"""
手机控制技能包 - FastAPI接口层
提供RESTful API接口和WebSocket，符合OpenClaw技能规范
"""

import os
import sys
import json
import base64
import traceback
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union, Set
from contextlib import asynccontextmanager
from datetime import datetime

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security.api_key import APIKeyQuery, APIKeyHeader
from pydantic import BaseModel, Field

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.device_manager import DeviceManager, get_device_manager, DeviceStatus
from src.adb_client import ADBClient, Point, get_adb_client
from src.screen import ScreenController, get_screen_controller
from src.script_runner import ScriptRunner, get_script_runner, ActionType
from src.script_recorder import ScriptRecorder, get_script_recorder
from src.database import (
    get_database_manager,
    DatabaseManager,
    DeviceRecord,
    ScriptRecord,
    OperationLogRecord
)

# ==================== 安全配置 ====================

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 从环境变量读取API Key，默认生成一个随机密钥
API_KEY = os.getenv("API_KEY", os.urandom(32).hex())
ENV = os.getenv("ENV", "development")

# API Key认证
api_key_query = APIKeyQuery(name="api_key", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(
    api_key_query: str = Depends(api_key_query),
    api_key_header: str = Depends(api_key_header),
):
    """验证API Key"""
    if api_key_query == API_KEY or api_key_header == API_KEY:
        return api_key_query or api_key_header
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API Key"
    )

# 初始化速率限制器
limiter = Limiter(key_func=get_remote_address)


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


class ScriptCreateRequest(BaseModel):
    """脚本创建请求"""
    script_name: str = Field(..., description="脚本名称")
    script_content: Union[str, List[Dict[str, Any]]] = Field(..., description="脚本内容")
    description: Optional[str] = Field(None, description="脚本描述")


class ScriptUpdateRequest(BaseModel):
    """脚本更新请求"""
    script_name: Optional[str] = Field(None, description="脚本名称")
    script_content: Optional[Union[str, List[Dict[str, Any]]]] = Field(None, description="脚本内容")
    description: Optional[str] = Field(None, description="脚本描述")
    status: Optional[str] = Field(None, description="状态")


class RecordStartRequest(BaseModel):
    """开始录制请求"""
    device_id: Optional[str] = Field(None, description="设备ID")


class RecordActionRequest(BaseModel):
    """录制动作请求"""
    action_type: str = Field(..., description="动作类型")
    params: Dict[str, Any] = Field(..., description="动作参数")
    description: Optional[str] = Field(None, description="动作描述")


# ==================== WebSocket连接管理器 ====================

class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.device_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        """连接WebSocket"""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket"""
        self.active_connections.discard(websocket)
        # 从设备连接中移除
        for device_id in list(self.device_connections.keys()):
            self.device_connections[device_id].discard(websocket)
            if not self.device_connections[device_id]:
                del self.device_connections[device_id]

    def subscribe_device(self, websocket: WebSocket, device_id: str):
        """订阅设备事件"""
        if device_id not in self.device_connections:
            self.device_connections[device_id] = set()
        self.device_connections[device_id].add(websocket)

    def unsubscribe_device(self, websocket: WebSocket, device_id: str):
        """取消订阅设备事件"""
        if device_id in self.device_connections:
            self.device_connections[device_id].discard(websocket)
            if not self.device_connections[device_id]:
                del self.device_connections[device_id]

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """发送个人消息"""
        await websocket.send_json(message)

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

    async def broadcast_to_device(self, device_id: str, message: Dict[str, Any]):
        """向特定设备的订阅者广播"""
        if device_id in self.device_connections:
            for connection in self.device_connections[device_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


# 全局连接管理器
manager = ConnectionManager()

# 全局录制器实例
recorders: Dict[str, ScriptRecorder] = {}


# ==================== FastAPI应用 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("手机控制技能包启动中...")
    logger.info(f"当前环境: {ENV}")
    if ENV == "development":
        logger.warning(f"API Key (仅供开发参考): {API_KEY}")
    # 初始化数据库
    get_database_manager()
    yield
    # 关闭时清理
    logger.info("手机控制技能包已停止")


app = FastAPI(
    title="手机控制技能包",
    description="OpenClaw技能包 - 通过ADB远程控制Android设备",
    version="0.1.0",
    docs_url=None if ENV == "production" else "/docs",
    redoc_url=None if ENV == "production" else "/redoc",
    openapi_url=None if ENV == "production" else "/openapi.json",
    lifespan=lifespan
)

# 添加速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 安全HTTP头中间件
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# 配置CORS - 仅允许本地访问
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 挂载静态文件
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 根路径返回Web管理面板
@app.get("/")
async def root():
    """根路径 - 返回Web管理面板"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": "手机控制技能包",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "web_panel": "/static/index.html"
    }


# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # 生产环境只返回通用错误信息
    error_message = "Internal server error" if ENV == "production" else f"内部错误: {str(exc)}"
    
    return JSONResponse(
        status_code=500,
        content={
            "code": 5000,
            "message": error_message,
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


def log_operation(
    db: DatabaseManager,
    device_id: Optional[str],
    operation_type: str,
    operation_detail: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    client_ip: Optional[str] = None
):
    """记录操作日志"""
    try:
        # 记录客户端IP到操作详情中
        detail_with_ip = operation_detail
        if client_ip:
            detail_json = {}
            if operation_detail:
                try:
                    detail_json = json.loads(operation_detail)
                except:
                    detail_json["detail"] = operation_detail
            detail_json["source_ip"] = client_ip
            detail_with_ip = json.dumps(detail_json, ensure_ascii=False)
        
        log = OperationLogRecord(
            device_id=device_id,
            operation_type=operation_type,
            operation_detail=detail_with_ip,
            status=status,
            error_message=error_message
        )
        db.save_log(log)
    except Exception as e:
        logger.error(f"记录日志失败: {e}")


# ==================== WebSocket端点 ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, api_key: str = Query(...)):
    """WebSocket端点 - 需要API Key认证"""
    # 验证API Key
    if api_key != API_KEY:
        await websocket.close(code=1008)
        return
    
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "")

            if message_type == "subscribe":
                # 订阅设备
                device_id = data.get("device_id")
                if device_id:
                    manager.subscribe_device(websocket, device_id)
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "device_id": device_id
                    }, websocket)

            elif message_type == "unsubscribe":
                # 取消订阅
                device_id = data.get("device_id")
                if device_id:
                    manager.unsubscribe_device(websocket, device_id)
                    await manager.send_personal_message({
                        "type": "unsubscribed",
                        "device_id": device_id
                    }, websocket)

            elif message_type == "ping":
                # 心跳
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        manager.disconnect(websocket)


# ==================== API路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "手机控制技能包",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return success_response({"status": "healthy"})


# ----- 设备管理接口 -----

@app.post("/api/v1/devices", response_model=ResponseModel)
@limiter.limit("60/minute")
async def list_devices(
    request: Request,
    device_request: DeviceListRequest,
    api_key: str = Depends(get_api_key)
):
    """获取设备列表"""
    try:
        manager = get_device_manager()
        db = get_database_manager()
        devices = manager.list_devices(refresh=device_request.refresh)

        device_list = []
        for d in devices:
            # 更新数据库中的设备信息
            device_record = DeviceRecord(
                device_id=d.device_id,
                device_name=d.name or d.device_id,
                device_model=d.model,
                os_version=d.android_version,
                os_type="Android",
                status=d.status.value,
                last_connect_time=datetime.now() if d.status == DeviceStatus.CONNECTED else None
            )
            db.save_device(device_record)

            device_list.append({
                "device_id": d.device_id,
                "status": d.status.value,
                "type": d.type.value,
                "model": d.model,
                "android_version": d.android_version,
                "name": d.name or d.device_id
            })

        return success_response({"devices": device_list})

    except Exception as e:
        return error_response(1003, f"获取设备列表失败: {str(e)}")


@app.get("/api/v1/devices/{device_id}", response_model=ResponseModel)
@limiter.limit("60/minute")
async def get_device(
    request: Request,
    device_id: str,
    api_key: str = Depends(get_api_key)
):
    """获取设备详情"""
    try:
        manager = get_device_manager()
        db = get_database_manager()

        # 先从内存中获取
        device = manager.get_device(device_id)
        if device:
            return success_response({
                "device_id": device.device_id,
                "status": device.status.value,
                "type": device.type.value,
                "model": device.model,
                "android_version": device.android_version,
                "name": device.name or device.device_id
            })

        # 从数据库获取
        device_record = db.get_device(device_id)
        if device_record:
            return success_response(device_record.to_dict())

        return error_response(1002, f"设备 {device_id} 不存在")

    except Exception as e:
        return error_response(1003, f"获取设备详情失败: {str(e)}")


@app.post("/api/v1/devices/{device_id}/connect", response_model=ResponseModel)
@limiter.limit("30/minute")
async def connect_device(
    request: Request,
    device_id: str,
    connect_request: Optional[DeviceConnectRequest] = None,
    api_key: str = Depends(get_api_key)
):
    """连接设备"""
    client_ip = request.client.host
    try:
        manager = get_device_manager()
        db = get_database_manager()

        wireless = connect_request.wireless if connect_request else False
        success, message = manager.connect_device(device_id, timeout=30)

        if success:
            # 更新数据库
            device_record = DeviceRecord(
                device_id=device_id,
                device_name=device_id,
                status="connected",
                last_connect_time=datetime.now()
            )
            db.save_device(device_record)

            # 记录日志
            log_operation(db, device_id, "connect", f"连接设备 {device_id}", "success", client_ip=client_ip)

            # 广播设备状态变更
            await manager.broadcast({
                "type": "device_status",
                "device_id": device_id,
                "status": "connected"
            })

            return success_response(None, f"设备 {device_id} 连接成功")
        else:
            log_operation(db, device_id, "connect", f"连接设备 {device_id}", "failed", message, client_ip=client_ip)
            return error_response(1002, f"设备 {device_id} 连接失败: {message}")

    except Exception as e:
        return error_response(1002, f"连接设备失败: {str(e)}")


@app.post("/api/v1/devices/{device_id}/disconnect", response_model=ResponseModel)
@limiter.limit("30/minute")
async def disconnect_device(
    request: Request,
    device_id: str,
    api_key: str = Depends(get_api_key)
):
    """断开设备"""
    client_ip = request.client.host
    try:
        manager = get_device_manager()
        db = get_database_manager()

        success, message = manager.disconnect_device(device_id)

        if success:
            # 更新数据库
            device_record = db.get_device(device_id)
            if device_record:
                device_record.status = "disconnected"
                db.save_device(device_record)

            # 记录日志
            log_operation(db, device_id, "disconnect", f"断开设备 {device_id}", "success", client_ip=client_ip)

            # 广播设备状态变更
            await manager.broadcast({
                "type": "device_status",
                "device_id": device_id,
                "status": "disconnected"
            })

            return success_response(None, f"设备 {device_id} 断开成功")
        else:
            return error_response(1003, f"设备 {device_id} 断开失败: {message}")

    except Exception as e:
        return error_response(1003, f"断开设备失败: {str(e)}")


# ----- 控制接口 -----

@app.post("/api/v1/devices/{device_id}/tap", response_model=ResponseModel)
@limiter.limit("120/minute")
async def click(
    request: Request,
    device_id: str,
    click_request: ClickRequest,
    api_key: str = Depends(get_api_key)
):
    """点击操作"""
    client_ip = request.client.host
    try:
        db = get_database_manager()
        client = get_adb_client(get_device_manager(), device_id)

        # 判断是坐标还是文字
        target = click_request.target.strip()
        if ',' in target and all(part.strip().isdigit() or part.strip().lstrip('-').isdigit() for part in target.split(',')):
            # 坐标点击
            parts = target.split(',')
            x, y = int(parts[0]), int(parts[1])
            success = client.click(x, y, device_id)
            operation_detail = f"点击坐标 ({x}, {y})"
        else:
            # 文字点击 (需要OCR)
            screen = get_screen_controller(get_device_manager())
            success = screen.click_by_text(target, device_id)
            operation_detail = f"点击文字 '{target}'"

        if success:
            log_operation(db, device_id, "click", operation_detail, "success", client_ip=client_ip)
            return success_response(None, operation_detail + " 成功")
        else:
            log_operation(db, device_id, "click", operation_detail, "failed", client_ip=client_ip)
            return error_response(1003, "点击失败")

    except Exception as e:
        return error_response(1003, f"点击操作失败: {str(e)}")


@app.post("/api/v1/devices/{device_id}/swipe", response_model=ResponseModel)
@limiter.limit("120/minute")
async def swipe(
    request: Request,
    device_id: str,
    swipe_request: SwipeRequest,
    api_key: str = Depends(get_api_key)
):
    """滑动操作"""
    client_ip = request.client.host
    try:
        db = get_database_manager()
        client = get_adb_client(get_device_manager(), device_id)

        # 解析起始位置
        start_parts = swipe_request.start.split(',')
        end_parts = swipe_request.end.split(',')

        if len(start_parts) != 2 or len(end_parts) != 2:
            return error_response(2001, "坐标格式错误，应为 'x,y'")

        start_x, start_y = int(start_parts[0]), int(start_parts[1])
        end_x, end_y = int(end_parts[0]), int(end_parts[1])

        success = client.swipe(start_x, start_y, end_x, end_y, swipe_request.duration, device_id)
        operation_detail = f"滑动从 ({start_x}, {start_y}) 到 ({end_x}, {end_y})"

        if success:
            log_operation(db, device_id, "swipe", operation_detail, "success", client_ip=client_ip)
            return success_response(None, operation_detail + " 成功")
        else:
            log_operation(db, device_id, "swipe", operation_detail, "failed", client_ip=client_ip)
            return error_response(1003, "滑动操作失败")

    except ValueError:
        return error_response(2001, "坐标格式错误")
    except Exception as e:
        return error_response(1003, f"滑动操作失败: {str(e)}")


@app.post("/api/v1/devices/{device_id}/input", response_model=ResponseModel)
@limiter.limit("120/minute")
async def input_text(
    request: Request,
    device_id: str,
    input_request: InputRequest,
    api_key: str = Depends(get_api_key)
):
    """输入文字"""
    client_ip = request.client.host
    try:
        db = get_database_manager()
        client = get_adb_client(get_device_manager(), device_id)
        success = client.input_text(input_request.text, device_id)
        operation_detail = f"输入文字 '{input_request.text}'"

        if success:
            log_operation(db, device_id, "input", operation_detail, "success", client_ip=client_ip)
            return success_response(None, operation_detail + " 成功")
        else:
            log_operation(db, device_id, "input", operation_detail, "failed", client_ip=client_ip)
            return error_response(1003, "输入文字失败")

    except Exception as e:
        return error_response(1003, f"输入文字失败: {str(e)}")


@app.post("/api/v1/devices/{device_id}/key", response_model=ResponseModel)
@limiter.limit("120/minute")
async def press_key(
    request: Request,
    device_id: str,
    key_request: KeyRequest,
    api_key: str = Depends(get_api_key)
):
    """按键操作"""
    client_ip = request.client.host
    try:
        db = get_database_manager()
        client = get_adb_client(get_device_manager(), device_id)
        success = client.press_key(key_request.key, device_id)
        operation_detail = f"按键 '{key_request.key}'"

        if success:
            log_operation(db, device_id, "key", operation_detail, "success", client_ip=client_ip)
            return success_response(None, operation_detail + " 成功")
        else:
            log_operation(db, device_id, "key", operation_detail, "failed", client_ip=client_ip)
            return error_response(1003, "按键操作失败")

    except Exception as e:
        return error_response(1003, f"按键操作失败: {str(e)}")


@app.post("/api/v1/devices/{device_id}/screenshot", response_model=ResponseModel)
@limiter.limit("60/minute")
async def take_screenshot(
    request: Request,
    device_id: str,
    screenshot_request: Optional[ScreenshotRequest] = None,
    api_key: str = Depends(get_api_key)
):
    """截取屏幕"""
    client_ip = request.client.host
    try:
        db = get_database_manager()
        screen = get_screen_controller(get_device_manager())
        save_path = screenshot_request.save_path if screenshot_request else None

        # 截图
        image = screen.screenshot(device_id, save_path)

        if image is not None:
            # 转换为base64
            img_base64 = screen.screenshot_to_base64(device_id)

            response_data = {
                "size": {
                    "width": image.shape[1],
                    "height": image.shape[0]
                }
            }

            if img_base64:
                response_data["image_base64"] = img_base64

            if save_path:
                response_data["save_path"] = save_path

            log_operation(db, device_id, "screenshot", "截图", "success", client_ip=client_ip)
            return success_response(response_data, "截图成功")
        else:
            log_operation(db, device_id, "screenshot", "截图", "failed", client_ip=client_ip)
            return error_response(1003, "截图失败")

    except Exception as e:
        return error_response(1003, f"截图失败: {str(e)}")


# ----- 脚本管理接口 -----

@app.get("/api/v1/scripts", response_model=ResponseModel)
@limiter.limit("60/minute")
async def list_scripts(
    request: Request,
    status: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """获取脚本列表"""
    try:
        db = get_database_manager()
        scripts = db.get_all_scripts(status=status)
        return success_response({
            "scripts": [s.to_dict() for s in scripts]
        })
    except Exception as e:
        return error_response(2001, f"获取脚本列表失败: {str(e)}")


@app.get("/api/v1/scripts/{script_id}", response_model=ResponseModel)
@limiter.limit("60/minute")
async def get_script(
    request: Request,
    script_id: int,
    api_key: str = Depends(get_api_key)
):
    """获取脚本详情"""
    try:
        db = get_database_manager()
        script = db.get_script(script_id)
        if script:
            return success_response(script.to_dict())
        else:
            return error_response(2001, f"脚本 {script_id} 不存在")
    except Exception as e:
        return error_response(2001, f"获取脚本详情失败: {str(e)}")


@app.post("/api/v1/scripts", response_model=ResponseModel)
@limiter.limit("30/minute")
async def create_script(
    request: Request,
    script_request: ScriptCreateRequest,
    api_key: str = Depends(get_api_key)
):
    """创建脚本"""
    try:
        db = get_database_manager()

        # 处理脚本内容
        if isinstance(script_request.script_content, list):
            script_content = json.dumps(script_request.script_content, ensure_ascii=False)
        else:
            script_content = script_request.script_content

        script = ScriptRecord(
            script_name=script_request.script_name,
            script_content=script_content,
            description=script_request.description,
            status="active"
        )
        script = db.save_script(script)

        return success_response(script.to_dict(), "脚本创建成功")
    except Exception as e:
        return error_response(2001, f"创建脚本失败: {str(e)}")


@app.put("/api/v1/scripts/{script_id}", response_model=ResponseModel)
@limiter.limit("30/minute")
async def update_script(
    request: Request,
    script_id: int,
    script_request: ScriptUpdateRequest,
    api_key: str = Depends(get_api_key)
):
    """更新脚本"""
    try:
        db = get_database_manager()
        script = db.get_script(script_id)

        if not script:
            return error_response(2001, f"脚本 {script_id} 不存在")

        if script_request.script_name is not None:
            script.script_name = script_request.script_name
        if script_request.script_content is not None:
            if isinstance(script_request.script_content, list):
                script.script_content = json.dumps(script_request.script_content, ensure_ascii=False)
            else:
                script.script_content = script_request.script_content
        if script_request.description is not None:
            script.description = script_request.description
        if script_request.status is not None:
            script.status = script_request.status

        script = db.save_script(script)
        return success_response(script.to_dict(), "脚本更新成功")
    except Exception as e:
        return error_response(2001, f"更新脚本失败: {str(e)}")


@app.delete("/api/v1/scripts/{script_id}", response_model=ResponseModel)
@limiter.limit("30/minute")
async def delete_script(
    request: Request,
    script_id: int,
    api_key: str = Depends(get_api_key)
):
    """删除脚本"""
    try:
        db = get_database_manager()
        success = db.delete_script(script_id)
        if success:
            return success_response(None, "脚本删除成功")
        else:
            return error_response(2001, f"脚本 {script_id} 不存在")
    except Exception as e:
        return error_response(2001, f"删除脚本失败: {str(e)}")


@app.post("/api/v1/scripts/{script_id}/execute", response_model=ResponseModel)
@limiter.limit("60/minute")
async def execute_script(
    request: Request,
    script_id: int,
    device_id: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """执行脚本"""
    client_ip = request.client.host
    try:
        db = get_database_manager()
        script = db.get_script(script_id)

        if not script:
            return error_response(2001, f"脚本 {script_id} 不存在")

        runner = get_script_runner(get_device_manager(), device_id)
        results = runner.execute_script(script.script_content, device_id)

        # 汇总结果
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        log_operation(db, device_id, "execute_script", f"执行脚本 {script_id}",
                      "success" if failed == 0 else "failed", client_ip=client_ip)

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
        return error_response(2002, f"脚本执行失败: {str(e)}")


# ----- 脚本录制接口 -----

@app.post("/api/v1/record/start", response_model=ResponseModel)
@limiter.limit("30/minute")
async def start_recording(
    request: Request,
    record_request: RecordStartRequest,
    api_key: str = Depends(get_api_key)
):
    """开始录制"""
    try:
        device_id = record_request.device_id
        recorder_key = device_id or "default"

        if recorder_key in recorders and recorders[recorder_key].is_recording:
            return error_response(2001, "已经在录制中")

        recorder = get_script_recorder(get_device_manager(), device_id)
        success = recorder.start_recording(device_id)

        if success:
            recorders[recorder_key] = recorder
            return success_response(recorder.get_recording_status(), "开始录制成功")
        else:
            return error_response(2001, "开始录制失败")

    except Exception as e:
        return error_response(2001, f"开始录制失败: {str(e)}")


@app.post("/api/v1/record/stop", response_model=ResponseModel)
@limiter.limit("30/minute")
async def stop_recording(
    request: Request,
    device_id: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """停止录制"""
    try:
        recorder_key = device_id or "default"

        if recorder_key not in recorders:
            return error_response(2001, "没有正在进行的录制")

        recorder = recorders[recorder_key]
        actions = recorder.stop_recording()

        return success_response({
            "actions": [a.to_dict() for a in actions],
            "script_json": recorder.get_script_json()
        }, "停止录制成功")

    except Exception as e:
        return error_response(2001, f"停止录制失败: {str(e)}")


@app.get("/api/v1/record/status", response_model=ResponseModel)
@limiter.limit("60/minute")
async def get_record_status(
    request: Request,
    device_id: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """获取录制状态"""
    try:
        recorder_key = device_id or "default"

        if recorder_key not in recorders:
            return success_response({
                "is_recording": False,
                "action_count": 0,
                "duration": 0
            })

        recorder = recorders[recorder_key]
        return success_response(recorder.get_recording_status())

    except Exception as e:
        return error_response(2001, f"获取录制状态失败: {str(e)}")


@app.post("/api/v1/record/action", response_model=ResponseModel)
@limiter.limit("120/minute")
async def record_action(
    request: Request,
    action_request: RecordActionRequest,
    device_id: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """录制动作"""
    try:
        recorder_key = device_id or "default"

        if recorder_key not in recorders:
            return error_response(2001, "没有正在进行的录制")

        recorder = recorders[recorder_key]
        success = recorder.add_custom_action(
            action_request.action_type,
            action_request.params,
            action_request.description
        )

        if success:
            return success_response(None, "录制动作成功")
        else:
            return error_response(2001, "录制动作失败")

    except Exception as e:
        return error_response(2001, f"录制动作失败: {str(e)}")


# ----- 日志查询接口 -----

@app.get("/api/v1/logs", response_model=ResponseModel)
@limiter.limit("60/minute")
async def get_logs(
    request: Request,
    device_id: Optional[str] = None,
    operation_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    api_key: str = Depends(get_api_key)
):
    """获取操作日志"""
    try:
        db = get_database_manager()
        logs = db.get_logs(device_id, operation_type, limit, offset)
        return success_response({
            "logs": [l.to_dict() for l in logs],
            "total": len(logs)
        })
    except Exception as e:
        return error_response(5001, f"获取日志失败: {str(e)}")


# ==================== 主入口 ====================

if __name__ == "__main__":
    import uvicorn

    # 获取配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8080))

    print(f"启动手机控制技能包服务...")
    print(f"API文档: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port)
