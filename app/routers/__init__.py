# ============================================================
# Routers Package - API 路由模块
# ============================================================
# 路由列表:
# - health: 健康检查 (/api/health)
# - config: 系统配置 (/api/config)
# - hopper_4: 料仓设备 (/api/hopper)
# - alarms: 报警管理 (/api/alarms)
# - websocket: WebSocket 实时推送 (/ws)
# ============================================================

from . import health
from . import config
from . import hopper_4
from . import alarms
from . import websocket

__all__ = ['health', 'config', 'hopper_4', 'alarms', 'websocket']

