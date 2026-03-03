from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.influxdb import get_influx_client, write_point
from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_MEASUREMENT = 'alarm_logs'
_ALARM_DEDUP_SECONDS = 60
_last_alarms: Dict[str, datetime] = {}


def log_alarm(
    *,
    device_id: str,
    sensor_type: str,
    param_name: str,
    value: float,
    threshold: float,
    level: str,
    timestamp: Optional[datetime] = None,
) -> bool:
    if level != 'alarm':
        return False

    dedup_key = f'{device_id}_{param_name}_{level}'
    now = datetime.now(timezone.utc)
    last = _last_alarms.get(dedup_key)
    if last is not None and (now - last).total_seconds() < _ALARM_DEDUP_SECONDS:
        return False

    _last_alarms[dedup_key] = now
    ts = timestamp if timestamp is not None else now

    tags = {
        'device_id': device_id,
        'sensor_type': sensor_type,
        'param_name': param_name,
        'level': level,
    }
    fields = {
        'value': float(value),
        'threshold': float(threshold),
    }

    return write_point(_MEASUREMENT, tags, fields, ts)


def query_alarms(
    *,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    level: Optional[str] = None,
    param_name: Optional[str] = None,
    param_names: Optional[List[str]] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    if start_time is None:
        start_time = now - timedelta(hours=24)
    if end_time is None:
        end_time = now

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    effective_level = level if level else 'alarm'
    level_filter = f'  |> filter(fn: (r) => r["level"] == "{effective_level}")'

    # 1. param_names 优先 (多参数一次查询): contains() Flux 过滤
    # 2. 如果只有单个 param_name 则用简单等式过滤
    if param_names and len(param_names) > 0:
        names_flux = ', '.join(f'"{n}"' for n in param_names)
        param_filter = f'  |> filter(fn: (r) => contains(value: r["param_name"], set: [{names_flux}]))'
    elif param_name:
        param_filter = f'  |> filter(fn: (r) => r["param_name"] == "{param_name}")'
    else:
        param_filter = ''

    query = f'''
from(bucket: "{settings.influx_bucket}")
  |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
  |> filter(fn: (r) => r["_measurement"] == "{_MEASUREMENT}")
{level_filter}
{param_filter}
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {limit})
'''

    try:
        client = get_influx_client()
        tables = client.query_api().query(query)
        results: List[Dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                results.append(
                    {
                        'time': record.get_time().isoformat(),
                        'device_id': record.values.get('device_id', ''),
                        'sensor_type': record.values.get('sensor_type', ''),
                        'param_name': record.values.get('param_name', ''),
                        'level': record.values.get('level', ''),
                        'value': record.values.get('value'),
                        'threshold': record.values.get('threshold'),
                    }
                )
        return results
    except Exception as error:
        logger.warning(
            '[AlarmStore] query_alarms 查询异常: measurement=%s, start=%s, end=%s, level=%s, param_name=%s, limit=%s, error=%s',
            _MEASUREMENT,
            start_time.isoformat(),
            end_time.isoformat(),
            effective_level,
            param_name,
            limit,
            error,
            exc_info=True,
        )
        return []


def get_alarm_count(*, hours: int = 24) -> Dict[str, int]:
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    query = f'''
from(bucket: "{settings.influx_bucket}")
  |> range(start: {start_time.isoformat()}, stop: {now.isoformat()})
  |> filter(fn: (r) => r["_measurement"] == "{_MEASUREMENT}")
  |> filter(fn: (r) => r["level"] == "alarm")
  |> filter(fn: (r) => r["_field"] == "value")
  |> count()
'''

    try:
        client = get_influx_client()
        tables = client.query_api().query(query)
        # warning 统一为 0: 当前只记录 alarm 级别, 保留字段以兼容前端 AlarmCount 模型
        counts = {'warning': 0, 'alarm': 0, 'total': 0}
        for table in tables:
            for record in table.records:
                count = int(record.get_value() or 0)
                counts['alarm'] += count
        counts['total'] = counts['alarm']
        return counts
    except Exception as error:
        logger.warning(
            '[AlarmStore] get_alarm_count 查询异常: measurement=%s, hours=%s, start=%s, end=%s, error=%s',
            _MEASUREMENT,
            hours,
            start_time.isoformat(),
            now.isoformat(),
            error,
            exc_info=True,
        )
        # warning 统一为 0: 当前只记录 alarm 级别, 保留字段以兼容前端 AlarmCount 模型
        return {'warning': 0, 'alarm': 0, 'total': 0}
