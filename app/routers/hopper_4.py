# 4号料仓设备API路由

from fastapi import APIRouter, Query, Path
from typing import Optional
from datetime import datetime, timedelta

from app.models.response import ApiResponse
from app.services.history_query_service import get_history_service
from app.services.polling_service import (
    get_latest_data,
    get_latest_timestamp,
    is_polling_running
)

router = APIRouter(prefix="/api/hopper", tags=["料仓设备"])

HOPPER_TYPES = ["hopper_sensor_unit"]


# ============================================================
# 1. GET /api/hopper/realtime/batch - 批量获取所有料仓实时数据（内存缓存）
# ============================================================
@router.get("/realtime/batch")
async def get_all_hoppers_realtime():
    """批量获取所有料仓实时数据（从内存缓存读取）

    **返回字段说明**
    - 电表模块 (module_type = electricity): Pt, ImpEp, Ua_0, I_0, I_1, I_2
    - 振动模块 (module_type = vibration_selected):
      - 速度幅值: vx, vy, vz
      - 速度RMS: vrms_x, vrms_y, vrms_z
      - 波峰因素: cf_x, cf_y, cf_z
      - 峭度: k_x, k_y, k_z
      - 频率: freq_x, freq_y, freq_z
      - 温度: temperature
      - 故障诊断: err_x, err_y, err_z
    """
    try:
        all_data = get_latest_data()
        devices_data = [
            data for data in all_data.values()
            if data.get("device_type") in HOPPER_TYPES
        ]

        if not devices_data:
            return ApiResponse.ok({
                "total": 0,
                "source": "cache",
                "timestamp": get_latest_timestamp(),
                "polling_running": is_polling_running(),
                "warning": "缓存为空，轮询服务可能未启动或首次轮询未完成",
                "devices": []
            })

        return ApiResponse.ok({
            "total": len(devices_data),
            "source": "cache",
            "timestamp": get_latest_timestamp(),
            "polling_running": is_polling_running(),
            "devices": devices_data
        })
    except Exception as e:
        return ApiResponse.fail(f"批量查询失败: {str(e)}")


# ============================================================
# 2. GET /api/hopper/{device_id}/history - 获取料仓历史数据（InfluxDB）
# ============================================================
@router.get("/{device_id}/history")
async def get_hopper_history(
    device_id: str = Path(..., description="设备ID", example="hopper_unit_4"),
    start: Optional[datetime] = Query(None, description="开始时间", example="2026-01-20T00:00:00"),
    end: Optional[datetime] = Query(None, description="结束时间", example="2026-01-20T23:59:59"),
    module_type: Optional[str] = Query(
        None,
        description="模块类型筛选",
        enum=["pm10", "temperature", "electricity", "vibration_selected"],
        example="vibration_selected"
    ),
    fields: Optional[str] = Query(None, description="字段筛选 (逗号分隔)", example="vrms_x,vrms_y,vrms_z"),
    interval: Optional[str] = Query("5m", description="聚合间隔", example="5m")
):
    """获取料仓历史数据（按 tag 查询）

    **电表字段**: Pt, ImpEp, Ua_0, I_0, I_1, I_2
    **振动字段**: vx, vy, vz, vrms_x, vrms_y, vrms_z, cf_x, cf_y, cf_z,
                 k_x, k_y, k_z, freq_x, freq_y, freq_z, temperature,
                 err_x, err_y, err_z
    """
    try:
        if not start:
            start = datetime.now() - timedelta(hours=1)
        if not end:
            end = datetime.now()

        field_list = fields.split(",") if fields else None

        data = get_history_service().query_device_history(
            device_id=device_id,
            start=start,
            end=end,
            module_type=module_type,
            fields=field_list,
            interval=interval
        )

        return ApiResponse.ok({
            "device_id": device_id,
            "time_range": {
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "interval": interval,
            "data": data
        })
    except Exception as e:
        return ApiResponse.fail(f"查询失败: {str(e)}")
