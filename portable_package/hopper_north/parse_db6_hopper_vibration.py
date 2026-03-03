# -*- coding: utf-8 -*-
"""DB6 振动传感器 - 原始值 -> 转换公式 -> 数据库格式 (独立诊断脚本)
   部署: 北厂  PLC: 192.168.50.235
   数据块: DB6 (38字节) - 加速度/速度/位移/频率/温度
   转换公式来源: app/tools/converter_vibration.py, app/plc/parser_vib_db6.py
"""

import struct
import sys
from datetime import datetime

try:
    import snap7
except ImportError:
    print("snap7 not installed, run: pip install python-snap7")
    sys.exit(1)

# PLC 连接配置 (北厂)
PLC_IP = "192.168.50.235"
PLC_RACK = 0
PLC_SLOT = 1

DB_NUMBER = 6
DB_SIZE = 38  # 全部 38 字节

# InfluxDB 存储信息
MEASUREMENT = "sensor_data"
DEVICE_ID = "hopper_unit_4"
DEVICE_TYPE = "hopper_sensor_unit"

# 振动精度模式 (来源: converter_vibration.py)
# 低精度 (默认): V/D/HZ 直接使用原始值
# 高精度: V = raw/100, D = raw/10, HZ = raw/10
HIGH_PRECISION = False  # 生产环境默认低精度


