# ============================================================
# 文件说明: plc_service.py - 兼容层（已精简）
# ============================================================
# 说明:
# - 旧 PLCService 属于历史 HTTP 方案，当前主链路已迁移到 polling_service + WebSocket。
# - 本文件保留最小兼容能力，避免外部旧导入立即失败。
# ============================================================

from datetime import datetime
from typing import Dict, Any, Optional

from app.services.polling_service import get_latest_data


class PLCService:
    """旧 PLCService 兼容层（仅返回内存缓存数据）"""

    def read_device_data(self, device_type: str, device_id: int) -> Dict[str, Any]:
        """按旧签名读取设备数据（从 polling 内存缓存映射）"""
        latest_data = get_latest_data()

        # 常见旧键推断
        key_candidates = [
            f"{device_type}_{device_id}",
            f"{device_type}{device_id}",
            str(device_id),
        ]

        for key in key_candidates:
            if key in latest_data:
                return latest_data[key]

        # 兜底：按 device_type 匹配首个设备
        for device in latest_data.values():
            if isinstance(device, dict) and device.get("device_type") == device_type:
                return device

        return {
            "timestamp": datetime.now().isoformat(),
            "error": f"Device {device_type} #{device_id} not found in polling cache"
        }
