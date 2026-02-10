# ============================================================
# 数据转换工具模块
# ============================================================
# 用于将 PLC 原始数据转换为 InfluxDB 存储字段
#
# 模块列表:
#   - converter_base: 转换器基类
#   - converter_elec: 电表数据转换
#   - converter_temp: 温度传感器数据转换
#   - converter_pm10: PM10粉尘浓度转换
#   - converter_vibration: 振动传感器转换
# ============================================================

from .converter_base import BaseConverter
from .converter_elec import ElectricityConverter
from .converter_temp import TemperatureConverter
from .converter_pm10 import PM10Converter
from .converter_vibration import VibrationConverter

# 模块类型 -> 转换器类 映射
CONVERTER_MAP = {
    # 基础模块名映射 (匹配 plc_modules.yaml)
    "ElectricityMeter": ElectricityConverter,
    "TemperatureSensor": TemperatureConverter,
    "PM10Sensor": PM10Converter,
    "VibrationSelected": VibrationConverter,
    
    # 业务类型名映射 (匹配 config_hopper_4.yaml 中的 module_type)
    "electricity": ElectricityConverter,
    "temperature": TemperatureConverter,
    "pm10": PM10Converter,
    "vibration": VibrationConverter,
}

# 转换器实例缓存 (转换器无状态，可以复用单例)
_converter_cache = {}


def get_converter(module_type: str) -> BaseConverter:
    """根据模块类型获取对应的转换器实例 (单例缓存)"""
    if module_type not in CONVERTER_MAP:
        raise ValueError(f"未知的模块类型: {module_type}")
    
    if module_type not in _converter_cache:
        _converter_cache[module_type] = CONVERTER_MAP[module_type]()
    return _converter_cache[module_type]


__all__ = [
    'BaseConverter',
    'ElectricityConverter',
    'TemperatureConverter',
    'PM10Converter',
    'VibrationConverter',
    'CONVERTER_MAP',
    'get_converter',
]
