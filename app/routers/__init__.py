# ============================================================
# Routers Package - API 路由模块
# ============================================================
# 路由列表:
# - health: 健康检查 (/api/health)
# - config: 系统配置 (/api/config)
# - hopper_4: 料仓设备 (/api/hopper)
# ============================================================

from . import health
from . import config
from . import hopper_4
from . import alarms

__all__ = ['health', 'config', 'hopper_4', 'alarms']

