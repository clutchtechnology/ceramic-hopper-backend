# -*- coding: utf-8 -*-
"""DB4 料仓传感器 - 原始值 -> 转换公式 -> 数据库格式 (独立诊断脚本)
   部署: 南厂  PLC: 192.168.50.234
   数据块: DB4 (60字节) - PM10 + 温度 + 电表
   注意: 振动数据已迁移到 DB6, 请使用 parse_db6_hopper_vibration.py
   转换公式来源: app/tools/converter_pm10.py, converter_temp.py, converter_elec.py
"""

import struct
import sys
from datetime import datetime

try:
    import snap7
except ImportError:
    print("snap7 not installed, run: pip install python-snap7")
    sys.exit(1)

# PLC 连接配置 (南厂)
PLC_IP = "192.168.50.234"
PLC_RACK = 0
PLC_SLOT = 1

DB_NUMBER = 4
DB_SIZE = 60  # PM10(2) + 温度(2) + 电表(56) = 60 字节

# 电流互感器变比 (料仓=20)
RATIO = 20

# InfluxDB 存储信息
MEASUREMENT = "sensor_data"
DEVICE_ID = "hopper_unit_4"
DEVICE_TYPE = "hopper_sensor_unit"

# 温度转换系数 (来源: converter_temp.py)
TEMP_SCALE_NUM = 250.0
TEMP_SCALE_DEN = 27683.0


