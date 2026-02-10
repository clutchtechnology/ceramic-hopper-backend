# ============================================================
# 振动传感器转换器 (Vibration) - DB6 数据
# ============================================================
# 三组核心数据: V_xyz (速度), D_xyz (位移), HZ_xyz (频率)
#
# 精度模式 (由 .env 的 VIB_HIGH_PRECISION 控制):
#   低精度 (false): V/D/HZ 均直接使用 PLC 原始值
#   高精度 (true):  V = 原始值 (mm/s)
#                   D = 原始值 / 100 (um)
#                   HZ = 原始值 (Hz)
# ============================================================

import logging
from typing import Dict, Any
from .converter_base import BaseConverter

logger = logging.getLogger(__name__)


class VibrationConverter(BaseConverter):
    """振动传感器数据转换器 (DB6 vibration 模块)"""
    
    MODULE_TYPE = "vibration"
    
    # 有效值范围校验
    VALID_RANGES = {
        "velocity": (0, 100),       # mm/s
        "displacement": (0, 600),   # um
        "frequency": (0, 10000),    # Hz
    }
    
    OUTPUT_FIELDS = {
        "vx": {"display_name": "X轴速度幅值", "unit": "mm/s"},
        "vy": {"display_name": "Y轴速度幅值", "unit": "mm/s"},
        "vz": {"display_name": "Z轴速度幅值", "unit": "mm/s"},
        "dx": {"display_name": "X轴位移幅值", "unit": "um"},
        "dy": {"display_name": "Y轴位移幅值", "unit": "um"},
        "dz": {"display_name": "Z轴位移幅值", "unit": "um"},
        "hzx": {"display_name": "X轴频率", "unit": "Hz"},
        "hzy": {"display_name": "Y轴频率", "unit": "Hz"},
        "hzz": {"display_name": "Z轴频率", "unit": "Hz"},
    }
    
    def __init__(self):
        super().__init__()
        # 从配置中读取精度模式
        from config import get_settings
        self._high_precision = get_settings().vib_high_precision
        mode_str = "高精度" if self._high_precision else "低精度"
        logger.info(f"[VibrationConverter] 精度模式: {mode_str}")
    
    def _validate(self, value, range_key: str, decimals: int) -> float:
        """验证数值范围"""
        if value is None:
            return None
        val = float(value)
        min_val, max_val = self.VALID_RANGES[range_key]
        if not (min_val <= val <= max_val):
            logger.warning(f"{range_key}异常: {val} (有效范围: {min_val}-{max_val})")
        return round(val, decimals)
    
    def convert(self, raw_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """转换振动三组核心数据
        
        低精度: V/D/HZ 均直接使用原始值
        高精度: V = 原始值, D = 原始值/100, HZ = 原始值
        """
        fields: Dict[str, Any] = {}

        def _set(output_key: str, field_name: str, range_key: str, decimals: int, divisor: float = 1.0):
            value = self.get_field_value(raw_data, field_name, None)
            if value is not None:
                value = float(value) / divisor
                fields[output_key] = self._validate(value, range_key, decimals)

        # 1. 速度幅值 (mm/s) - 直接使用原始值
        _set("vx", "VX", "velocity", 2)
        _set("vy", "VY", "velocity", 2)
        _set("vz", "VZ", "velocity", 2)
        
        # 2. 位移幅值 (um) - 高精度模式: /100
        d_divisor = 100.0 if self._high_precision else 1.0
        _set("dx", "DX", "displacement", 2, d_divisor)
        _set("dy", "DY", "displacement", 2, d_divisor)
        _set("dz", "DZ", "displacement", 2, d_divisor)
        
        # 3. 频率 (Hz) - 直接使用原始值
        _set("hzx", "HZX", "frequency", 1)
        _set("hzy", "HZY", "frequency", 1)
        _set("hzz", "HZZ", "frequency", 1)

        return fields
