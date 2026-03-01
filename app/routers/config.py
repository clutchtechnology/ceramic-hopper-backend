# ============================================================
# 文件说明: config.py - 系统配置路由
# ============================================================
# 接口列表:
# 1. GET /server            - 获取服务器配置
# 2. GET /plc               - 获取PLC配置
# 3. PUT /plc               - PLC配置写入（禁用，只读）
# 4. POST /plc/test         - 测试PLC连接
# 5. GET /database          - 获取数据库配置
# ============================================================

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from config import get_settings
from app.models.response import ApiResponse

router = APIRouter()
settings = get_settings()

# 运行时 PLC 配置（支持热更新）
_runtime_plc_config = {
    "ip_address": settings.plc_ip,
    "rack": settings.plc_rack,
    "slot": settings.plc_slot,
    "timeout_ms": settings.plc_timeout,
    "poll_interval": settings.plc_poll_interval
}


def get_runtime_plc_config():
    """获取运行时 PLC 配置"""
    return _runtime_plc_config.copy()


# 配置更新模型
class PLCConfigUpdate(BaseModel):
    ip_address: Optional[str] = None
    rack: Optional[int] = None
    slot: Optional[int] = None
    timeout_ms: Optional[int] = None
    poll_interval: Optional[float] = None


# ------------------------------------------------------------
# 1. GET /server - 获取服务器配置
# ------------------------------------------------------------
@router.get("/server")
async def get_server_config():
    """获取服务器配置"""
    return ApiResponse.ok({
        "host": settings.server_host,
        "port": settings.server_port,
        "debug": settings.debug
    })


# ------------------------------------------------------------
# 2. GET /plc - 获取PLC配置
# ------------------------------------------------------------
@router.get("/plc")
async def get_plc_config():
    """获取PLC配置（返回运行时配置）"""
    return ApiResponse.ok(get_runtime_plc_config())


# ------------------------------------------------------------
# 3. PUT /plc - PLC配置写入（禁用，只读）
# ------------------------------------------------------------
@router.put(
    "/plc",
    summary="PLC配置写入（禁用）",
    description="该接口已禁用。PLC配置为只读，请在后端 .env 文件中修改后重启服务使其生效。",
    responses={
        403: {
            "description": "写入被拒绝：PLC配置只读",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "error": "PLC配置为只读，请修改后端 .env 文件并重启服务后生效"
                    }
                }
            }
        }
    },
)
async def update_plc_config(config: PLCConfigUpdate):
    """PLC 配置只读：拒绝写入"""
    return JSONResponse(
        status_code=403,
        content=ApiResponse.fail("PLC配置为只读，请修改后端 .env 文件并重启服务后生效").model_dump(),
    )


# ------------------------------------------------------------
# 4. POST /plc/test - 测试PLC连接
# ------------------------------------------------------------
@router.post("/plc/test")
async def test_plc_connection():
    """测试PLC连接（使用当前运行时配置）"""
    try:
        from app.plc.s7_client import get_s7_client
        client = get_s7_client()
        if not client.is_connected():
            client.connect()

        plc_config = get_runtime_plc_config()
        return ApiResponse.ok({
            "success": client.is_connected(),
            "message": "PLC连接成功" if client.is_connected() else "PLC连接失败",
            "plc_ip": plc_config["ip_address"]
        })
    except Exception as e:
        plc_config = get_runtime_plc_config()
        return ApiResponse.fail(f"PLC连接失败: {str(e)}")


@router.get("/database")
async def get_database_config():
    """获取数据库配置"""
    return ApiResponse.ok({
        "influx_url": settings.influx_url,
        "influx_org": settings.influx_org,
        "influx_bucket": settings.influx_bucket
    })

