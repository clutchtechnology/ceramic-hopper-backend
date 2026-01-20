# ============================================================
# PM10 粉尘浓度转换器 (PM10Sensor)
# ============================================================
# 存储字段: concentration (μg/m³)
# ============================================================

from typing import Dict, Any
from .converter_base import BaseConverter


class PM10Converter(BaseConverter):
    """PM10 粉尘浓度数据转换器
    
    手册结论:
    - PM2.5/PM10/PM1.0 寄存器为“真实值”，无需再缩放
    - 单位: μg/m³
    """
    
    MODULE_TYPE = "PM10Sensor"
    
    OUTPUT_FIELDS = {
        "pm10": {"display_name": "PM10", "unit": "μg/m³"},
        "pm2_5": {"display_name": "PM2.5", "unit": "μg/m³"},
        "pm1_0": {"display_name": "PM1.0", "unit": "μg/m³"},
        "concentration": {"display_name": "粉尘浓度", "unit": "μg/m³"},
    }
    
    def convert(self, raw_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """转换 PM 数据（手册：真实值，无需缩放）"""
        fields: Dict[str, Any] = {}
        
        # 常见字段名
        pm10 = self.get_field_value(raw_data, "PM10", None)
        pm2_5 = self.get_field_value(raw_data, "PM2_5", None)
        if pm2_5 is None:
            pm2_5 = self.get_field_value(raw_data, "PM2.5", None)
        pm1_0 = self.get_field_value(raw_data, "PM1_0", None)
        if pm1_0 is None:
            pm1_0 = self.get_field_value(raw_data, "PM1.0", None)

        # 兼容旧字段名
        if pm10 is None:
            pm10 = self.get_field_value(raw_data, "Concentration", None)

        if pm10 is not None:
            fields["pm10"] = round(float(pm10), 1)
            fields["concentration"] = round(float(pm10), 1)
        if pm2_5 is not None:
            fields["pm2_5"] = round(float(pm2_5), 1)
        if pm1_0 is not None:
            fields["pm1_0"] = round(float(pm1_0), 1)

        if not fields:
            fields["concentration"] = 0.0

        return fields
