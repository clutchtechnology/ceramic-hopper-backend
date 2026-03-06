# ============================================================
# 文件说明: health.py - 健康检查路由
# ============================================================
# 接口列表:
# 1. GET /health            - 系统健康检查
# 2. GET /health/plc        - PLC连接状态
# 3. GET /health/database   - 数据库连接状态
# 4. GET /health/polling    - 轮询服务状态
# ============================================================

import asyncio
from fastapi import APIRouter
from datetime import datetime

from app.models.response import ApiResponse
from app.services.polling_service import get_polling_stats, is_polling_running

router = APIRouter(prefix="/api", tags=["health"])


# ------------------------------------------------------------
# 1. GET /health - 系统健康检查
# ------------------------------------------------------------
@router.get("/health")
async def health_check():
    """系统健康检查"""
    return ApiResponse.ok({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


# ------------------------------------------------------------
# 2. GET /health/plc - PLC连接状态（实时检测）
# ------------------------------------------------------------
@router.get("/health/plc")
async def plc_health(probe: bool = True):
    """PLC连接状态检查
    
    [FIX] 改为 async def + asyncio.to_thread()，避免同步 PLC 调用阻塞事件循环
    
    Args:
        probe: 是否进行实时探测（默认 True）
               - True: 实时调用 snap7 检测 PLC 是否在线
               - False: 只返回内部状态变量（更快，但可能不准确）
    
    Returns:
        connected: 实时连接状态
        internal_state: 内部状态变量（调试用）
    """
    try:
        from app.plc.plc_manager import get_plc_manager
        plc = get_plc_manager()
        # [FIX] 同步 snap7 调用放到线程池，不阻塞事件循环
        status = await asyncio.to_thread(plc.get_status, check_realtime=probe)
        
        return ApiResponse.ok({
            "connected": status["connected"],
            "internal_state": status.get("internal_state", status["connected"]),
            "plc_ip": status["ip"],
            "rack": status["rack"],
            "slot": status["slot"],
            "connect_count": status["connect_count"],
            "error_count": status["error_count"],
            "last_error": status["last_error"],
            "last_connect_time": status["last_connect_time"],
            "last_read_time": status["last_read_time"],
            "snap7_available": status["snap7_available"],
            "message": "PLC连接正常" if status["connected"] else "PLC未连接或已断开"
        })
    except Exception as e:
        return ApiResponse.fail(f"PLC连接检查失败: {str(e)}")


# ------------------------------------------------------------
# 3. GET /health/database - 数据库连接状态
# ------------------------------------------------------------
@router.get("/health/database")
async def database_health():
    """数据库连接状态检查
    
    [FIX] 改为 async def + asyncio.to_thread()，避免同步 InfluxDB 调用阻塞事件循环
    """
    status = {
        "influxdb": {"connected": False}
    }
    
    # [FIX] 检查InfluxDB - 在线程池中执行同步网络 I/O
    try:
        from app.core.influxdb import check_influx_health
        healthy, msg = await asyncio.to_thread(check_influx_health)
        status["influxdb"]["connected"] = healthy
        if not healthy:
            status["influxdb"]["error"] = msg
    except Exception as e:
        status["influxdb"]["error"] = str(e)
    
    all_healthy = all(db["connected"] for db in status.values())
    
    return ApiResponse.ok({
        "status": "healthy" if all_healthy else "degraded",
        "databases": status
    })


# ------------------------------------------------------------
# 4. GET /health/polling - 轮询服务状态
# ------------------------------------------------------------
@router.get("/health/polling")
async def polling_health():
    """轮询服务状态检查

    [FIX] get_polling_stats() 内部调用 plc.get_status() 会获取 _rw_lock + snap7,
    以及 local_cache.get_stats() 涉及 SQLite 读取,
    在线程池中执行避免阻塞事件循环
    """
    try:
        stats = await asyncio.to_thread(get_polling_stats)
        return ApiResponse.ok({
            "polling_running": is_polling_running(),
            **stats
        })
    except Exception as e:
        return ApiResponse.fail(f"轮询状态检查失败: {str(e)}")


# ------------------------------------------------------------
# 5. GET /health/diagnose - 全面诊断（排查全0数据问题）

# ------------------------------------------------------------
# 6. GET /health/latest-timestamp - 获取数据库中最新数据的时间戳
# ------------------------------------------------------------
@router.get("/health/latest-timestamp")
async def get_latest_timestamp():
    """获取数据库中最新数据的时间戳
    
    [FIX] 改为 async def + asyncio.to_thread()，避免同步 InfluxDB 查询阻塞事件循环
    
    用于前端确定历史数据查询的时间范围。
    返回数据库中最新写入的数据的时间戳。
    
    Returns:
        timestamp: 最新数据的ISO格式时间戳
        timestamp_utc: UTC时间戳
    """
    try:
        from app.services.history_query_service import get_history_service
        service = get_history_service()
        # [FIX] InfluxDB 查询在线程池中执行
        latest_time = await asyncio.to_thread(service.get_latest_db_timestamp)
        
        if latest_time:
            return ApiResponse.ok({
                "timestamp": latest_time.isoformat(),
                "timestamp_utc": latest_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "has_data": True
            })
        else:
            return ApiResponse.ok({
                "timestamp": None,
                "timestamp_utc": None,
                "has_data": False,
                "message": "数据库中暂无数据"
            })
    except Exception as e:
        return ApiResponse.fail(f"获取最新时间戳失败: {str(e)}")
