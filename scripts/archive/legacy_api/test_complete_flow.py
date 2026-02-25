#!/usr/bin/env python3
# ============================================================
# 完整测试脚本 - 模拟PLC数据写入和查询
# ============================================================

import sys
import struct
import random
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.plc.parser_hopper import HopperParser
from app.plc.parser_roller_kiln import RollerKilnParser
from app.plc.parser_scr_fan import SCRFanParser
from app.core.influxdb import write_point
from app.services.history_query_service import HistoryQueryService


def generate_realistic_plc_data(db_size: int, data_type: str = "random") -> bytes:
    """生成模拟的PLC数据
    
    Args:
        db_size: DB块大小（字节）
        data_type: 数据类型 (random/realistic)
    
    Returns:
        字节数据
    """
    if data_type == "realistic":
        # 生成逼真的数据
        data = bytearray(db_size)
        
        # 填充一些合理的Real值
        for i in range(0, db_size - 4, 4):
            if i % 40 < 36:  # 电表数据区域
                # 电压: 380V左右
                if i % 40 < 12:
                    value = 380.0 + random.uniform(-10, 10)
                # 电流: 0-50A
                elif i % 40 < 36:
                    value = random.uniform(0, 50)
                # 功率: 0-100kW
                else:
                    value = random.uniform(0, 100)
            else:
                # 温度: 50-1300°C
                value = random.uniform(50, 1300)
            
            # 转换为Big Endian Real (4字节)
            packed = struct.pack('>f', value)
            data[i:i+4] = packed
        
        return bytes(data)
    else:
        # 生成随机数据
        return bytes([random.randint(0, 255) for _ in range(db_size)])


def write_db6_to_influx(parser: HopperParser, db6_data: bytes):
    """写入DB6数据到InfluxDB"""
    devices = parser.parse_all(db6_data)
    timestamp = datetime.now()
    
    for device in devices:
        for module_tag, module_data in device['modules'].items():
            # 提取字段值
            fields = {}
            for field_name, field_info in module_data['fields'].items():
                fields[field_name] = field_info['value']
            
            # 写入InfluxDB
            write_point(
                measurement="sensor_data",
                tags={
                    "device_id": device['device_id'],
                    "device_type": device['device_type'],
                    "module_type": module_data['module_type'],
                    "module_tag": module_tag,
                    "db_number": "6"
                },
                fields=fields,
                timestamp=timestamp
            )
    
    print(f"✅ DB6: {len(devices)}个设备数据已写入InfluxDB")


def write_db7_to_influx(parser: RollerKilnParser, db7_data: bytes):
    """写入DB7数据到InfluxDB"""
    device = parser.parse_all(db7_data)
    timestamp = datetime.now()
    
    # 写入电表数据
    for meter_tag, meter_data in device['electricity_meters'].items():
        fields = {}
        for field_name, field_info in meter_data['fields'].items():
            fields[field_name] = field_info['value']
        
        write_point(
            measurement="sensor_data",
            tags={
                "device_id": device['device_id'],
                "device_type": device['device_type'],
                "module_type": "ElectricityMeter",
                "module_tag": meter_tag,
                "db_number": "7"
            },
            fields=fields,
            timestamp=timestamp
        )
    
    # 写入温度数据
    for temp_tag, temp_data in device['temperature_sensors'].items():
        fields = {}
        for field_name, field_info in temp_data['fields'].items():
            fields[field_name] = field_info['value']
        
        write_point(
            measurement="sensor_data",
            tags={
                "device_id": device['device_id'],
                "device_type": device['device_type'],
                "module_type": "TemperatureSensor",
                "module_tag": temp_tag,
                "db_number": "7"
            },
            fields=fields,
            timestamp=timestamp
        )
    
    print(f"✅ DB7: 辊道窑数据已写入InfluxDB")


