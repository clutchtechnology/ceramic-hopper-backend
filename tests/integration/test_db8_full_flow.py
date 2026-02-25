"""
DB8 料仓数据 - 完整流程测试
流程: 原始字节 → 解析 → 转换 → 存储 → API验证
"""
import asyncio
import struct
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any

# 添加项目根目录到路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.plc.parser_hopper import HopperParser
from app.tools import get_converter
from app.core.influxdb import write_point, get_influx_client
from config import get_settings

settings = get_settings()

# API 基础地址
API_BASE = "http://localhost:8080"


# ============================================================
# 1. 生成 DB8 测试数据 (626 字节)
# ============================================================
def generate_db8_test_data() -> bytes:
    """生成 DB8 料仓测试数据
    
    DB8 结构 (626 字节):
    - 短料仓 x4 (72字节/个 = 288字节): WeighSensor(14) + Temp(2) + Meter(56)
    - 无料仓 x2 (58字节/个 = 116字节): Temp(2) + Meter(56)
    - 长料仓 x3 (74字节/个 = 222字节): WeighSensor(14) + Temp(2) + Temp(2) + Meter(56)
    """
    data = bytearray(626)
    
    def write_weigh_sensor(offset: int, gross: int, net: int, status: int = 0x0080):
        """写入称重模块 (14字节)"""
        # GrossWeight_W (Word, 2)
        struct.pack_into('>H', data, offset, gross & 0xFFFF)
        # NetWeight_W (Word, 2)
        struct.pack_into('>H', data, offset + 2, net & 0xFFFF)
        # StatusWord (Word, 2)
        struct.pack_into('>H', data, offset + 4, status)
        # GrossWeight (DWord, 4)
        struct.pack_into('>I', data, offset + 6, gross)
        # NetWeight (DWord, 4)
        struct.pack_into('>I', data, offset + 10, net)
    
    def write_temp_sensor(offset: int, temp: int):
        """写入温度模块 (2字节)"""
        struct.pack_into('>H', data, offset, temp)
    
    def write_electricity_meter(offset: int, 
                                 uab: tuple = (380.0, 381.0, 379.0),
                                 ua: tuple = (220.0, 221.0, 219.0),
                                 i: tuple = (10.0, 11.0, 9.5),
                                 pt: float = 5.5,
                                 pa: float = 1.8,
                                 pb: float = 1.9,
                                 pc: float = 1.8,
                                 impep: float = 1234.5):
        """写入电表模块 (56字节)"""
        # Uab_0, Uab_1, Uab_2 (3 x Real = 12)
        struct.pack_into('>f', data, offset, uab[0])
        struct.pack_into('>f', data, offset + 4, uab[1])
        struct.pack_into('>f', data, offset + 8, uab[2])
        # Ua_0, Ua_1, Ua_2 (3 x Real = 12)
        struct.pack_into('>f', data, offset + 12, ua[0])
        struct.pack_into('>f', data, offset + 16, ua[1])
        struct.pack_into('>f', data, offset + 20, ua[2])
        # I_0, I_1, I_2 (3 x Real = 12)
        struct.pack_into('>f', data, offset + 24, i[0])
        struct.pack_into('>f', data, offset + 28, i[1])
        struct.pack_into('>f', data, offset + 32, i[2])
        # Pt, Pa, Pb, Pc (4 x Real = 16)
        struct.pack_into('>f', data, offset + 36, pt)
        struct.pack_into('>f', data, offset + 40, pa)
        struct.pack_into('>f', data, offset + 44, pb)
        struct.pack_into('>f', data, offset + 48, pc)
        # ImpEp (Real = 4)
        struct.pack_into('>f', data, offset + 52, impep)
    
    # ============================================================
    # 短料仓 x4 (偏移 0-287)
    # ============================================================
    for i in range(4):
        base = i * 72
        write_weigh_sensor(base, gross=5000 + i * 100, net=4800 + i * 100)
        write_temp_sensor(base + 14, temp=250 + i * 10)  # 25.0°C ~ 28.0°C
        write_electricity_meter(
            base + 16,
            pt=5.0 + i * 0.5,
            impep=1000.0 + i * 100
        )
    
    # ============================================================
    # 无料仓 x2 (偏移 288-403)
    # ============================================================
    for i in range(2):
        base = 288 + i * 58
        write_temp_sensor(base, temp=300 + i * 10)  # 30.0°C ~ 31.0°C
        write_electricity_meter(
            base + 2,
            pt=3.0 + i * 0.5,
            impep=500.0 + i * 50
        )
    
    # ============================================================
    # 长料仓 x3 (偏移 404-625)
    # ============================================================
    for i in range(3):
        base = 404 + i * 74
        write_weigh_sensor(base, gross=8000 + i * 200, net=7500 + i * 200)
        write_temp_sensor(base + 14, temp=280 + i * 5)   # temp1
        write_temp_sensor(base + 16, temp=275 + i * 5)   # temp2
        write_electricity_meter(
            base + 18,
            pt=8.0 + i * 0.5,
            impep=2000.0 + i * 200
        )
    
    print(f"✅ 生成 DB8 测试数据: {len(data)} 字节")
    return bytes(data)


