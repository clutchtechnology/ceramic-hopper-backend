"""
WebSocket 消息模型 - 料仓监控系统

消息类型:
    - subscribe / unsubscribe: 客户端订阅/取消订阅
    - heartbeat: 心跳消息
    - realtime_data: 实时数据推送
    - error: 错误消息
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============================================================
# 客户端 -> 服务端消息
# ============================================================
class SubscribeMessage(BaseModel):
    """订阅消息"""
    type: Literal["subscribe"] = "subscribe"
    channel: Literal["realtime"]


class UnsubscribeMessage(BaseModel):
    """取消订阅消息"""
    type: Literal["unsubscribe"] = "unsubscribe"
    channel: Literal["realtime"]


class HeartbeatMessage(BaseModel):
    """心跳消息"""
    type: Literal["heartbeat"] = "heartbeat"
    timestamp: Optional[str] = None


# ============================================================
# 服务端 -> 客户端消息
# ============================================================
class ModuleData(BaseModel):
    """模块数据"""
    module_type: str = Field(..., description="模块类型")
    fields: Dict[str, float] = Field(default_factory=dict, description="字段数据")


class HopperDeviceData(BaseModel):
    """料仓设备数据"""
    device_id: str = Field(..., description="设备ID")
    device_name: str = Field(..., description="设备名称")
    device_type: str = Field(..., description="设备类型")
    timestamp: str = Field(..., description="时间戳")
    modules: Dict[str, ModuleData] = Field(default_factory=dict, description="模块数据")


class RealtimeDataMessage(BaseModel):
    """实时数据推送消息"""
    type: Literal["realtime_data"] = "realtime_data"
    success: bool = True
    timestamp: str = Field(..., description="ISO 8601 时间戳")
    source: Literal["plc", "mock"] = Field(default="plc", description="数据来源")
    data: Dict[str, HopperDeviceData] = Field(
        default_factory=dict, 
        description="设备数据字典 {device_id: device_data}"
    )


# ============================================================
# 错误消息
# ============================================================
class ErrorMessage(BaseModel):
    """错误消息"""
    type: Literal["error"] = "error"
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误描述")


# ============================================================
# 错误码枚举
# ============================================================
class ErrorCode:
    """常用错误码"""
    PLC_DISCONNECTED = "PLC_DISCONNECTED"
    DB_ERROR = "DB_ERROR"
    INVALID_CHANNEL = "INVALID_CHANNEL"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_MESSAGE = "INVALID_MESSAGE"

