from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.alarm_thresholds import AlarmThresholdManager
from app.core.alarm_store import get_alarm_count, log_alarm, query_alarms
from app.models.response import ApiResponse

router = APIRouter(prefix='/alarms', tags=['报警'])


class AlarmReportRequest(BaseModel):
    device_id: str = Field(...)
    sensor_type: str = Field(...)
    level: str = Field(...)
    value: float = Field(...)
    threshold: float = Field(...)
    param_name: Optional[str] = Field(None)
    timestamp: Optional[datetime] = Field(None)


@router.get('/thresholds')
async def get_thresholds():
    try:
        manager = AlarmThresholdManager.get_instance()
        return ApiResponse.ok(manager.get_all())
    except Exception as error:
        return ApiResponse.fail(str(error))


@router.put('/thresholds')
def update_thresholds(body: dict):
    try:
        manager = AlarmThresholdManager.get_instance()
        ok = manager.save(body)
        if ok:
            return ApiResponse.ok({'updated': len(body), 'message': '阈值配置已保存'})
        return ApiResponse.fail('保存阈值配置失败')
    except Exception as error:
        return ApiResponse.fail(str(error))


@router.get('/records')
def get_alarm_records(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    level: Optional[str] = Query('alarm'),
    param_name: Optional[str] = Query(None),
    param_names: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    try:
        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None
        if start:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        if end:
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))

        # 1. 解析逗号分隔的 param_names (多参数一次查询)
        names_list = None
        if param_names:
            names_list = [n.strip() for n in param_names.split(',') if n.strip()]

        records = query_alarms(
            start_time=start_dt,
            end_time=end_dt,
            level=level,
            param_name=param_name,
            param_names=names_list,
            limit=limit,
        )
        return ApiResponse.ok({'records': records, 'count': len(records)})
    except Exception as error:
        return ApiResponse.fail(str(error))


@router.get('/count')
def get_count(hours: int = Query(24, ge=1, le=168)):
    try:
        counts = get_alarm_count(hours=hours)
        return ApiResponse.ok(counts)
    except Exception as error:
        return ApiResponse.fail(str(error))


@router.post('/report')
def report_alarm(request: AlarmReportRequest):
    try:
        if request.level != 'alarm':
            return ApiResponse.fail('仅支持报警级别记录')

        ok = log_alarm(
            device_id=request.device_id,
            sensor_type=request.sensor_type,
            param_name=request.param_name or request.sensor_type,
            value=request.value,
            threshold=request.threshold,
            level=request.level,
            timestamp=request.timestamp,
        )
        if ok:
            return ApiResponse.ok(True)
        return ApiResponse.fail('写入报警记录失败')
    except Exception as error:
        return ApiResponse.fail(str(error))


@router.get('/history')
def get_alarm_history(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    try:
        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None
        if start:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        if end:
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))

        records = query_alarms(start_time=start_dt, end_time=end_dt, limit=limit)
        return ApiResponse.ok({'records': records, 'count': len(records)})
    except Exception as error:
        return ApiResponse.fail(str(error))
