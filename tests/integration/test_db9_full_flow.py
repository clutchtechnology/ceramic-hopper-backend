"""
DB9 辊道窑数据 - 完整流程测试
流程: 原始字节 → 解析 → 转换 → 存储 → API验证
"""
import asyncio
import struct
import httpx
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.plc.parser_roller_kiln import RollerKilnParser
from app.tools import get_converter
from app.core.influxdb import write_point
from config import get_settings

settings = get_settings()

# API 基础地址
API_BASE = "http://localhost:8080"


# ============================================================
# 1. 生成 DB9 测试数据 (348 字节)
# ============================================================
def generate_db9_test_data() -> bytes:
    """生成 DB9 辊道窑测试数据
    
    DB9 结构 (348 字节):
    - 6个温度传感器 (2字节/个 = 12字节): zone1_temp ~ zone6_temp
    - 6个电表 (56字节/个 = 336字节): main_meter, zone1_meter ~ zone5_meter
    """
    data = bytearray(348)
    
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
        # Uab_0, Uab_1, Uab_2
        struct.pack_into('>f', data, offset, uab[0])
        struct.pack_into('>f', data, offset + 4, uab[1])
        struct.pack_into('>f', data, offset + 8, uab[2])
        # Ua_0, Ua_1, Ua_2
        struct.pack_into('>f', data, offset + 12, ua[0])
        struct.pack_into('>f', data, offset + 16, ua[1])
        struct.pack_into('>f', data, offset + 20, ua[2])
        # I_0, I_1, I_2
        struct.pack_into('>f', data, offset + 24, i[0])
        struct.pack_into('>f', data, offset + 28, i[1])
        struct.pack_into('>f', data, offset + 32, i[2])
        # Pt, Pa, Pb, Pc
        struct.pack_into('>f', data, offset + 36, pt)
        struct.pack_into('>f', data, offset + 40, pa)
        struct.pack_into('>f', data, offset + 44, pb)
        struct.pack_into('>f', data, offset + 48, pc)
        # ImpEp
        struct.pack_into('>f', data, offset + 52, impep)
    
    # ============================================================
    # 6个温度传感器 (偏移 0-11)
    # ============================================================
    zone_temps = [850, 920, 980, 1050, 1100, 950]  # 各温区温度 (x10)
    for i, temp in enumerate(zone_temps):
        write_temp_sensor(i * 2, temp)
    
    # ============================================================
    # 6个电表 (偏移 12-347)
    # ============================================================
    meter_powers = [50.0, 12.0, 15.0, 18.0, 20.0, 10.0]  # 功率 kW
    meter_energies = [50000.0, 10000.0, 12000.0, 15000.0, 18000.0, 8000.0]  # 电能 kWh
    
    for i in range(6):
        offset = 12 + i * 56
        write_electricity_meter(
            offset,
            pt=meter_powers[i],
            impep=meter_energies[i]
        )
    
    print(f"✅ 生成 DB9 测试数据: {len(data)} 字节")
    return bytes(data)


# ============================================================
# 2. 解析测试数据
# ============================================================
def parse_db9_data(raw_data: bytes) -> list:
    """使用 RollerKilnParser 解析 DB9 数据"""
    parser = RollerKilnParser()
    devices = parser.parse_all(raw_data)
    
    print(f"\n📦 解析结果: {len(devices)} 个设备")
    for device in devices:
        print(f"   - {device['device_id']}: {len(device['modules'])} 个模块")
    
    return devices


# ============================================================
# 3. 转换并写入 InfluxDB
# ============================================================
def convert_and_write(devices: list, db_number: int = 9):
    """转换数据并写入 InfluxDB"""
    timestamp = datetime.now()
    write_count = 0
    
    for device in devices:
        device_id = device['device_id']
        device_type = device['device_type']
        
        for module_tag, module_data in device['modules'].items():
            module_type = module_data['module_type']
            raw_fields = module_data['fields']
            
            try:
                converter = get_converter(module_type)
                fields = converter.convert(raw_fields)
            except Exception as e:
                print(f"     转换失败 {module_type}: {e}")
                continue
            
            if not fields:
                continue
            
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
    """验证辊道窑 API 能否返回数据"""
    print("\n🔍 验证 API...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 4.1 测试 /api/roller/info
        print("\n   [1] GET /api/roller/info")
        try:
            resp = await client.get(f"{API_BASE}/api/roller/info")
            data = resp.json()
            if data.get('success'):
                info = data.get('data', {})
                print(f"       ✅ 成功! 辊道窑信息: {info.get('device_name', 'N/A')}")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.2 测试 /api/roller/realtime
        print("\n   [2] GET /api/roller/realtime")
        try:
            resp = await client.get(f"{API_BASE}/api/roller/realtime")
            data = resp.json()
            if data.get('success'):
                device_data = data.get('data', {})
                modules = device_data.get('modules', {})
                print(f"       ✅ 成功! 返回 {len(modules)} 个模块")
                # 显示温区数据
                for tag in ['zone1_temp', 'zone2_temp', 'zone3_temp']:
                    if tag in modules:
                        temp = modules[tag].get('fields', {}).get('temperature', 'N/A')
                        print(f"          - {tag}: {temp}°C")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.3 测试 /api/roller/zone/{zone_id}
        print("\n   [3] GET /api/roller/zone/zone1")
        try:
            resp = await client.get(f"{API_BASE}/api/roller/zone/zone1")
            data = resp.json()
            if data.get('success'):
                zone_data = data.get('data', {})
                print(f"       ✅ 成功! zone1 数据:")
                print(f"          温度: {zone_data.get('temperature', 'N/A')}°C")
                print(f"          功率: {zone_data.get('power', 'N/A')} kW")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.4 测试 /api/roller/history
        print("\n   [4] GET /api/roller/history")
        try:
            resp = await client.get(
                f"{API_BASE}/api/roller/history",
                params={"module_type": "TemperatureSensor"}
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
    print("DB9 辊道窑数据 - 完整流程测试")
    print("=" * 70)
    print("流程: 原始字节 → 解析 → 转换 → 存储 → API验证")
    print("=" * 70)
    
    # Step 1: 生成测试数据
    print("\n📝 Step 1: 生成 DB9 测试数据")
    raw_data = generate_db9_test_data()
    
    # 打印前 68 字节 (6个温度 + 1个电表)
    print("\n   前 68 字节 (6个温度 + main_meter):")
    for i in range(0, 68, 16):
        chunk = raw_data[i:i+16]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        print(f"   [{i:4d}] {hex_str}")
    
    # Step 2: 解析数据
    print("\n📦 Step 2: 解析 DB9 数据")
    devices = parse_db9_data(raw_data)
    
    # 打印设备详细数据
    if devices:
        device = devices[0]
        print(f"\n   示例 - {device['device_id']}:")
        for tag, mod in list(device['modules'].items())[:4]:
            print(f"   [{tag}] {mod['module_type']}:")
            for field_name, field_info in list(mod['fields'].items())[:2]:
                print(f"      {field_name}: {field_info['value']} {field_info.get('unit', '')}")
    
    # Step 3: 转换并写入
    print("\n💾 Step 3: 转换并写入 InfluxDB")
    write_count = convert_and_write(devices)
    
    # Step 4: 验证 API
    print("\n🔍 Step 4: 验证 API (需要 main.py 运行)")
    try:
        asyncio.run(verify_api())
    except Exception as e:
        print(f"     API 验证跳过 (服务未运行): {e}")
    
    print("\n" + "=" * 70)
    print("✅ DB9 完整流程测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
