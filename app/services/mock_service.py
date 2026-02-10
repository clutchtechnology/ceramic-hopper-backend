"""
Mock 数据生成服务 - 料仓监控系统

用于开发和测试环境，生成模拟的料仓传感器数据
"""

import random
from datetime import datetime
from typing import Dict, Any


class MockService:
    """Mock 数据生成服务"""

    @staticmethod
    def generate_hopper_data() -> Dict[str, Any]:
        """生成料仓实时数据
        
        Returns:
            料仓设备数据字典
        """
        timestamp = datetime.now().isoformat()
        
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
                            "PM10": {"value": round(random.uniform(30.0, 80.0), 1)}
                        }
                    },
                    # 温度传感器 (raw * 0.1 = C)
                    "temperature": {
                        "module_type": "temperature",
                        "fields": {
                            "Temperature": {"value": random.randint(200, 350)}
                        }
                    },
                    # 三相电表 (PLC原始值)
                    "electricity": {
                        "module_type": "electricity",
                        "fields": {
                            # 电压 raw * 0.1 = V (3750~3850 -> 375~385V)
                            "Ua_0": {"value": random.randint(3750, 3850)},
                            "Ua_1": {"value": random.randint(3750, 3850)},
                            "Ua_2": {"value": random.randint(3750, 3850)},
                            # 电流 raw * 0.001 * 20 = A (500~750 -> 10~15A)
                            "I_0": {"value": random.randint(500, 750)},
                            "I_1": {"value": random.randint(500, 750)},
                            "I_2": {"value": random.randint(500, 750)},
                            # 功率 raw * 0.001 * 20 = kW (225~325 -> 4.5~6.5kW)
                            "Pt": {"value": random.randint(225, 325)},
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
                            # 速度幅值 (mm/s)
                            "VX": {"value": round(random.uniform(1.5, 3.0), 2)},
                            "VY": {"value": round(random.uniform(1.5, 3.0), 2)},
                            "VZ": {"value": round(random.uniform(1.0, 2.5), 2)},
                            # 位移幅值 (um)
                            "DX": {"value": round(random.uniform(30.0, 60.0), 2)},
                            "DY": {"value": round(random.uniform(30.0, 60.0), 2)},
                            "DZ": {"value": round(random.uniform(25.0, 55.0), 2)},
                            # 频率 (Hz)
                            "HZX": {"value": round(random.uniform(48.0, 52.0), 1)},
                            "HZY": {"value": round(random.uniform(48.0, 52.0), 1)},
                            "HZZ": {"value": round(random.uniform(48.0, 52.0), 1)},
                        }
                    }
                }
            }
        }
        
        return hopper_data

