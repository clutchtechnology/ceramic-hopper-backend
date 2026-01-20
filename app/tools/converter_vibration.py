# ============================================================
# 振动传感器转换器 (Vibration) - DB4 专用
# ============================================================
# 说明:
#   - 基础缩放由 plc_modules.yaml 的 scale 完成
#   - 本转换器添加量程模式支持和数值校验
#   - 字段名严格遵循 PLC 工程师的 DB4 定义（有注释的字段）
# ============================================================
# 传感器规格参考（寄存器协议）:
#   DX~DZ (寄存器地址 65~67):
#     - 模式1: 60000μm量程, 1μm分辨率   → DX = (DXH << 8) | DXL
#     - 模式2: 600μm量程, 0.01μm分辨率 → DX = ((DXH << 8) | DXL) / 100
#   HZX~HZZ (寄存器地址 68~70):
#     - 计算公式: HZX(Hz) = ((HZXH << 8) | HZXL) / 10
# ============================================================

from typing import Dict, Any
from .converter_base import BaseConverter


class VibrationConverter(BaseConverter):
    """振动传感器数据转换器 (DB4 VibrationSelected)
    
    只保留 PLC 工程师标注的核心指标（有注释的字段）:
    - 位移幅值: DX/DY/DZ (μm) - 支持双量程模式
    - 频率: HZX/HZY/HZZ (Hz) - 自动 /10 转换
    - 加速度峰值: KX (X轴), AAVGY (Y轴), AAVGZ (Z轴) (m/s²)
    - 速度RMS: VRMSX (X轴), VRMSY (Y轴), VRMGZ (Z轴) (mm/s)
    
    量程模式配置:
    - DISPLACEMENT_MODE = 'high_range'  # 60000μm量程, 1μm分辨率 (默认)
    - DISPLACEMENT_MODE = 'high_precision'  # 600μm量程, 0.01μm分辨率
    """
    
    MODULE_TYPE = "VibrationSelected"
    
    # ========== 量程模式配置 ==========
    # 根据实际传感器配置选择
    # 'high_range': 60000μm量程, 1μm分辨率 (scale=1.0)
    # 'high_precision': 600μm量程, 0.01μm分辨率 (scale=0.01)
    DISPLACEMENT_MODE = 'high_range'  # 默认使用高量程模式
    
    # ========== 有效值范围校验 (根据传感器规格书) ==========
    VALID_RANGES = {
        # 位移幅值 (μm)
        "displacement": {
            "high_range": (0, 60000),       # 60000μm量程
            "high_precision": (0, 600)      # 600μm量程
        },
        # 频率 (Hz) - 典型工业设备振动频率
        "frequency": (0, 10000),
        # 加速度峰值 (m/s²) - 典型范围
        "acceleration": (0, 100),
        # 速度RMS (mm/s) - 根据ISO 10816标准
        "velocity": (0, 50),
    }
    
    OUTPUT_FIELDS = {
        # 位移幅值 (μm) - 寄存器地址 65~67 (0x41~0x43)
        "dx": {"display_name": "X轴振动位移幅值", "unit": "μm", "reg_addr": 65},
        "dy": {"display_name": "Y轴振动位移幅值", "unit": "μm", "reg_addr": 66},
        "dz": {"display_name": "Z轴振动位移幅值", "unit": "μm", "reg_addr": 67},
        
        # 频率 (Hz) - 寄存器地址 68~70 (0x44~0x46)
        "freq_x": {"display_name": "X轴振动频率", "unit": "Hz", "reg_addr": 68},
        "freq_y": {"display_name": "Y轴振动频率", "unit": "Hz", "reg_addr": 69},
        "freq_z": {"display_name": "Z轴振动频率", "unit": "Hz", "reg_addr": 70},
        
        # 加速度峰值 (m/s²)
        "acc_peak_x": {"display_name": "X轴加速度峰值", "unit": "m/s²"},
        "acc_peak_y": {"display_name": "Y轴加速度峰值", "unit": "m/s²"},
        "acc_peak_z": {"display_name": "Z轴加速度峰值", "unit": "m/s²"},
        
        # 速度RMS (mm/s)
        "vrms_x": {"display_name": "X轴速度RMS值", "unit": "mm/s"},
        "vrms_y": {"display_name": "Y轴速度RMS值", "unit": "mm/s"},
        "vrms_z": {"display_name": "Z轴速度RMS值", "unit": "mm/s"},
    }
    
    def _validate_and_convert_displacement(self, value: float) -> float:
        """验证并转换位移值（支持双量程模式）
        
        Args:
            value: 从 PLC 读取的原始值 (已经过 plc_modules.yaml scale 处理)
        
        Returns:
            转换后的位移值 (μm)
        
        计算公式:
            - high_range 模式: DX = (DXH << 8) | DXL (scale=1.0)
            - high_precision 模式: DX = ((DXH << 8) | DXL) / 100 (scale=0.01)
        """
        if value is None:
            return None
        
        # 如果 plc_modules.yaml 中已经设置了 scale=0.01，
        # 则 value 已经是除以100后的值，无需再次处理
        # 这里只做范围校验
        min_val, max_val = self.VALID_RANGES["displacement"][self.DISPLACEMENT_MODE]
        
        if not (min_val <= value <= max_val):
            # 数值超出量程，可能是传感器故障或配置错误
            # 记录警告但仍返回原值（避免丢失数据）
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"位移值超出量程: {value}μm (有效范围: {min_val}-{max_val}μm, "
                f"模式: {self.DISPLACEMENT_MODE})"
            )
        
        return round(value, 2)  # 保留2位小数
    
    def _validate_frequency(self, value: float) -> float:
        """验证频率值
        
        计算公式: HZX(Hz) = ((HZXH << 8) | HZXL) / 10
        注意: plc_modules.yaml 中 scale=0.1 已完成 /10 转换
        """
        if value is None:
            return None
        
        min_val, max_val = self.VALID_RANGES["frequency"]
        if not (min_val <= value <= max_val):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"频率值异常: {value}Hz (有效范围: {min_val}-{max_val}Hz)")
        
        return round(value, 1)  # 保留1位小数
    
    def _validate_acceleration(self, value: float) -> float:
        """验证加速度值"""
        if value is None:
            return None
        
        min_val, max_val = self.VALID_RANGES["acceleration"]
        if not (min_val <= value <= max_val):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"加速度值异常: {value}m/s² (有效范围: {min_val}-{max_val}m/s²)")
        
        return round(value, 2)
    
    def _validate_velocity(self, value: float) -> float:
        """验证速度RMS值"""
        if value is None:
            return None
        
        min_val, max_val = self.VALID_RANGES["velocity"]
        if not (min_val <= value <= max_val):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"速度RMS值异常: {value}mm/s (有效范围: {min_val}-{max_val}mm/s)")
        
        return round(value, 1)
    
    def convert(self, raw_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """转换振动核心指标数据（仅保留 PLC 工程师标注字段）
        
        处理流程:
        1. plc_modules.yaml 中定义的 scale 已完成基础转换
        2. 本方法添加量程模式支持和数值校验
        3. 对超出范围的值记录警告但保留原值
        """
        fields: Dict[str, Any] = {}

        def _set_if_present(output_key: str, field_name: str, validator=None) -> None:
            value = self.get_field_value(raw_data, field_name, None)
            if value is not None:
                # 应用验证器（如果提供）
                if validator:
                    value = validator(value)
                fields[output_key] = value

        # ========== 位移幅值 (μm) - 寄存器 65~67 ==========
        # 计算公式见传感器规格书
        _set_if_present("dx", "DX", self._validate_and_convert_displacement)
        _set_if_present("dy", "DY", self._validate_and_convert_displacement)
        _set_if_present("dz", "DZ", self._validate_and_convert_displacement)
        
        # ========== 频率 (Hz) - 寄存器 68~70 ==========
        # 计算公式: HZX = ((HZXH << 8) | HZXL) / 10
        _set_if_present("freq_x", "HZX", self._validate_frequency)
        _set_if_present("freq_y", "HZY", self._validate_frequency)
        _set_if_present("freq_z", "HZZ", self._validate_frequency)
        
        # ========== 加速度峰值 (m/s²) ==========
        _set_if_present("acc_peak_x", "KX", self._validate_acceleration)
        _set_if_present("acc_peak_y", "AAVGY", self._validate_acceleration)
        _set_if_present("acc_peak_z", "AAVGZ", self._validate_acceleration)
        
        # ========== 速度RMS (mm/s) ==========
        _set_if_present("vrms_x", "VRMSX", self._validate_velocity)
        _set_if_present("vrms_y", "VRMSY", self._validate_velocity)
        _set_if_present("vrms_z", "VRMGZ", self._validate_velocity)

        # 兼容性处理: 如果没有匹配到标准字段，尝试提取所有原始字段
        if not fields:
            for k, v in raw_data.items():
                if isinstance(v, dict) and 'value' in v:
                    fields[k.lower()] = v['value']
                elif isinstance(v, (int, float)):
                    fields[k.lower()] = v

        return fields
