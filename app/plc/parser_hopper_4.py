# ============================================================
# 文件说明: parser_hopper_4.py - 4号料仓传感器综合数据解析器 (DB4)
# ============================================================
# 专门用于解析 DB4 这种单设备多模块的数据结构
# 包含 PM10、温度、电表、三轴振动等传感器
# ============================================================

import struct
import yaml
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

class Hopper4Parser:
    """料仓传感器综合解析器 (DB4)
    
    负责解析 DB4 中的所有传感器模块:
    - PM10 粉尘浓度 (PM10Sensor)
    - 温度传感器 (TemperatureSensor)
    - 三相电表 (ElectricityMeter)
    - 三轴振动核心指标 (VibrationSelected)
    """
    
    # 项目根目录 (ceramic-hopper-backend/)
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    def __init__(self, 
                 config_path: str = None,
                 module_config_path: str = None):
        """初始化解析器
        
        Args:
            config_path: DB4 配置文件路径
            module_config_path: 基础模块模板路径
        """
        # 默认路径指向 configs/config_hopper_4.yaml
        self.config_path = Path(config_path) if config_path else self.PROJECT_ROOT / "configs" / "config_hopper_4.yaml"
        self.module_config_path = Path(module_config_path) if module_config_path else self.PROJECT_ROOT / "configs" / "plc_modules.yaml"
        
        self.config = None
        self.base_modules = {}
        self.load_config()
        
    def load_config(self):
        """加载配置"""
        try:
            # 1. 加载基础模块定义
            if not self.module_config_path.exists():
                print(f"[Parser] 基础模块配置不存在: {self.module_config_path}")
            else:
                with open(self.module_config_path, 'r', encoding='utf-8') as f:
                    module_config = yaml.safe_load(f)
                    for module in module_config.get('modules', []):
                        self.base_modules[module['name']] = module
                    
            # 2. 加载 DB4 结构配置
            if not self.config_path.exists():
                print(f"[Parser] DB4 配置文件不存在: {self.config_path}")
            else:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
            
            db_num = self.config.get('db_number', 4) if self.config else 4
            size = self.config.get('total_size', 176) if self.config else 176
            print(f"[Parser] Hopper4Parser 初始化完成: DB{db_num}, 总大小{size}字节")
        except Exception as e:
            print(f"[Parser] Hopper4Parser 加载配置失败: {e}")

    def _parse_field_value(self, module_data: bytes, field: Dict[str, Any]) -> Any:
        """解析单个字段的基础数据类型"""
        offset = field['offset']
        data_type = field['data_type']
        
        try:
            # S7-1200 使用大端序 (Big Endian)
            if data_type == 'Word' or data_type == 'WORD':
                val = struct.unpack('>H', module_data[offset:offset+2])[0]
            elif data_type == 'DWord' or data_type == 'DWORD':
                val = struct.unpack('>I', module_data[offset:offset+4])[0]
            elif data_type == 'Int' or data_type == 'INT':
                val = struct.unpack('>h', module_data[offset:offset+2])[0]
            elif data_type == 'DInt' or data_type == 'DINT':
                val = struct.unpack('>i', module_data[offset:offset+4])[0]
            elif data_type == 'Real' or data_type == 'REAL':
                val = struct.unpack('>f', module_data[offset:offset+4])[0]
            elif data_type == 'Bool' or data_type == 'BOOL':
                bit_offset = field.get('bit', 0)
                byte_val = module_data[offset]
                val = bool(byte_val & (1 << bit_offset))
            else:
                val = 0
                
            # 应用缩放
            scale = field.get('scale', 1.0)
            if isinstance(val, (int, float)):
                val = val * scale
            return val
        except Exception:
            return 0

    def parse_module(self, module_info: Dict, db_data: bytes) -> Dict[str, Any]:
        """解析单个模块的所有字段"""
        base_module_name = module_info['base_module']
        offset = module_info['offset']
        size = module_info['size']
        
        if base_module_name not in self.base_modules:
            print(f"[Parser] 未找到基础模块定义: {base_module_name}")
            return {}
            
        base_module = self.base_modules[base_module_name]
        
        # 边界检查
        if offset + size > len(db_data):
            print(f"[Parser] 模块偏移越界: {base_module_name} (offset {offset}, size {size})")
            return {}
            
        module_data = db_data[offset : offset + size]
        
        parsed_fields = {}
        for field in base_module.get('fields', []):
            val = self._parse_field_value(module_data, field)
            parsed_fields[field['name']] = {
                'value': val,
                'display_name': field.get('display_name', field['name']),
                'unit': field.get('unit', '')
            }
                
        return {
            'module_type': module_info['module_type'],
            'base_module': base_module_name,
            'description': module_info.get('description', ''),
            'fields': parsed_fields
        }

    def parse_all(self, db_data: bytes) -> List[Dict[str, Any]]:
        """解析所有模块数据
        
        Returns:
            List[Dict]: 列表格式，保持与 PollingService 兼容。
            DB4 作为一个综合设备返回。
        """
        if not self.config:
            return []
            
        device_result = {
            'device_id': 'hopper_unit_4',
            'device_name': '4号料仓综合监测单元',
            'device_type': 'hopper_sensor_unit',
            'timestamp': datetime.now().isoformat(),
            'modules': {}
        }
        
        # 遍历配置文件中的模块定义
        for module in self.config.get('modules', []):
            module_tag = module['module_type'] # 作为识别标签
            parsed = self.parse_module(module, db_data)
            if parsed:
                device_result['modules'][module_tag] = parsed
            
        return [device_result]

    def get_device_list(self) -> List[Dict[str, str]]:
        """获取设备基本信息"""
        return [{
            'device_id': 'hopper_unit_4',
            'device_name': '4号料仓综合监测单元',
            'device_type': 'hopper_sensor_unit',
            'category': 'sensor_unit'
        }]
