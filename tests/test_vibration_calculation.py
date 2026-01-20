#!/usr/bin/env python3
"""
振动传感器量程模式测试脚本
用于验证不同 scale 配置下的数据解析
"""

import struct

def test_displacement_calculation():
    """测试位移计算公式"""
    
    # 模拟 PLC 原始数据 (Big Endian)
    # 假设传感器返回的原始值为 5000 (0x1388)
    raw_value = 5000
    dxh = (raw_value >> 8) & 0xFF  # 高字节: 0x13
    dxl = raw_value & 0xFF          # 低字节: 0x88
    
    print("=" * 60)
    print("振动位移 (DX) 计算测试")
    print("=" * 60)
    print(f"原始寄存器值: {raw_value} (0x{raw_value:04X})")
    print(f"高字节 DXH: {dxh} (0x{dxh:02X})")
    print(f"低字节 DXL: {dxl} (0x{dxl:02X})")
    print()
    
    # 模式1: 高量程模式 (60000μm, 1μm分辨率)
    print("【模式1】高量程模式")
    print("  配置: scale=1.0")
    print("  计算公式: DX = (DXH << 8) | DXL")
    displacement_mode1 = (dxh << 8) | dxl
    print(f"  结果: {displacement_mode1}μm")
    print(f"  有效范围: 0-60000μm")
    print()
    
    # 模式2: 高精度模式 (600μm, 0.01μm分辨率)
    print("【模式2】高精度模式")
    print("  配置: scale=0.01")
    print("  计算公式: DX = ((DXH << 8) | DXL) / 100")
    displacement_mode2 = ((dxh << 8) | dxl) / 100
    print(f"  结果: {displacement_mode2:.2f}μm")
    print(f"  有效范围: 0-600μm")
    print()

def test_frequency_calculation():
    """测试频率计算公式"""
    
    # 模拟频率原始数据: 500 (表示 50.0Hz)
    raw_value = 500
    hzxh = (raw_value >> 8) & 0xFF
    hzxl = raw_value & 0xFF
    
    print("=" * 60)
    print("振动频率 (HZX) 计算测试")
    print("=" * 60)
    print(f"原始寄存器值: {raw_value} (0x{raw_value:04X})")
    print(f"高字节 HZXH: {hzxh} (0x{hzxh:02X})")
    print(f"低字节 HZXL: {hzxl} (0x{hzxl:02X})")
    print()
    
    print("【频率计算】")
    print("  配置: scale=0.1 (固定)")
    print("  计算公式: HZX = ((HZXH << 8) | HZXL) / 10")
    frequency = ((hzxh << 8) | hzxl) / 10
    print(f"  结果: {frequency:.1f}Hz")
    print(f"  有效范围: 0-10000Hz")
    print()

def test_modbus_response():
    """测试 Modbus 响应解析"""
    
    print("=" * 60)
    print("Modbus 响应解析测试")
    print("=" * 60)
    
    # 模拟 Modbus 响应 (位移)
    # 发送: 50 03 00 41 00 03 58 5E (读取DX/DY/DZ)
    # 返回: 50 03 06 DXH DXL DYH DYL DZH DZL CRCH CRCL
    print("【读取三轴振动位移】")
    print("发送: 50 03 00 41 00 03 58 5E")
    
    # 假设返回: DX=1234, DY=2345, DZ=3456
    dx_value = 1234
    dy_value = 2345
    dz_value = 3456
    
    response = bytearray([
        0x50, 0x03, 0x06,  # 地址, 功能码, 字节数
        (dx_value >> 8) & 0xFF, dx_value & 0xFF,  # DX
        (dy_value >> 8) & 0xFF, dy_value & 0xFF,  # DY
        (dz_value >> 8) & 0xFF, dz_value & 0xFF,  # DZ
        0x00, 0x00  # CRC (占位)
    ])
    
    print(f"返回: {' '.join(f'{b:02X}' for b in response)}")
    print()
    
    # 解析高量程模式
    dx = (response[3] << 8) | response[4]
    dy = (response[5] << 8) | response[6]
    dz = (response[7] << 8) | response[8]
    print(f"高量程模式 (scale=1.0): DX={dx}μm, DY={dy}μm, DZ={dz}μm")
    
    # 解析高精度模式
    dx_hp = dx / 100
    dy_hp = dy / 100
    dz_hp = dz / 100
    print(f"高精度模式 (scale=0.01): DX={dx_hp:.2f}μm, DY={dy_hp:.2f}μm, DZ={dz_hp:.2f}μm")
    print()
    
    # 模拟 Modbus 响应 (频率)
    print("【读取三轴振动频率】")
    print("发送: 50 03 00 44 00 03 48 5F")
    
    hzx_value = 503  # 表示 50.3Hz
    hzy_value = 503
    hzz_value = 503
    
    response = bytearray([
        0x50, 0x03, 0x06,
        (hzx_value >> 8) & 0xFF, hzx_value & 0xFF,
        (hzy_value >> 8) & 0xFF, hzy_value & 0xFF,
        (hzz_value >> 8) & 0xFF, hzz_value & 0xFF,
        0x00, 0x00
    ])
    
    print(f"返回: {' '.join(f'{b:02X}' for b in response)}")
    print()
    
    hzx = ((response[3] << 8) | response[4]) / 10
    hzy = ((response[5] << 8) | response[6]) / 10
    hzz = ((response[7] << 8) | response[8]) / 10
    print(f"频率计算 (scale=0.1): HZX={hzx:.1f}Hz, HZY={hzy:.1f}Hz, HZZ={hzz:.1f}Hz")
    print()

def test_backend_config_examples():
    """后端配置示例"""
    
    print("=" * 60)
    print("后端配置示例")
    print("=" * 60)
    
    print("【当前配置 - configs/plc_modules.yaml】")
    print("- name: DX")
    print("  data_type: Word")
    print("  offset: 0")
    print("  size: 2")
    print("  unit: μm")
    print("  scale: 1.0  # 60000μm量程")
    print()
    
    print("【切换到高精度模式】")
    print("1. 修改 plc_modules.yaml:")
    print("   scale: 1.0  →  scale: 0.01")
    print()
    print("2. 修改 app/tools/converter_vibration.py:")
    print("   DISPLACEMENT_MODE = 'high_range'  →  DISPLACEMENT_MODE = 'high_precision'")
    print()
    print("3. 重启服务:")
    print("   docker compose down")
    print("   docker compose build --no-cache backend-mock")
    print("   docker compose up -d backend-mock")
    print()

if __name__ == "__main__":
    test_displacement_calculation()
    test_frequency_calculation()
    test_modbus_response()
    test_backend_config_examples()
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)
    print()
    print("💡 提示:")
    print("  - 当前后端配置使用高量程模式 (60000μm, scale=1.0)")
    print("  - 如需切换到高精度模式 (600μm, scale=0.01)，请参考上述配置示例")
    print("  - 频率固定使用 scale=0.1 (除以10)，不需要修改")
    print()
