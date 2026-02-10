# -*- coding: utf-8 -*-
"""DB6 振动传感器完整数据 - 原始值 -> 计算方法 -> 数据库格式 (独立诊断脚本)"""

import struct
import sys
from datetime import datetime

try:
    import snap7
except ImportError:
    print("snap7 not installed, run: pip install python-snap7")
    sys.exit(1)

# PLC 连接配置
PLC_IP = "192.168.50.235"
PLC_RACK = 0
PLC_SLOT = 1

DB_NUMBER = 6
DB_SIZE = 38

# InfluxDB 存储信息
MEASUREMENT = "sensor_data"
DEVICE_ID = "hopper_unit_4"
DEVICE_TYPE = "hopper_sensor_unit"


def parse_and_show(data: bytes):
    """解析 DB6 并展示: 原始值 -> 计算过程 -> 数据库字段"""

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # ================================================================
    # 1. 加速度 accel (Offset 0-5, 3xInt16)
    # ================================================================
    print()
    print("=" * 72)
    print("  1. 加速度幅值  |  Offset 0-5  |  3 x Int16 (6 bytes)")
    print("=" * 72)
    accel_x_raw = struct.unpack(">h", data[0:2])[0]
    accel_y_raw = struct.unpack(">h", data[2:4])[0]
    accel_z_raw = struct.unpack(">h", data[4:6])[0]
    
    print(f"  [RAW]  accel_x: 0x{accel_x_raw & 0xFFFF:04X} = {accel_x_raw}")
    print(f"  [RAW]  accel_y: 0x{accel_y_raw & 0xFFFF:04X} = {accel_y_raw}")
    print(f"  [RAW]  accel_z: 0x{accel_z_raw & 0xFFFF:04X} = {accel_z_raw}")
    print(f"  [CALC] 直接使用原始值")
    print(f"  [DB]   accel_x = {accel_x_raw}")
    print(f"         accel_y = {accel_y_raw}")
    print(f"         accel_z = {accel_z_raw}")

    # ================================================================
    # 2. 加速度频率 accel_f (Offset 6-11, 3xInt16)
    # ================================================================
    print()
    print("=" * 72)
    print("  2. 加速度频率  |  Offset 6-11  |  3 x Int16 (6 bytes)")
    print("=" * 72)
    accel_f_x_raw = struct.unpack(">h", data[6:8])[0]
    accel_f_y_raw = struct.unpack(">h", data[8:10])[0]
    accel_f_z_raw = struct.unpack(">h", data[10:12])[0]
    
    print(f"  [RAW]  accel_f_x: 0x{accel_f_x_raw & 0xFFFF:04X} = {accel_f_x_raw}")
    print(f"  [RAW]  accel_f_y: 0x{accel_f_y_raw & 0xFFFF:04X} = {accel_f_y_raw}")
    print(f"  [RAW]  accel_f_z: 0x{accel_f_z_raw & 0xFFFF:04X} = {accel_f_z_raw}")
    print(f"  [CALC] 直接使用原始值")
    print(f"  [DB]   accel_f_x = {accel_f_x_raw} Hz")
    print(f"         accel_f_y = {accel_f_y_raw} Hz")
    print(f"         accel_f_z = {accel_f_z_raw} Hz")

    # ================================================================
    # 3. 速度 vel (Offset 12-17, 3xInt16)
    # ================================================================
    print()
    print("=" * 72)
    print("  3. 速度幅值  |  Offset 12-17  |  3 x Int16 (6 bytes)")
    print("=" * 72)
    vel_x_raw = struct.unpack(">h", data[12:14])[0]
    vel_y_raw = struct.unpack(">h", data[14:16])[0]
    vel_z_raw = struct.unpack(">h", data[16:18])[0]
    
    print(f"  [RAW]  vel_x: 0x{vel_x_raw & 0xFFFF:04X} = {vel_x_raw}")
    print(f"  [RAW]  vel_y: 0x{vel_y_raw & 0xFFFF:04X} = {vel_y_raw}")
    print(f"  [RAW]  vel_z: 0x{vel_z_raw & 0xFFFF:04X} = {vel_z_raw}")
    print(f"  [CALC] 直接使用原始值")
    print(f"  [DB]   vel_x = {vel_x_raw} mm/s")
    print(f"         vel_y = {vel_y_raw} mm/s")
    print(f"         vel_z = {vel_z_raw} mm/s")

    # ================================================================
    # 4. 预留 reserved (Offset 18-25, 4xInt16)
    # ================================================================
    print()
    print("=" * 72)
    print("  4. 预留数据  |  Offset 18-25  |  4 x Int16 (8 bytes)")
    print("=" * 72)
    reserved_x_raw = struct.unpack(">h", data[18:20])[0]
    reserved_y_raw = struct.unpack(">h", data[20:22])[0]
    reserved_z_raw = struct.unpack(">h", data[22:24])[0]
    temp_raw = struct.unpack(">h", data[24:26])[0]
    
    print(f"  [RAW]  reserved_x: 0x{reserved_x_raw & 0xFFFF:04X} = {reserved_x_raw}")
    print(f"  [RAW]  reserved_y: 0x{reserved_y_raw & 0xFFFF:04X} = {reserved_y_raw}")
    print(f"  [RAW]  reserved_z: 0x{reserved_z_raw & 0xFFFF:04X} = {reserved_z_raw}")
    print(f"  [RAW]  temp: 0x{temp_raw & 0xFFFF:04X} = {temp_raw}")
    print(f"  [CALC] 直接使用原始值")
    print(f"  [DB]   reserved_x = {reserved_x_raw}")
    print(f"         reserved_y = {reserved_y_raw}")
    print(f"         reserved_z = {reserved_z_raw}")
    print(f"         temp = {temp_raw} C")

    # ================================================================
    # 5. 位移幅值 dis_f (Offset 26-31, 3xInt16)
    # ================================================================
    print()
    print("=" * 72)
    print("  5. 位移幅值  |  Offset 26-31  |  3 x Int16 (6 bytes)")
    print("=" * 72)
    dis_f_x_raw = struct.unpack(">h", data[26:28])[0]
    dis_f_y_raw = struct.unpack(">h", data[28:30])[0]
    dis_f_z_raw = struct.unpack(">h", data[30:32])[0]
    
    print(f"  [RAW]  dis_f_x: 0x{dis_f_x_raw & 0xFFFF:04X} = {dis_f_x_raw}")
    print(f"  [RAW]  dis_f_y: 0x{dis_f_y_raw & 0xFFFF:04X} = {dis_f_y_raw}")
    print(f"  [RAW]  dis_f_z: 0x{dis_f_z_raw & 0xFFFF:04X} = {dis_f_z_raw}")
    print(f"  [CALC] 直接使用原始值")
    print(f"  [DB]   dis_f_x = {dis_f_x_raw} um")
    print(f"         dis_f_y = {dis_f_y_raw} um")
    print(f"         dis_f_z = {dis_f_z_raw} um")

    # ================================================================
    # 6. 频率 freq (Offset 32-37, 3xInt16)
    # ================================================================
    print()
    print("=" * 72)
    print("  6. 频率  |  Offset 32-37  |  3 x Int16 (6 bytes)")
    print("=" * 72)
    freq_x_raw = struct.unpack(">h", data[32:34])[0]
    freq_y_raw = struct.unpack(">h", data[34:36])[0]
    freq_z_raw = struct.unpack(">h", data[36:38])[0]
    
    print(f"  [RAW]  freq_x: 0x{freq_x_raw & 0xFFFF:04X} = {freq_x_raw}")
    print(f"  [RAW]  freq_y: 0x{freq_y_raw & 0xFFFF:04X} = {freq_y_raw}")
    print(f"  [RAW]  freq_z: 0x{freq_z_raw & 0xFFFF:04X} = {freq_z_raw}")
    print(f"  [CALC] 直接使用原始值")
    print(f"  [DB]   freq_x = {freq_x_raw} Hz")
    print(f"         freq_y = {freq_y_raw} Hz")
    print(f"         freq_z = {freq_z_raw} Hz")

    # ================================================================
    # 7. 数据库写入格式汇总 (InfluxDB Point)
    # ================================================================
    print()
    print("=" * 72)
    print("  7. 数据库写入格式汇总 (InfluxDB)")
    print("=" * 72)
    print()
    print(f"  measurement = {MEASUREMENT}")
    print(f"  timestamp   = {now}")
    print()
    print("  [Tags]")
    print(f"    device_id   = {DEVICE_ID}")
    print(f"    device_type = {DEVICE_TYPE}")
    print()

    # 加速度模块 (vib_1.accel)
    print("  [Point 1] module_type=accel, module_tag=vib_1.accel")
    print(f"    fields: {{ accel_x: {accel_x_raw}, accel_y: {accel_y_raw}, accel_z: {accel_z_raw} }}")
    print()

    # 加速度频率模块 (vib_1.accel_f)
    print("  [Point 2] module_type=accel_f, module_tag=vib_1.accel_f")
    print(f"    fields: {{ accel_f_x: {accel_f_x_raw}, accel_f_y: {accel_f_y_raw}, accel_f_z: {accel_f_z_raw} }}")
    print()

    # 速度模块 (vib_1.vel)
    print("  [Point 3] module_type=vel, module_tag=vib_1.vel")
    print(f"    fields: {{ vel_x: {vel_x_raw}, vel_y: {vel_y_raw}, vel_z: {vel_z_raw} }}")
    print()

    # 预留模块 (vib_1.reserved)
    print("  [Point 4] module_type=reserved, module_tag=vib_1.reserved")
    print(f"    fields: {{ reserved_x: {reserved_x_raw}, reserved_y: {reserved_y_raw}, reserved_z: {reserved_z_raw}, temp: {temp_raw} }}")
    print()

    # 位移幅值模块 (vib_1.dis_f)
    print("  [Point 5] module_type=dis_f, module_tag=vib_1.dis_f")
    print(f"    fields: {{ dis_f_x: {dis_f_x_raw}, dis_f_y: {dis_f_y_raw}, dis_f_z: {dis_f_z_raw} }}")
    print()

    # 频率模块 (vib_1.freq)
    print("  [Point 6] module_type=freq, module_tag=vib_1.freq")
    print(f"    fields: {{ freq_x: {freq_x_raw}, freq_y: {freq_y_raw}, freq_z: {freq_z_raw} }}")

    # ================================================================
    # 8. 原始数据 hex dump (全部38字节)
    # ================================================================
    print()
    print("=" * 72)
    print("  8. 原始数据 Hex Dump (38 bytes)")
    print("=" * 72)
    print()
    for i in range(0, DB_SIZE, 16):
        chunk = data[i: min(i + 16, DB_SIZE)]
        hex_str = " ".join([f"{b:02X}" for b in chunk])
        ascii_str = "".join([chr(b) if 32 <= b < 127 else "." for b in chunk])
        print(f"  {i:3d}: {hex_str:<48s}  {ascii_str}")


# ================================================================
# 主入口
# ================================================================
client = snap7.client.Client()

try:
    client.connect(PLC_IP, PLC_RACK, PLC_SLOT)
except Exception as e:
    print(f"PLC connect failed: {e}")
    sys.exit(1)

print()
print("=" * 72)
print("  DB6 振动传感器完整数据 - 原始值 -> 计算方法 -> 数据库格式")
print(f"  PLC: {PLC_IP}  Rack: {PLC_RACK}  Slot: {PLC_SLOT}")
print(f"  DB: {DB_NUMBER}  Size: {DB_SIZE} bytes")
print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 72)

try:
    data = client.db_read(DB_NUMBER, 0, DB_SIZE)
    data = bytes(data)
    parse_and_show(data)

except Exception as e:
    print(f"Read DB6 failed: {e}")
    import traceback
    traceback.print_exc()

client.disconnect()
print()
print("=" * 80)
print("读取完成")
print("=" * 80)
input("按回车键退出...")

