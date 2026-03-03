# ============================================================
# 温度传感器转换器 (TemperatureSensor)
# ============================================================
# 存储字段: temperature (C)
# 转换公式: temperature = raw * 250 / 27683
# ============================================================

from typing import Dict, Any
from .converter_base import BaseConverter


class TemperatureConverter(BaseConverter):
    """
    温度传感器数据转换器
    
    输入字段 (PLC原始):
        - Temperature: 温度原始值 (SINT16 有符号16位整数)
    
    输出字段 (存储):
        - temperature: 当前温度 (C)
    
    转换公式:
        temperature = raw_value * 250 / 27683
        例如: PLC 存储 27683 表示实际温度 250.0C
              PLC 存储 11073 表示实际温度 100.0C
    
    数据类型说明:
        SINT16 范围: -32768 ~ 32767
    """
    
    MODULE_TYPE = "TemperatureSensor"
    
    OUTPUT_FIELDS = {
        "temperature": {"display_name": "当前温度", "unit": "C"},
    }
    
    # 温度转换系数: raw * 250 / 27683
    SCALE_NUMERATOR = 250.0
    SCALE_DENOMINATOR = 27683.0
    
    def convert(self, raw_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        转换温度传感器数据
        
        转换公式: temperature = raw * 250 / 27683
        """
        # 获取原始温度值 (SINT16)
        raw_temp = self.get_field_value(raw_data, "Temperature", 0)
        
        # 确保是数值类型
        if isinstance(raw_temp, float):
            raw_temp = int(raw_temp)
        
        # 应用转换公式: raw * 250 / 27683
        temperature = raw_temp * self.SCALE_NUMERATOR / self.SCALE_DENOMINATOR
        
        # 修正异常负温度: 传感器故障时取绝对值
        if temperature < -10.0:
            temperature = abs(temperature)
        
        return {
            "temperature": round(temperature, 1),
        }
