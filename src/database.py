"""
数据库模块
提供SQLite数据库操作和数据模型
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ScriptStatus(Enum):
    """脚本状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class OperationStatus(Enum):
    """操作状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class DeviceRecord:
    """设备记录"""
    id: Optional[int] = None
    device_id: str = ""
    device_name: str = ""
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    os_type: str = "Android"
    status: str = "disconnected"
    last_connect_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_model": self.device_model,
            "os_version": self.os_version,
            "os_type": self.os_type,
            "status": self.status,
            "last_connect_time": self.last_connect_time.isoformat() if self.last_connect_time else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ScriptRecord:
    """脚本记录"""
    id: Optional[int] = None
    script_name: str = ""
    script_content: str = ""
    description: Optional[str] = None
    created_by: Optional[str] = None
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "script_name": self.script_name,
            "script_content": self.script_content,
            "description": self.description,
            "created_by": self.created_by,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    def get_script_actions(self) -> List[Dict]:
        """获取脚本动作列表"""
        try:
            return json.loads(self.script_content)
        except Exception:
            return []


@dataclass
class OperationLogRecord:
    """操作日志记录"""
    id: Optional[int] = None
    device_id: Optional[str] = None
    operation_type: str = ""
    operation_detail: Optional[str] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "operation_type": self.operation_type,
            "operation_detail": self.operation_detail,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat()
        }


class DatabaseManager:
    """
    数据库管理器
    负责SQLite数据库的初始化、连接和操作
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径，默认为用户目录下的mobile_manager.db
        """
        if db_path is None:
            # 默认使用用户目录下的数据库
            home_dir = Path.home()
            app_dir = home_dir / ".mobile_manager"
            app_dir.mkdir(exist_ok=True)
            db_path = str(app_dir / "mobile_manager.db")

        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _set_db_permissions(self):
        """设置数据库文件权限（仅所有者可读写）"""
        try:
            if os.path.exists(self.db_path):
                # Windows不支持os.chmod的权限模式，跳过
                if os.name != 'nt':
                    os.chmod(self.db_path, 0o600)
        except Exception as e:
            print(f"设置数据库文件权限失败: {e}")

    def _init_database(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 设备表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                device_name TEXT NOT NULL,
                device_model TEXT,
                os_version TEXT,
                os_type TEXT NOT NULL DEFAULT 'Android',
                status TEXT NOT NULL DEFAULT 'disconnected',
                last_connect_time TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # 脚本表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_name TEXT NOT NULL,
                script_content TEXT NOT NULL,
                description TEXT,
                created_by TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # 操作日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                operation_type TEXT NOT NULL,
                operation_detail TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT NOT NULL
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scripts_status ON scripts(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_device_id ON operation_logs(device_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_created_at ON operation_logs(created_at)')

        conn.commit()
        
        # 设置文件权限
        self._set_db_permissions()

    # ==================== 设备操作 ====================

    def save_device(self, device: DeviceRecord) -> DeviceRecord:
        """保存或更新设备记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        if device.id is not None:
            # 更新
            cursor.execute('''
                UPDATE devices
                SET device_id = ?, device_name = ?, device_model = ?, os_version = ?,
                    os_type = ?, status = ?, last_connect_time = ?, updated_at = ?
                WHERE id = ?
            ''', (
                device.device_id, device.device_name, device.device_model,
                device.os_version, device.os_type, device.status,
                device.last_connect_time.isoformat() if device.last_connect_time else None,
                now, device.id
            ))
        else:
            # 检查是否已存在
            cursor.execute('SELECT id FROM devices WHERE device_id = ?', (device.device_id,))
            existing = cursor.fetchone()

            if existing:
                # 更新现有记录
                cursor.execute('''
                    UPDATE devices
                    SET device_name = ?, device_model = ?, os_version = ?,
                        os_type = ?, status = ?, last_connect_time = ?, updated_at = ?
                    WHERE device_id = ?
                ''', (
                    device.device_name, device.device_model, device.os_version,
                    device.os_type, device.status,
                    device.last_connect_time.isoformat() if device.last_connect_time else None,
                    now, device.device_id
                ))
                device.id = existing['id']
            else:
                # 插入新记录
                cursor.execute('''
                    INSERT INTO devices
                    (device_id, device_name, device_model, os_version, os_type, status,
                     last_connect_time, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    device.device_id, device.device_name, device.device_model,
                    device.os_version, device.os_type, device.status,
                    device.last_connect_time.isoformat() if device.last_connect_time else None,
                    now, now
                ))
                device.id = cursor.lastrowid

        conn.commit()
        return device

    def get_device(self, device_id: str) -> Optional[DeviceRecord]:
        """根据设备ID获取设备记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM devices WHERE device_id = ?', (device_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_device(row)
        return None

    def get_all_devices(self) -> List[DeviceRecord]:
        """获取所有设备记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM devices ORDER BY updated_at DESC')
        rows = cursor.fetchall()

        return [self._row_to_device(row) for row in rows]

    def delete_device(self, device_id: str) -> bool:
        """删除设备记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM devices WHERE device_id = ?', (device_id,))
        conn.commit()

        return cursor.rowcount > 0

    def _row_to_device(self, row: sqlite3.Row) -> DeviceRecord:
        """将数据库行转换为DeviceRecord对象"""
        return DeviceRecord(
            id=row['id'],
            device_id=row['device_id'],
            device_name=row['device_name'],
            device_model=row['device_model'],
            os_version=row['os_version'],
            os_type=row['os_type'],
            status=row['status'],
            last_connect_time=datetime.fromisoformat(row['last_connect_time']) if row['last_connect_time'] else None,
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at'])
        )

    # ==================== 脚本操作 ====================

    def save_script(self, script: ScriptRecord) -> ScriptRecord:
        """保存或更新脚本记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        if script.id is not None:
            # 更新
            cursor.execute('''
                UPDATE scripts
                SET script_name = ?, script_content = ?, description = ?,
                    created_by = ?, status = ?, updated_at = ?
                WHERE id = ?
            ''', (
                script.script_name, script.script_content, script.description,
                script.created_by, script.status, now, script.id
            ))
        else:
            # 插入
            cursor.execute('''
                INSERT INTO scripts
                (script_name, script_content, description, created_by, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                script.script_name, script.script_content, script.description,
                script.created_by, script.status, now, now
            ))
            script.id = cursor.lastrowid

        conn.commit()
        return script

    def get_script(self, script_id: int) -> Optional[ScriptRecord]:
        """根据ID获取脚本记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM scripts WHERE id = ?', (script_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_script(row)
        return None

    def get_all_scripts(self, status: Optional[str] = None) -> List[ScriptRecord]:
        """获取所有脚本记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute('SELECT * FROM scripts WHERE status = ? ORDER BY updated_at DESC', (status,))
        else:
            cursor.execute('SELECT * FROM scripts ORDER BY updated_at DESC')

        rows = cursor.fetchall()
        return [self._row_to_script(row) for row in rows]

    def delete_script(self, script_id: int) -> bool:
        """删除脚本记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM scripts WHERE id = ?', (script_id,))
        conn.commit()

        return cursor.rowcount > 0

    def _row_to_script(self, row: sqlite3.Row) -> ScriptRecord:
        """将数据库行转换为ScriptRecord对象"""
        return ScriptRecord(
            id=row['id'],
            script_name=row['script_name'],
            script_content=row['script_content'],
            description=row['description'],
            created_by=row['created_by'],
            status=row['status'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at'])
        )

    # ==================== 操作日志操作 ====================

    def save_log(self, log: OperationLogRecord) -> OperationLogRecord:
        """保存操作日志"""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO operation_logs
            (device_id, operation_type, operation_detail, status, error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            log.device_id, log.operation_type, log.operation_detail,
            log.status, log.error_message, now
        ))

        log.id = cursor.lastrowid
        log.created_at = datetime.fromisoformat(now)
        conn.commit()

        return log

    def get_logs(
        self,
        device_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OperationLogRecord]:
        """获取操作日志列表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM operation_logs WHERE 1=1'
        params = []

        if device_id:
            query += ' AND device_id = ?'
            params.append(device_id)

        if operation_type:
            query += ' AND operation_type = ?'
            params.append(operation_type)

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_log(row) for row in rows]

    def delete_old_logs(self, days: int = 30) -> int:
        """删除旧日志"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now() - datetime.timedelta(days=days)).isoformat()
        cursor.execute('DELETE FROM operation_logs WHERE created_at < ?', (cutoff,))
        conn.commit()

        return cursor.rowcount

    def _row_to_log(self, row: sqlite3.Row) -> OperationLogRecord:
        """将数据库行转换为OperationLogRecord对象"""
        return OperationLogRecord(
            id=row['id'],
            device_id=row['device_id'],
            operation_type=row['operation_type'],
            operation_detail=row['operation_detail'],
            status=row['status'],
            error_message=row['error_message'],
            created_at=datetime.fromisoformat(row['created_at'])
        )

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# 单例实例
_db_manager: Optional[DatabaseManager] = None


def get_database_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """
    获取数据库管理器单例

    Args:
        db_path: 数据库文件路径

    Returns:
        DatabaseManager实例
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager
