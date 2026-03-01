from datetime import datetime
import logging
from typing import Any, Dict, Optional

from app.alarm_thresholds import AlarmThresholdManager
from app.core.alarm_store import log_alarm

logger = logging.getLogger(__name__)


def check_device_alarm(
    *,
    device_id: str,
    device_type: str,
    modules_data: Dict[str, Any],
    timestamp: Optional[datetime] = None,
) -> None:
    try:
        if device_type == 'hopper_sensor_unit':
            _check_hopper_unit(device_id=device_id, modules_data=modules_data, timestamp=timestamp)
        elif device_type == 'vibration_sensor':
            _check_vibration_unit(device_id=device_id, modules_data=modules_data, timestamp=timestamp)
        else:
            logger.warning(
                '[AlarmChecker] 未识别的 device_type，跳过报警检查: device_id=%s, device_type=%s',
                device_id,
                device_type,
            )
    except Exception as error:
        logger.warning(
            '[AlarmChecker] 报警检查异常: device_id=%s, device_type=%s, modules=%s, error=%s',
            device_id,
            device_type,
            list(modules_data.keys()),
            error,
            exc_info=True,
        )
        return


def _check_hopper_unit(*, device_id: str, modules_data: Dict[str, Any], timestamp: Optional[datetime]) -> None:
    pm10 = modules_data.get('pm10', {}).get('fields', {})
    temperature = modules_data.get('temperature', {}).get('fields', {})
    electricity = modules_data.get('electricity', {}).get('fields', {})

    _check_one(
        device_id=device_id,
        sensor_type='pm10',
        param_name='pm10',
        value=pm10.get('pm10', pm10.get('concentration')),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='temperature',
        param_name='temperature',
        value=temperature.get('temperature'),
        timestamp=timestamp,
    )

    _check_one(device_id=device_id, sensor_type='electricity', param_name='voltage_a', value=electricity.get('Ua_0'), timestamp=timestamp)
    _check_one(device_id=device_id, sensor_type='electricity', param_name='voltage_b', value=electricity.get('Ua_1'), timestamp=timestamp)
    _check_one(device_id=device_id, sensor_type='electricity', param_name='voltage_c', value=electricity.get('Ua_2'), timestamp=timestamp)
    _check_one(device_id=device_id, sensor_type='electricity', param_name='current_a', value=electricity.get('I_0'), timestamp=timestamp)
    _check_one(device_id=device_id, sensor_type='electricity', param_name='current_b', value=electricity.get('I_1'), timestamp=timestamp)
    _check_one(device_id=device_id, sensor_type='electricity', param_name='current_c', value=electricity.get('I_2'), timestamp=timestamp)
    _check_one(device_id=device_id, sensor_type='electricity', param_name='power', value=electricity.get('Pt'), timestamp=timestamp)


def _check_vibration_unit(*, device_id: str, modules_data: Dict[str, Any], timestamp: Optional[datetime]) -> None:
    vibration = modules_data.get('vibration', {}).get('fields', {})
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='speed_x',
        value=_get_field(vibration, 'vx', 'vel_x', 'x_speed'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='speed_y',
        value=_get_field(vibration, 'vy', 'vel_y', 'y_speed'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='speed_z',
        value=_get_field(vibration, 'vz', 'vel_z', 'z_speed'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='displacement_x',
        value=_get_field(vibration, 'dx', 'dis_f_x', 'x_displacement'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='displacement_y',
        value=_get_field(vibration, 'dy', 'dis_f_y', 'y_displacement'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='displacement_z',
        value=_get_field(vibration, 'dz', 'dis_f_z', 'z_displacement'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='freq_x',
        value=_get_field(vibration, 'hzx', 'freq_x'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='freq_y',
        value=_get_field(vibration, 'hzy', 'freq_y'),
        timestamp=timestamp,
    )
    _check_one(
        device_id=device_id,
        sensor_type='vibration',
        param_name='freq_z',
        value=_get_field(vibration, 'hzz', 'freq_z'),
        timestamp=timestamp,
    )


def _get_field(fields: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key in fields and fields[key] is not None:
            return fields[key]
    return None


def _check_one(
    *,
    device_id: str,
    sensor_type: str,
    param_name: str,
    value: Optional[float],
    timestamp: Optional[datetime],
) -> None:
    if value is None:
        return

    manager = AlarmThresholdManager.get_instance()
    level = manager.check_value(param_name, float(value))
    if level != 'alarm':
        return

    config = getattr(manager.thresholds, param_name, None)
    if config is None:
        return
    threshold = config.alarm_max if level == 'alarm' else config.warning_max

    log_alarm(
        device_id=_normalize_alarm_device_id(device_id),
        sensor_type=sensor_type,
        param_name=param_name,
        value=float(value),
        threshold=float(threshold),
        level=level,
        timestamp=timestamp,
    )


def _normalize_alarm_device_id(device_id: str) -> str:
    """统一报警记录设备ID，避免标签格式混用"""
    if device_id.startswith('hopper_'):
        return 'hopper_4'
    return device_id
