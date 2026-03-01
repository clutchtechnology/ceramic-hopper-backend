"""
Mock 数据生成服务 - 料仓监控系统

用于开发和测试环境，生成模拟的料仓传感器数据
"""

import random
from datetime import datetime
from typing import Dict, Any
from config import get_settings


class MockService:
    """Mock 数据生成服务"""

    @staticmethod
    def generate_hopper_data() -> Dict[str, Any]:
        """生成料仓实时数据
        
        Returns:
            料仓设备数据字典
        """
        timestamp = datetime.now().isoformat()
        settings = get_settings()

        # 1. 速度/频率在高精度模式下会额外缩放：
        #    速度 = raw / 100, 频率 = raw / 10
        #    为了确保无论精度模式如何都能触发报警，按模式生成不同原始值。
        if settings.vib_high_precision:
            speed_x_raw = 1200.0  # -> 12.0 mm/s (> 10)
            speed_y_raw = 1300.0
            speed_z_raw = 1250.0
            freq_x_raw = 650.0    # -> 65.0 Hz (> 60)
            freq_y_raw = 670.0
            freq_z_raw = 660.0
        else:
            speed_x_raw = 12.0    # 直接使用原始值 (> 10)
            speed_y_raw = 13.0
            speed_z_raw = 12.5
            freq_x_raw = 65.0     # 直接使用原始值 (> 60)
            freq_y_raw = 67.0
            freq_z_raw = 66.0
        
        # 1. 生成 4号料仓数据 - DB4 (PM10/温度/电表)
        hopper_data = {
            "hopper_unit_4": {
                "device_id": "hopper_unit_4",
                "device_name": "4号料仓综合监测单元",
                "device_type": "hopper_sensor_unit",
                "timestamp": timestamp,
                "modules": {
                    # PM10 粉尘浓度 (真实值，无需缩放)
                    "pm10": {
                        "module_type": "pm10",
                        "fields": {
                            # 报警阈值 alarm_max=150
                            "PM10": {"value": round(random.uniform(180.0, 230.0), 1)}
                        }
                    },
                    # 温度传感器 (raw * 0.1 = C)
                    "temperature": {
                        "module_type": "temperature",
                        "fields": {
                            # 报警阈值 alarm_max=80 -> raw > 800
                            "Temperature": {"value": random.randint(900, 1050)}
                        }
                    },
                    # 三相电表 (PLC原始值)
                    "electricity": {
                        "module_type": "electricity",
                        "fields": {
                            # 电压报警阈值 420V -> raw > 4200
                            "Ua_0": {"value": random.randint(4300, 4500)},
                            "Ua_1": {"value": random.randint(4300, 4500)},
                            "Ua_2": {"value": random.randint(4300, 4500)},
                            # 电流报警阈值 80A, 计算: raw*0.001*20 -> raw > 4000
                            "I_0": {"value": random.randint(4200, 4600)},
                            "I_1": {"value": random.randint(4200, 4600)},
                            "I_2": {"value": random.randint(4200, 4600)},
                            # 功率报警阈值 15kW, 计算: raw*0.001*20 -> raw > 750
                            "Pt": {"value": random.randint(900, 1100)},
                            # 能耗 raw * 2 = kWh (500~1000 -> 1000~2000kWh)
                            "ImpEp": {"value": random.randint(500, 1000)},
                        }
                    },
                }
            },
            # 2. 生成振动传感器数据 - DB6 (独立设备)
            "hopper_vib_6": {
                "device_id": "hopper_vib_6",
                "device_name": "4号料仓振动传感器",
                "device_type": "vibration_sensor",
                "timestamp": timestamp,
                "modules": {
                    "vibration": {
                        "module_type": "vibration",
                        "fields": {
                            # 速度报警阈值 10
                            "VX": {"value": speed_x_raw},
                            "VY": {"value": speed_y_raw},
                            "VZ": {"value": speed_z_raw},
                            # 位移报警阈值 500
                            "DX": {"value": round(random.uniform(530.0, 580.0), 2)},
                            "DY": {"value": round(random.uniform(530.0, 580.0), 2)},
                            "DZ": {"value": round(random.uniform(530.0, 580.0), 2)},
                            # 频率报警阈值 60
                            "HZX": {"value": freq_x_raw},
                            "HZY": {"value": freq_y_raw},
                            "HZZ": {"value": freq_z_raw},
                        }
                    }
                }
            }
        }
        
        return hopper_data