def write_db8_to_influx(parser: SCRFanParser, db8_data: bytes):
    """写入DB8数据到InfluxDB"""
    devices = parser.parse_all(db8_data)
    timestamp = datetime.now()
    
    for device in devices:
        for module_tag, module_data in device['modules'].items():
            fields = {}
            for field_name, field_info in module_data['fields'].items():
                fields[field_name] = field_info['value']
            
            write_point(
                measurement="sensor_data",
                tags={
                    "device_id": device['device_id'],
                    "device_type": device['device_type'],
                    "module_type": module_data['module_type'],
                    "module_tag": module_tag,
                    "db_number": "8"
                },
                fields=fields,
                timestamp=timestamp
            )
    
    print(f"✅ DB8: {len(devices)}个设备数据已写入InfluxDB")


def test_write_data():
    """测试数据写入"""
    print("\n" + "="*80)
    print("  测试1: 写入模拟数据到InfluxDB")
    print("="*80)
    
    # 初始化解析器
    db6_parser = HopperParser()
    db7_parser = RollerKilnParser()
    db8_parser = SCRFanParser()
    
    # 生成模拟数据
    print("\n生成模拟PLC数据...")
    db6_data = generate_realistic_plc_data(554, "realistic")
    db7_data = generate_realistic_plc_data(288, "realistic")
    db8_data = generate_realistic_plc_data(176, "realistic")
    
    # 写入InfluxDB
    print("\n写入数据到InfluxDB...")
    write_db6_to_influx(db6_parser, db6_data)
    write_db7_to_influx(db7_parser, db7_data)
    write_db8_to_influx(db8_parser, db8_data)
    
    print("\n✅ 数据写入完成！")


def test_query_history():
    """测试历史数据查询"""
    print("\n" + "="*80)
    print("  测试2: 查询历史数据")
    print("="*80)
    
    service = HistoryQueryService()

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)

    print(f"\n查询 hopper_unit_4 历史数据...")
    print(f"  时间范围: {start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}")

    data = service.query_device_history(
        device_id="hopper_unit_4",
        start=start_time,
        end=end_time,
        module_type="temperature",
        fields=["temperature"],
        interval="5m"
    )

    print(f"  查询到 {len(data)} 条数据")
    if data:
        print(f"\n  最新数据:")
        latest = data[-1]
        print(f"    时间: {latest['time']}")
        print(f"    温度: {latest.get('temperature', 0):.2f}°C")


def test_latest_timestamp():
    """测试最新时间戳查询"""
    print("\n" + "="*80)
    print("  测试3: 查询最新时间戳")
    print("="*80)

    service = HistoryQueryService()

    latest = service.get_latest_db_timestamp()
    print(f"\n最新时间戳: {latest.isoformat() if latest else '无数据'}")


def main():
    print("\n" + "🧪 " * 40)
    print("完整数据流测试: PLC → 解析 → InfluxDB → 查询API")
    print("🧪 " * 40)
    
    try:
        # 1. 写入数据
        test_write_data()
        
        # 等待一下让数据落盘
        import time
        print("\n⏳ 等待2秒让数据落盘...")
        time.sleep(2)
        
        # 2. 查询测试
        test_query_history()
        test_latest_timestamp()
        
        print("\n" + "="*80)
        print("  ✅ 所有测试完成!")
        print("="*80)
        
        print("\n📋 API使用示例:")
        print("  1. 实时数据: GET http://localhost:8080/api/devices/short_hopper_1/realtime")
        print("  2. 温度历史: GET http://localhost:8080/api/devices/roller_kiln_1/temperature?start=2025-12-09T00:00:00&end=2025-12-09T23:59:59")
        print("  3. 功率历史: GET http://localhost:8080/api/devices/short_hopper_1/power?start=2025-12-09T00:00:00&end=2025-12-09T23:59:59")
        print("  4. 设备对比: GET http://localhost:8080/api/devices/compare?device_ids=short_hopper_1,short_hopper_2&field=Temperature&start=2025-12-09T00:00:00&end=2025-12-09T23:59:59")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
