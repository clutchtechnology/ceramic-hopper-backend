# ============================================================
# Services Package - 业务服务层
# ============================================================
# 服务列表:
# - polling_service: 数据轮询服务
# - history_query_service: 历史数据查询服务
# - plc_service: PLC 通信服务
# - mock_service: Mock 数据生成服务
# - ws_manager: WebSocket 连接管理器
# ============================================================

from .polling_service import (
    start_polling,
    stop_polling,
    get_latest_data,
    get_latest_device_data,
    get_latest_devices_by_type,
    get_latest_timestamp,
    is_polling_running,
    get_polling_stats
)

from .ws_manager import get_ws_manager

from .mock_service import MockService

__all__ = [
    'start_polling',
    'stop_polling',
    'get_latest_data',
    'get_latest_device_data',
    'get_latest_devices_by_type',
    'get_latest_timestamp',
    'is_polling_running',
    'get_polling_stats',
    'get_ws_manager',
    'MockService'
]