def parse_and_show(data: bytes):
    """解析 DB6 并展示: 原始值 -> 计算过程 -> 数据库字段"""

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def read_int16(offset):
        return struct.unpack(">h", data[offset:offset + 2])[0]

    # ================================================================
    # 1. 加速度幅值 accel (Offset 0-5, 3xInt16)
    # 产线不存入数据库, 仅诊断用
    # ================================================================
    print()
    print("=" * 72)
    print("  1. 加速度幅值 (accel)  |  Offset 0-5  |  3 x Int16 (6 bytes)")
    print("     [不写入数据库, 仅诊断]")
    print("=" * 72)
    accel_x = read_int16(0)
    accel_y = read_int16(2)
    accel_z = read_int16(4)
    for name, raw, offset in [("accel_x", accel_x, 0), ("accel_y", accel_y, 2), ("accel_z", accel_z, 4)]:
        print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}")

    # ================================================================
    # 2. 加速度频率 accel_f (Offset 6-11, 3xInt16)
    # 产线不存入数据库, 仅诊断用
    # ================================================================
    print()
    print("=" * 72)
    print("  2. 加速度频率 (accel_f)  |  Offset 6-11  |  3 x Int16 (6 bytes)")
    print("     [不写入数据库, 仅诊断]")
    print("=" * 72)
    accel_f_x = read_int16(6)
    accel_f_y = read_int16(8)
    accel_f_z = read_int16(10)
    for name, raw, offset in [("accel_f_x", accel_f_x, 6), ("accel_f_y", accel_f_y, 8), ("accel_f_z", accel_f_z, 10)]:
        print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}  Hz")

    # ================================================================
    # 3. 速度幅值 vel (Offset 12-17, 3xInt16) -> VX/VY/VZ
    # 转换器: converter_vibration.py
    # 低精度: 直接使用  高精度: raw / 100
    # DB字段: vx, vy, vz (mm/s)
    # ================================================================
    print()
    print("=" * 72)
    print("  3. 速度幅值 (vel)  |  Offset 12-17  |  3 x Int16 (6 bytes)")
    if HIGH_PRECISION:
        print("     公式: raw / 100 (高精度模式)")
    else:
        print("     公式: raw (直接使用, 低精度模式)")
    print("     DB映射: vel_x -> VX -> vx, vel_y -> VY -> vy, vel_z -> VZ -> vz")
    print("=" * 72)
    vel_x_raw = read_int16(12)
    vel_y_raw = read_int16(14)
    vel_z_raw = read_int16(16)

    v_divisor = 100.0 if HIGH_PRECISION else 1.0
    vel_data = []
    for name, db_name, raw, offset in [("vel_x", "vx", vel_x_raw, 12), ("vel_y", "vy", vel_y_raw, 14), ("vel_z", "vz", vel_z_raw, 16)]:
        val = round(float(raw) / v_divisor, 2)
        vel_data.append((db_name, val))
        if HIGH_PRECISION:
            print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}")
            print(f"         [CALC] {raw} / 100 = {val}  [DB] {db_name} = {val} mm/s")
        else:
            print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}")
            print(f"         [CALC] {raw} (直接使用)  [DB] {db_name} = {val} mm/s")

    # ================================================================
    # 4. 预留 reserved (Offset 18-25, 4xInt16, 含温度)
    # reserved_x/y/z: 不使用
    # temp (Offset 24-25): 振动传感器温度
    # ================================================================
    print()
    print("=" * 72)
    print("  4. 预留数据 (reserved)  |  Offset 18-25  |  4 x Int16 (8 bytes)")
    print("     [reserved_x/y/z 不使用, temp 为振动传感器温度]")
    print("=" * 72)
    reserved_x = read_int16(18)
    reserved_y = read_int16(20)
    reserved_z = read_int16(22)
    vib_temp = read_int16(24)
    for name, raw, offset in [("reserved_x", reserved_x, 18), ("reserved_y", reserved_y, 20), ("reserved_z", reserved_z, 22)]:
        print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}  (不使用)")
    print(f"  temp:       [RAW] Offset 24  Hex: 0x{vib_temp & 0xFFFF:04X}  Decimal: {vib_temp}  C")

    # ================================================================
    # 5. 位移幅值 dis_f (Offset 26-31, 3xInt16) -> DX/DY/DZ
    # 转换器: converter_vibration.py
    # 低精度: 直接使用  高精度: raw / 10
    # DB字段: dx, dy, dz (um)
    # ================================================================
    print()
    print("=" * 72)
    print("  5. 位移幅值 (dis_f)  |  Offset 26-31  |  3 x Int16 (6 bytes)")
    if HIGH_PRECISION:
        print("     公式: raw / 10 (高精度模式)")
    else:
        print("     公式: raw (直接使用, 低精度模式)")
    print("     DB映射: dis_f_x -> DX -> dx, dis_f_y -> DY -> dy, dis_f_z -> DZ -> dz")
    print("=" * 72)
    dis_f_x_raw = read_int16(26)
    dis_f_y_raw = read_int16(28)
    dis_f_z_raw = read_int16(30)

    d_divisor = 10.0 if HIGH_PRECISION else 1.0
    dis_data = []
    for name, db_name, raw, offset in [("dis_f_x", "dx", dis_f_x_raw, 26), ("dis_f_y", "dy", dis_f_y_raw, 28), ("dis_f_z", "dz", dis_f_z_raw, 30)]:
        val = round(float(raw) / d_divisor, 1)
        dis_data.append((db_name, val))
        if HIGH_PRECISION:
            print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}")
            print(f"          [CALC] {raw} / 10 = {val}  [DB] {db_name} = {val} um")
        else:
            print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}")
            print(f"          [CALC] {raw} (直接使用)  [DB] {db_name} = {val} um")

    # ================================================================
    # 6. 频率 freq (Offset 32-37, 3xInt16) -> HZX/HZY/HZZ
    # 转换器: converter_vibration.py
    # 低精度: 直接使用  高精度: raw / 10
    # DB字段: hzx, hzy, hzz (Hz)
    # ================================================================
    print()
    print("=" * 72)
    print("  6. 频率 (freq)  |  Offset 32-37  |  3 x Int16 (6 bytes)")
    if HIGH_PRECISION:
        print("     公式: raw / 10 (高精度模式)")
    else:
        print("     公式: raw (直接使用, 低精度模式)")
    print("     DB映射: freq_x -> HZX -> hzx, freq_y -> HZY -> hzy, freq_z -> HZZ -> hzz")
    print("=" * 72)
    freq_x_raw = read_int16(32)
    freq_y_raw = read_int16(34)
    freq_z_raw = read_int16(36)

    hz_divisor = 10.0 if HIGH_PRECISION else 1.0
    freq_data = []
    for name, db_name, raw, offset in [("freq_x", "hzx", freq_x_raw, 32), ("freq_y", "hzy", freq_y_raw, 34), ("freq_z", "hzz", freq_z_raw, 36)]:
        val = round(float(raw) / hz_divisor, 1)
        freq_data.append((db_name, val))
        if HIGH_PRECISION:
            print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}")
            print(f"         [CALC] {raw} / 10 = {val}  [DB] {db_name} = {val} Hz")
        else:
            print(f"  {name}: [RAW] Offset {offset}  Hex: 0x{raw & 0xFFFF:04X}  Decimal: {raw}")
            print(f"         [CALC] {raw} (直接使用)  [DB] {db_name} = {val} Hz")

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
    print(f"    module_type = vibration_selected")
    print()

    # 合并为一个 vibration 模块写入
    fields_str_parts = []
    for db_name, val in vel_data:
        fields_str_parts.append(f"{db_name}: {val}")
    for db_name, val in dis_data:
        fields_str_parts.append(f"{db_name}: {val}")
    for db_name, val in freq_data:
        fields_str_parts.append(f"{db_name}: {val}")

    print("  [Point] module_type=vibration_selected")
    print(f"    fields: {{ {', '.join(fields_str_parts)} }}")

    # ================================================================
    # 8. 原始数据 hex dump (全部38字节)
    # ================================================================
    print()
    print("=" * 72)
    print(f"  8. 原始数据 Hex Dump ({DB_SIZE} bytes)")
    print("=" * 72)
    print()
    for i in range(0, DB_SIZE, 16):
        chunk = data[i: min(i + 16, DB_SIZE)]
        hex_str = " ".join([f"{b:02X}" for b in chunk])
        ascii_str = "".join([chr(b) if 32 <= b < 127 else "." for b in chunk])
        print(f"  {i:3d}: {hex_str:<48s}  {ascii_str}")

    # ================================================================
    # 9. 转换公式速查表
    # ================================================================
    print()
    print("=" * 72)
    precision_str = "高精度" if HIGH_PRECISION else "低精度"
    print(f"  9. 转换公式速查表 (当前: {precision_str}模式)")
    print("=" * 72)
    print()
    print("  | DB6模块  | DB字段    | 低精度公式      | 高精度公式       | 单位   |")
    print("  |----------|-----------|-----------------|------------------|--------|")
    print("  | vel_x    | vx        | raw (直接使用)  | raw / 100        | mm/s   |")
    print("  | vel_y    | vy        | raw (直接使用)  | raw / 100        | mm/s   |")
    print("  | vel_z    | vz        | raw (直接使用)  | raw / 100        | mm/s   |")
    print("  | dis_f_x  | dx        | raw (直接使用)  | raw / 10         | um     |")
    print("  | dis_f_y  | dy        | raw (直接使用)  | raw / 10         | um     |")
    print("  | dis_f_z  | dz        | raw (直接使用)  | raw / 10         | um     |")
    print("  | freq_x   | hzx       | raw (直接使用)  | raw / 10         | Hz     |")
    print("  | freq_y   | hzy       | raw (直接使用)  | raw / 10         | Hz     |")
    print("  | freq_z   | hzz       | raw (直接使用)  | raw / 10         | Hz     |")
    print()
    print("  DB6 偏移量布局:")
    print("  | Offset | 模块    | 说明          | 写入DB |")
    print("  |--------|---------|---------------|--------|")
    print("  | 0-5    | accel   | 加速度幅值    | 否     |")
    print("  | 6-11   | accel_f | 加速度频率    | 否     |")
    print("  | 12-17  | vel     | 速度幅值 (VX) | 是     |")
    print("  | 18-25  | reserved| 预留+温度     | 否     |")
    print("  | 26-31  | dis_f   | 位移幅值 (DX) | 是     |")
    print("  | 32-37  | freq    | 频率 (HZX)    | 是     |")


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
print("  DB6 振动传感器 - 北厂诊断脚本")
print(f"  PLC: {PLC_IP}  Rack: {PLC_RACK}  Slot: {PLC_SLOT}")
print(f"  DB: {DB_NUMBER}  Size: {DB_SIZE} bytes")
precision_str = "高精度" if HIGH_PRECISION else "低精度"
print(f"  精度模式: {precision_str}")
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
print("DB6 读取完成")
print("=" * 80)
input("按回车键退出...")
