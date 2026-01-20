from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from app.core.influxdb import write_alarm, query_alarms

router = APIRouter(
    prefix="/alarms",
    tags=["alarms"],
    responses={404: {"description": "Not found"}},
)

# ------------------------------------------------------------
# Models
# ------------------------------------------------------------
class AlarmReportRequest(BaseModel):
    device_id: str = Field(..., description="设备ID (例: hopper_1)")
    sensor_type: str = Field(..., description="传感器类型 (pm10, temperature, vibration, electricity)")
    level: str = Field(..., description="报警级别 (warning, alarm)")
    value: float = Field(..., description="触发报警的当前值")
    threshold: float = Field(..., description="触发报警的阈值")
    message: str = Field(..., description="报警描述信息")
    timestamp: Optional[datetime] = Field(None, description="报警发生时间(可选, 默认当前)")

class AlarmRecord(BaseModel):
    time: datetime
    device_id: str
    sensor_type: str
    level: str
    value: float
    threshold: float
    message: str

# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

@router.post("/report", response_model=bool, summary="上报报警记录 (供前端调用)")
async def report_alarm(request: AlarmReportRequest):
    """
    前端监测到数值超过阈值时，调用此接口上报报警记录。
    后端将其存储到 InfluxDB 的 alarm_events 表中。
    """
    success = write_alarm(
        device_id=request.device_id,
        sensor_type=request.sensor_type,
        level=request.level,
        value=request.value,
        threshold=request.threshold,
        message=request.message,
        timestamp=request.timestamp
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to write alarm to database")
    
    return True

@router.get("/history", response_model=List[AlarmRecord], summary="查询报警历史记录")
async def get_alarm_history(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100
):
    """
    查询历史报警记录，默认最近24小时。
    """
    if not end:
        end = datetime.now(timezone.utc)
    if not start:
        start = end - timedelta(hours=24)
        
    alarms = query_alarms(
        start_time=start,
        end_time=end,
        limit=limit
    )
    
    return alarms
