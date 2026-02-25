"""
DB10 SCR/风机数据 - 完整流程测试
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

from app.plc.parser_scr_fan import SCRFanParser
from app.tools import get_converter
from app.core.influxdb import write_point
from config import get_settings

settings = get_settings()

# API 基础地址
API_BASE = "http://localhost:8080"


# ============================================================
# 1. 生成 DB10 测试数据 (244 字节)
# ============================================================
def generate_db10_test_data() -> bytes:
    """生成 DB10 SCR/风机测试数据
    
    DB10 结构 (244 字节):
    - SCR x2 (66字节/个 = 132字节): FlowMeter(10) + ElectricityMeter(56)
    - 风机 x2 (56字节/个 = 112字节): ElectricityMeter(56)
    """
    data = bytearray(244)
    
    def write_flow_meter(offset: int, rt_flow: int, total_flow: int, milli: int = 500):
        """写入流量计模块 (10字节)"""
        # RtFlow (DWord, 4) - 实时流量 L/min
        struct.pack_into('>I', data, offset, rt_flow)
        # TotalFlow (DWord, 4) - 累计流量 m³
        struct.pack_into('>I', data, offset + 4, total_flow)
        # TotalFlowMilli (Word, 2) - 累计流量小数 mL
        struct.pack_into('>H', data, offset + 8, milli)
    
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
    # SCR x2 (偏移 0-131)
    # ============================================================
    scr_flows = [(1500, 12345), (1800, 15678)]  # (实时流量L/min, 累计流量m³)
    scr_powers = [25.0, 30.0]
    scr_energies = [8000.0, 9500.0]
    
    for i in range(2):
        base = i * 66
        write_flow_meter(base, rt_flow=scr_flows[i][0], total_flow=scr_flows[i][1])
        write_electricity_meter(
            base + 10,
            pt=scr_powers[i],
            impep=scr_energies[i]
        )
    
    # ============================================================
    # 风机 x2 (偏移 132-243)
    # ============================================================
    fan_powers = [15.0, 18.0]
    fan_energies = [5000.0, 6000.0]
    
    for i in range(2):
        base = 132 + i * 56
        write_electricity_meter(
            base,
            pt=fan_powers[i],
            impep=fan_energies[i]
        )
    
    print(f"✅ 生成 DB10 测试数据: {len(data)} 字节")
    return bytes(data)


# ============================================================
# 2. 解析测试数据
# ============================================================
def parse_db10_data(raw_data: bytes) -> list:
    """使用 SCRFanParser 解析 DB10 数据"""
    parser = SCRFanParser()
    devices = parser.parse_all(raw_data)
    
    print(f"\n📦 解析结果: {len(devices)} 个设备")
    for device in devices:
        print(f"   - {device['device_id']}: {len(device['modules'])} 个模块")
    
    return devices


# ============================================================
# 3. 转换并写入 InfluxDB
# ============================================================
def convert_and_write(devices: list, db_number: int = 10):
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
    """验证 SCR/风机 API 能否返回数据"""
    print("\n🔍 验证 API...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 4.1 测试 /api/scr/list
        print("\n   [1] GET /api/scr/list")
        try:
            resp = await client.get(f"{API_BASE}/api/scr/list")
            data = resp.json()
            if data.get('success'):
                devices = data.get('data', [])
                print(f"       ✅ 成功! 返回 {len(devices)} 个 SCR 设备")
                for d in devices:
                    print(f"          - {d.get('device_id')}")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.2 测试 /api/scr/{device_id}
        print("\n   [2] GET /api/scr/scr_1")
        try:
            resp = await client.get(f"{API_BASE}/api/scr/scr_1")
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
        
        # 4.3 测试 /api/fan/list
        print("\n   [3] GET /api/fan/list")
        try:
            resp = await client.get(f"{API_BASE}/api/fan/list")
            data = resp.json()
            if data.get('success'):
                devices = data.get('data', [])
                print(f"       ✅ 成功! 返回 {len(devices)} 个风机设备")
                for d in devices:
                    print(f"          - {d.get('device_id')}")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.4 测试 /api/fan/{device_id}
        print("\n   [4] GET /api/fan/fan_1")
        try:
            resp = await client.get(f"{API_BASE}/api/fan/fan_1")
            data = resp.json()
            if data.get('success'):
                device_data = data.get('data', {})
                modules = device_data.get('modules', {})
                print(f"       ✅ 成功! 返回 {len(modules)} 个模块")
                for tag, mod in modules.items():
                    fields = mod.get('fields', {})
                    pt = fields.get('Pt', 'N/A')
                    print(f"          - {tag}: Pt={pt} kW")
            else:
                print(f"       ❌ 失败: {data.get('error')}")
        except Exception as e:
            print(f"       ❌ 请求失败: {e}")
        
        # 4.5 测试 /api/scr/{device_id}/history
        print("\n   [5] GET /api/scr/scr_1/history?module_type=FlowMeter")
        try:
            resp = await client.get(
                f"{API_BASE}/api/scr/scr_1/history",
                params={"module_type": "FlowMeter"}
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
    print("DB10 SCR/风机数据 - 完整流程测试")
    print("=" * 70)
    print("流程: 原始字节 → 解析 → 转换 → 存储 → API验证")
    print("=" * 70)
    
    # Step 1: 生成测试数据
    print("\n📝 Step 1: 生成 DB10 测试数据")
    raw_data = generate_db10_test_data()
    
    # 打印前 66 字节 (SCR_1)
    print("\n   前 66 字节 (scr_1: FlowMeter + ElectricityMeter):")
    for i in range(0, 66, 16):
        chunk = raw_data[i:i+16]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        print(f"   [{i:4d}] {hex_str}")
    
    # Step 2: 解析数据
    print("\n📦 Step 2: 解析 DB10 数据")
    devices = parse_db10_data(raw_data)
    
    # 打印设备详细数据
    if devices:
        for device in devices[:2]:
            print(f"\n   示例 - {device['device_id']}:")
            for tag, mod in device['modules'].items():
                print(f"   [{tag}] {mod['module_type']}:")
                for field_name, field_info in list(mod['fields'].items())[:3]:
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
    print("✅ DB10 完整流程测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
