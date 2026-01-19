# ============================================================
# 文件说明: parser_hopper_sensor.py - 料仓传感器数据解析器 (DB4)
# ============================================================
# 专门用于解析 DB4 这种单设备多模块的数据结构
# ============================================================

import struct
import yaml
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

class HopperSensorParser:
    """料仓传感器数据解析器 (DB4)"""
    
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    def __init__(self, 
                 config_path: str = None,
                 module_config_path: str = None):
        """初始化解析器"""
        self.config_path = Path(config_path) if config_path else self.PROJECT_ROOT / "configs" / "config_hopper_4.yaml"
        self.module_config_path = Path(module_config_path) if module_config_path else self.PROJECT_ROOT / "configs" / "plc_modules.yaml"
        
        self.config = None
        self.base_modules = {}
        self.load_config()
        
    def load_config(self):
        """加载配置"""
        # 加载基础模块配置
        with open(self.module_config_path, 'r', encoding='utf-8') as f:
            module_config = yaml.safe_load(f)
            for module in module_config.get('modules', []):
                self.base_modules[module['name']] = module
                
        # 加载DB配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        print(f"✅ HopperSensorParser 初始化完成: DB{self.config.get('db_number')}, 总大小{self.config.get('total_size')}字节")

    def parse_module(self, module_info: Dict, data: bytes) -> Dict[str, Any]:
        """解析单个模块"""
        base_module_name = module_info['base_module']
        offset = module_info['offset']
        size = module_info['size']
        
        if base_module_name not in self.base_modules:
            # 如果找不到基础模块，尝试用默认解析或报错
            print(f"⚠️ 未找到基础模块定义: {base_module_name}")
            return {}
            
        base_module = self.base_modules[base_module_name]
        module_data = data[offset : offset + size]
        
        parsed_fields = {}
        for field in base_module['fields']:
            field_offset = field['offset']
            data_type = field['data_type']
            field_name = field['name']
            
            try:
                val = 0
                # 简单的类型解析
                if data_type == 'Word':
                    val = struct.unpack('>H', module_data[field_offset:field_offset+2])[0]
                elif data_type == 'DWord':
                    val = struct.unpack('>I', module_data[field_offset:field_offset+4])[0]
                elif data_type == 'Int':
                    val = struct.unpack('>h', module_data[field_offset:field_offset+2])[0]
                elif data_type == 'DInt':
                    val = struct.unpack('>i', module_data[field_offset:field_offset+4])[0]
                elif data_type == 'Real':
                    val = struct.unpack('>f', module_data[field_offset:field_offset+4])[0]
                elif data_type == 'Bool':
                     # 简单处理Bool，假设它是一个字节中的某一位，这里简化处理，需完善
                     byte_val = module_data[field_offset]
                     bit_offset = field.get('bit', 0)
                     val = bool(byte_val & (1 << bit_offset))
                
                scale = field.get('scale', 1.0)
                if isinstance(val, (int, float)):
                    val = val * scale
                    
                parsed_fields[field_name] = {
                    'value': val,
                    'display_name': field.get('display_name', field_name),
                    'unit': field.get('unit', '')
                }
            except Exception as e:
                print(f"⚠️ 解析字段失败 {base_module_name}.{field_name}: {e}")
                
        return {
            'module_type': module_info['module_type'],
            'base_module': base_module_name,
            'description': module_info.get('description', ''),
            'fields': parsed_fields
        }

    def parse_all(self, db_data: bytes) -> List[Dict[str, Any]]:
        """解析所有数据"""
        # 这里我们将整个DB视为一个设备
        device_result = {
            'device_id': 'hopper_sensors_db4', # 虚拟设备ID
            'device_name': '料仓传感器综合监测',
            'device_type': 'hopper_sensor_unit',
            'timestamp': datetime.now().isoformat(),
            'modules': {}
        }
        
        for module in self.config.get('modules', []):
            module_type = module['module_type'] # 作为key
            parsed = self.parse_module(module, db_data)
            device_result['modules'][module_type] = parsed
            
        return [device_result]

    def get_device_list(self) -> List[Dict[str, str]]:
        return [{
            'device_id': 'hopper_sensors_db4',
            'device_name': '料仓传感器综合监测',
            'device_type': 'hopper_sensor_unit',
            'category': 'sensor_unit'
        }]