def parse_and_show(data: bytes):
    """解析 DB4 并展示: 原始值 -> 计算过程 -> 数据库字段"""

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # ================================================================
    # 1. PM10 粉尘浓度 (Offset 0-1, Word)
    # 转换器: converter_pm10.py - 直接使用, 无需缩放
    # DB字段: pm10, concentration (ug/m3)
    # ================================================================
    print()
    print("=" * 72)
    print("  1. PM10 粉尘浓度  |  Offset 0-1  |  Word (2 bytes)")
    print("=" * 72)
    pm10_raw = struct.unpack(">H", data[0:2])[0]
    pm10_db = round(float(pm10_raw), 1)
    print(f"  [RAW]  Hex: 0x{pm10_raw:04X}  Decimal: {pm10_raw}")
    print(f"  [CALC] pm10 = raw (直接使用, 无需缩放)")
    print(f"         {pm10_raw} -> {pm10_db}")
    print(f"  [DB]   pm10 = {pm10_db} ug/m3")
    print(f"         concentration = {pm10_db} ug/m3")

    # ================================================================
    # 2. 温度 (Offset 2-3, Int16)
    # 转换器: converter_temp.py
    # 公式: temperature = raw * 250 / 27683
    # 例: PLC=27683 -> 250.0C, PLC=11073 -> 100.0C
    # DB字段: temperature (C)
    # ================================================================
    print()
    print("=" * 72)
    print("  2. 温度传感器  |  Offset 2-3  |  Int16 (2 bytes)")
    print(f"     公式: raw * {TEMP_SCALE_NUM} / {TEMP_SCALE_DEN}")
    print("=" * 72)
    temp_raw = struct.unpack(">h", data[2:4])[0]
    temp_db = round(temp_raw * TEMP_SCALE_NUM / TEMP_SCALE_DEN, 1)
    if temp_db < -10.0:
        temp_orig = temp_db
        temp_db = abs(temp_db)
        print(f"  [RAW]  Hex: 0x{temp_raw & 0xFFFF:04X}  Decimal: {temp_raw}")
        print(f"  [CALC] temperature = {temp_raw} * {TEMP_SCALE_NUM} / {TEMP_SCALE_DEN} = {temp_orig}")
        print(f"         (< -10C, 取绝对值修正) -> {temp_db}")
    else:
        print(f"  [RAW]  Hex: 0x{temp_raw & 0xFFFF:04X}  Decimal: {temp_raw}")
        print(f"  [CALC] temperature = {temp_raw} * {TEMP_SCALE_NUM} / {TEMP_SCALE_DEN} = {temp_db}")
    print(f"  [DB]   temperature = {temp_db} C")

    # ================================================================
    # 3. 电表 (Offset 4-59, 14xReal, 56 bytes)
    # 转换器: converter_elec.py (2026-03-03 修正版)
    #   电压: raw * 0.1                -> V
    #   电流: raw * 0.001 * ratio(20)  -> A
    #   功率: raw * 0.0001 * ratio(20) -> kW
    #   能耗: raw * ratio(20)          -> kWh
    # ================================================================
    print()
    print("=" * 72)
    print("  3. 三相电表  |  Offset 4-59  |  14 x Real (56 bytes)")
    print(f"     变比 ratio = {RATIO}")
    print("=" * 72)

    base = 4

    def read_real(offset):
        return struct.unpack(">f", data[base + offset: base + offset + 4])[0]

    # 线电压 (不存数据库, 仅显示)
    Uab_0_raw = read_real(0)
    Uab_1_raw = read_real(4)
    Uab_2_raw = read_real(8)

    # 相电压
    Ua_0_raw = read_real(12)
    Ua_1_raw = read_real(16)
    Ua_2_raw = read_real(20)

    # 电流
    I_0_raw = read_real(24)
    I_1_raw = read_real(28)
    I_2_raw = read_real(32)

    # 功率
    Pt_raw = read_real(36)
    Pa_raw = read_real(40)
    Pb_raw = read_real(44)
    Pc_raw = read_real(48)

    # 能耗
    ImpEp_raw = read_real(52)

    # -- 3.1 线电压 (不写入DB, 仅诊断) --
    print()
    print("  [3.1] 线电压 (不写入数据库, 仅诊断)")
    for name, raw in [("Uab_0", Uab_0_raw), ("Uab_1", Uab_1_raw), ("Uab_2", Uab_2_raw)]:
        val = round(raw * 0.1, 1)
        print(f"    {name}: [RAW] {raw:.1f}  [CALC] {raw:.1f} * 0.1 = {val} V")

    # -- 3.2 相电压: raw * 0.1 --
    print()
    print("  [3.2] 相电压: raw * 0.1  -> DB字段: Ua_0, Ua_1, Ua_2")
    Ua_0_db = round(Ua_0_raw * 0.1, 1)
    Ua_1_db = round(Ua_1_raw * 0.1, 1)
    Ua_2_db = round(Ua_2_raw * 0.1, 1)
    for name, raw, db_val in [("Ua_0", Ua_0_raw, Ua_0_db), ("Ua_1", Ua_1_raw, Ua_1_db), ("Ua_2", Ua_2_raw, Ua_2_db)]:
        print(f"    {name}: [RAW] {raw:.1f}  [CALC] {raw:.1f} * 0.1 = {db_val}  [DB] {name} = {db_val} V")

    # -- 3.3 电流: raw * 0.001 * ratio --
    print()
    print(f"  [3.3] 电流: raw * 0.001 * {RATIO}  -> DB字段: I_0, I_1, I_2")
    I_0_db = round(I_0_raw * 0.001 * RATIO, 2)
    I_1_db = round(I_1_raw * 0.001 * RATIO, 2)
    I_2_db = round(I_2_raw * 0.001 * RATIO, 2)
    for name, raw, db_val in [("I_0", I_0_raw, I_0_db), ("I_1", I_1_raw, I_1_db), ("I_2", I_2_raw, I_2_db)]:
        print(f"    {name}: [RAW] {raw:.1f}  [CALC] {raw:.1f} * 0.001 * {RATIO} = {db_val}  [DB] {name} = {db_val} A")

    # -- 3.4 功率: raw * 0.0001 * ratio --
    print()
    print(f"  [3.4] 功率: raw * 0.0001 * {RATIO}  -> DB字段: Pt")
    Pt_db = round(Pt_raw * 0.0001 * RATIO, 3)
    print(f"    Pt:  [RAW] {Pt_raw:.1f}  [CALC] {Pt_raw:.1f} * 0.0001 * {RATIO} = {Pt_db}  [DB] Pt = {Pt_db} kW")
    # 各相功率仅诊断
    for name, raw in [("Pa", Pa_raw), ("Pb", Pb_raw), ("Pc", Pc_raw)]:
        val = round(raw * 0.0001 * RATIO, 3)
        print(f"    {name}:  [RAW] {raw:.1f}  [CALC] {raw:.1f} * 0.0001 * {RATIO} = {val} kW  (不写入DB)")

    # -- 3.5 能耗: raw * ratio --
    print()
    print(f"  [3.5] 能耗: raw * {RATIO}  -> DB字段: ImpEp")
    ImpEp_db = round(ImpEp_raw * RATIO, 2)
    print(f"    ImpEp: [RAW] {ImpEp_raw:.2f}  [CALC] {ImpEp_raw:.2f} * {RATIO} = {ImpEp_db}  [DB] ImpEp = {ImpEp_db} kWh")

    # ================================================================
    # 4. 数据库写入格式汇总 (InfluxDB Point)
    # ================================================================
    print()
    print("=" * 72)
    print("  4. 数据库写入格式汇总 (InfluxDB)")
    print("=" * 72)
    print()
    print(f"  measurement = {MEASUREMENT}")
    print(f"  timestamp   = {now}")
    print()
    print("  [Tags]")
    print(f"    device_id   = {DEVICE_ID}")
    print(f"    device_type = {DEVICE_TYPE}")
    print()

    # PM10
    print("  [Point 1] module_type=pm10, module_tag=pm10")
    print(f"    fields: {{ pm10: {pm10_db}, concentration: {pm10_db} }}")
    print()

    # 温度
    print("  [Point 2] module_type=temperature, module_tag=temperature")
    print(f"    fields: {{ temperature: {temp_db} }}")
    print()

    # 电表
    print("  [Point 3] module_type=electricity, module_tag=electricity")
    print(f"    fields: {{ Ua_0: {Ua_0_db}, Ua_1: {Ua_1_db}, Ua_2: {Ua_2_db},")
    print(f"              I_0: {I_0_db}, I_1: {I_1_db}, I_2: {I_2_db},")
    print(f"              Pt: {Pt_db}, ImpEp: {ImpEp_db} }}")

    # ================================================================
    # 5. 原始数据 hex dump (全部60字节)
    # ================================================================
    print()
    print("=" * 72)
    print(f"  5. 原始数据 Hex Dump ({DB_SIZE} bytes)")
    print("=" * 72)
    print()
    for i in range(0, DB_SIZE, 16):
        chunk = data[i: min(i + 16, DB_SIZE)]
        hex_str = " ".join([f"{b:02X}" for b in chunk])
        ascii_str = "".join([chr(b) if 32 <= b < 127 else "." for b in chunk])
        print(f"  {i:3d}: {hex_str:<48s}  {ascii_str}")

    # ================================================================
    # 6. 转换公式速查表
    # ================================================================
    print()
    print("=" * 72)
    print("  6. 转换公式速查表 (与后端 converter 一致)")
    print("=" * 72)
    print()
    print("  | 模块     | 字段        | 公式                       | 来源                 |")
    print("  |----------|-------------|----------------------------|----------------------|")
    print("  | PM10     | pm10        | raw (直接使用)             | converter_pm10.py    |")
    print(f"  | 温度     | temperature | raw * {TEMP_SCALE_NUM} / {TEMP_SCALE_DEN}       | converter_temp.py    |")
    print("  | 电压     | Ua_0/1/2    | raw * 0.1                  | converter_elec.py    |")
    print(f"  | 电流     | I_0/1/2     | raw * 0.001 * {RATIO}           | converter_elec.py    |")
    print(f"  | 功率     | Pt          | raw * 0.0001 * {RATIO}          | converter_elec.py    |")
    print(f"  | 能耗     | ImpEp       | raw * {RATIO}                   | converter_elec.py    |")


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
print("  DB4 料仓传感器 - 南厂诊断脚本")
print(f"  PLC: {PLC_IP}  Rack: {PLC_RACK}  Slot: {PLC_SLOT}")
print(f"  DB: {DB_NUMBER}  Size: {DB_SIZE} bytes")
print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("  [注意] 振动数据已迁移到 DB6, 请运行 parse_db6_hopper_vibration.py")
print("=" * 72)

try:
    data = client.db_read(DB_NUMBER, 0, DB_SIZE)
    data = bytes(data)
    parse_and_show(data)

except Exception as e:
    print(f"Read DB4 failed: {e}")
    import traceback
    traceback.print_exc()

client.disconnect()
print()
print("=" * 80)
print("DB4 读取完成")
print("=" * 80)
input("按回车键退出...")