# ============================================================
# 2. 解析测试数据
# ============================================================
def parse_db8_data(raw_data: bytes) -> list:
    """使用 HopperParser 解析 DB8 数据"""
    parser = HopperParser()
    devices = parser.parse_all(raw_data)
    
    print(f"\n📦 解析结果: {len(devices)} 个设备")
    for device in devices:
        print(f"   - {device['device_id']}: {len(device['modules'])} 个模块")
    
    return devices


# ============================================================
# 3. 转换并写入 InfluxDB
# ============================================================
def convert_and_write(devices: list, db_number: int = 8):
    """转换数据并写入 InfluxDB"""
    timestamp = datetime.now()
    write_count = 0
    
    # 历史重量缓存 (用于计算下料速度)
    weight_history = {}
    
    for device in devices:
        device_id = device['device_id']
        device_type = device['device_type']
        
        for module_tag, module_data in device['modules'].items():
            module_type = module_data['module_type']
            raw_fields = module_data['fields']
            
            # 使用转换器
            try:
                converter = get_converter(module_type)
                
                if module_type == 'WeighSensor':
                    cache_key = f"{device_id}:{module_tag}"
                    previous_weight = weight_history.get(cache_key)
                    fields = converter.convert(
                        raw_fields,
                        previous_weight=previous_weight,
                        interval=5
                    )
                    weight_history[cache_key] = fields.get('weight', 0.0)
                else:
                    fields = converter.convert(raw_fields)
                
            except Exception as e:
                print(f"     转换失败 {module_type}: {e}")
                continue
            
            if not fields:
                continue
            
            # 写入 InfluxDB
            write_point(
                measurement="sensor_data",
                tags={
                    "device_id": device_id,
                    "device_type": device_type,
                    "module_type": module_type,
                    "module_tag": module_tag,
                    "db_number": str(db_number)
                },
                fields=fields,
                timestamp=timestamp
            )
            write_count += 1
    
    print(f"\n💾 写入 InfluxDB: {write_count} 条记录")
    return write_count


# ============================================================
# 4. 验证 API
# ============================================================
async def verify_api():
    """验证料仓 API 能否返回数据"""
    print("\n🔍 验证 API...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 4.1 测试 /api/hopper/list
        print("\n   [1] GET /api/hopper/list")
        try:
            resp = await client.get(f"{API_BASE}/api/hopper/list")
            data = resp.json()
            if data.get('success'):
                devices = data.get('data', [])
                print(f"       ✅ 成功! 返回 {len(devices)} 个设备")
                for d in devices[:3]:
                    print(f"          - {d.get('device_id')}")
                if len(devices) > 3:
                    print(f"          ... 还有 {len(devices) - 3} 个")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.2 测试 /api/hopper/{device_id}
        print("\n   [2] GET /api/hopper/short_hopper_1")
        try:
            resp = await client.get(f"{API_BASE}/api/hopper/short_hopper_1")
            data = resp.json()
            if data.get('success'):
                device_data = data.get('data', {})
                modules = device_data.get('modules', {})
                print(f"       ✅ 成功! 返回 {len(modules)} 个模块")
                for tag, mod in modules.items():
                    fields = mod.get('fields', {})
                    print(f"          - {tag}: {list(fields.keys())[:4]}...")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.3 测试 /api/hopper/{device_id}/history
        print("\n   [3] GET /api/hopper/short_hopper_1/history")
        try:
            resp = await client.get(
                f"{API_BASE}/api/hopper/short_hopper_1/history",
                params={"module_type": "WeighSensor"}
            )
            data = resp.json()
            if data.get('success'):
                records = data.get('data', [])
                print(f"       ✅ 成功! 返回 {len(records)} 条记录")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")


# ============================================================
# 5. 主测试流程
# ============================================================
def main():
    print("=" * 70)
    print("DB8 料仓数据 - 完整流程测试")
    print("=" * 70)
    print("流程: 原始字节 → 解析 → 转换 → 存储 → API验证")
    print("=" * 70)
    
    # Step 1: 生成测试数据
    print("\n📝 Step 1: 生成 DB8 测试数据")
    raw_data = generate_db8_test_data()
    
    # 打印前 82 字节 (第一个设备)
    print("\n   前 82 字节 (short_hopper_1):")
    for i in range(0, 82, 16):
        chunk = raw_data[i:i+16]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        print(f"   [{i:4d}] {hex_str}")
    
    # Step 2: 解析数据
    print("\n📦 Step 2: 解析 DB8 数据")
    devices = parse_db8_data(raw_data)
    
    # 打印第一个设备的详细数据
    if devices:
        first_device = devices[0]
        print(f"\n   示例 - {first_device['device_id']}:")
        for tag, mod in first_device['modules'].items():
            print(f"   [{tag}] {mod['module_type']}:")
            for field_name, field_info in list(mod['fields'].items())[:3]:
                print(f"      {field_name}: {field_info['value']} {field_info.get('unit', '')}")
    
    # Step 3: 转换并写入
    print("\n💾 Step 3: 转换并写入 InfluxDB")
    write_count = convert_and_write(devices)
    
    # Step 4: 验证 API (需要服务运行)
    print("\n🔍 Step 4: 验证 API (需要 main.py 运行)")
    try:
        asyncio.run(verify_api())
    except Exception as e:
        print(f"     API 验证跳过 (服务未运行): {e}")
    
    print("\n" + "=" * 70)
    print("✅ DB8 完整流程测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
