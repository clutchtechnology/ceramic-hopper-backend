# ============================================================
# 文件说明: mock_data_generator.py - 电炉料仓模拟PLC原始数据生成器
# ============================================================
# 功能:
# 1. 生成符合PLC DB4块结构的16进制原始数据 (PM10/温度/电表/振动)
# 2. 模拟各种传感器的数据变化
# ============================================================

import struct
import random
import math
from datetime import datetime
from typing import Dict, Tuple

class MockDataGenerator:
    """模拟PLC原始数据生成器
    
    生成符合PLC DB块结构的原始字节数据
    """
    
    def __init__(self):
        # 基础值
        self._base_values = {
            'pm10': 35.0,        # μg/m³
            'temperature': 45.0, # °C
            'voltage_ab': 380.0, # V Line
            'voltage_a': 220.0,  # V Phase
            'current_a': 15.0,   # A Phase
            'power_total': 18.5, # kW
            'energy': 12345.0,   # kWh
            
            # Vibration
            'vib_speed': 2.5,    # mm/s
            'vib_hz': 50.0,      # Hz
            'vib_temp': 40.0,    # °C
        }
        
        self._tick = 0
    
    def tick(self):
        """时间前进一步 (每次轮询调用)"""
        self._tick += 1
    
    def _add_noise(self, base: float, noise_range: float = 0.03) -> float:
        """添加随机波动 (默认3%波动)"""
        noise = random.uniform(-noise_range, noise_range)
        return base * (1 + noise)
    
    def _add_sine_wave(self, base: float, amplitude: float = 0.1, period: int = 60) -> float:
        """添加正弦波动 (模拟周期性变化)"""
        wave = math.sin(2 * math.pi * self._tick / period) * amplitude
        return base * (1 + wave)

    # ============================================================
    # 模块数据生成
    # ============================================================
    
    def generate_pm10(self) -> bytes:
        """Offset 0-1: PM10 (Word)"""
        val = self._add_noise(self._base_values['pm10'], 0.1)  # 10%波动
        return struct.pack('>H', int(val))

    def generate_temperature(self) -> bytes:
        """Offset 2-3: Temperature (Int, 0.1°C scale)"""
        val = self._add_noise(self._base_values['temperature'], 0.02)
        scaled_val = int(val * 10) # 45.0 -> 450
        return struct.pack('>h', scaled_val)

    def generate_electricity(self) -> bytes:
        """Offset 4-59: ElectricityMeter (14 Real = 56 bytes)"""
        # Uab_0/1/2 (Line Voltage)
        u_line = self._add_noise(self._base_values['voltage_ab'], 0.01)
        # Ua_0/1/2 (Phase Voltage)
        u_phase = self._add_noise(self._base_values['voltage_a'], 0.01)
        # Ia_0/1/2 (Current)
        i_phase = self._add_noise(self._base_values['current_a'], 0.05)
        # Pt/Pa/Pb/Pc
        pt = self._add_noise(self._base_values['power_total'], 0.05)
        p_phase = pt / 3.0
        # Energy
        self._base_values['energy'] += (pt / 3600.0) # Accumulate simpler
        energy = self._base_values['energy']
        
        data = b''
        # Uab (3)
        data += struct.pack('>f', u_line) * 3
        # Ua (3)
        data += struct.pack('>f', u_phase) * 3
        # I (3)
        data += struct.pack('>f', i_phase) * 3
        # Pt (1)
        data += struct.pack('>f', pt)
        # Pa/Pb/Pc (3)
        data += struct.pack('>f', p_phase) * 3
        # Energy (1)
        data += struct.pack('>f', energy)
        
        return data

    def generate_vibration(self) -> bytes:
        """Offset 60-143: VibrationSelected (84 bytes)
        只生成 PLC 工程师标注的字段（有注释的字段）
        """
        buffer = bytearray(84)
        
        def write_word(offset, val, scale=1.0):
            """写入 Word (16位无符号整数, Big Endian)"""
            if offset + 2 > len(buffer): 
                return
            int_val = int(val / scale) if scale != 0 else int(val)
            int_val = max(0, min(65535, int_val))  # 限制范围 0-65535
            struct.pack_into('>H', buffer, offset, int_val)

        # 基础振动值
        vib_speed = self._add_noise(self._base_values['vib_speed'], 0.1)  # mm/s
        vib_freq = self._add_noise(self._base_values['vib_hz'], 0.01)    # Hz
        
        # ========== 振动位移幅值 (μm) ==========
        # DX (Offset 0), DY (Offset 2), DZ (Offset 4)
        dx = vib_speed * 15.9  # 转换为位移 (μm)
        dy = vib_speed * 15.9 * 0.8
        dz = vib_speed * 15.9 * 1.2
        write_word(0, dx, scale=1.0)
        write_word(2, dy, scale=1.0)
        write_word(4, dz, scale=1.0)
        
        # ========== 振动频率 (Hz) ==========
        # HZX (Offset 6), HZY (Offset 8), HZZ (Offset 10)
        write_word(6, vib_freq, scale=0.1)
        write_word(8, vib_freq, scale=0.1)
        write_word(10, vib_freq, scale=0.1)
        
        # ========== 加速度峰值 (m/s²) ==========
        # KX (Offset 14) - X轴加速度峰值
        ax = vib_speed * 0.628  # 简化转换 (mm/s -> m/s²)
        write_word(14, ax, scale=0.01)
        
        # AAVGY (Offset 40) - Y轴加速度峰值
        ay = ax * 0.8
        write_word(40, ay, scale=0.01)
        
        # AAVGZ (Offset 64) - Z轴加速度峰值
        az = ax * 1.2
        write_word(64, az, scale=0.01)
        
        # ========== 速度RMS值 (mm/s) ==========
        # VRMSX (Offset 30) - X轴速度RMS
        vrms_x = vib_speed * 0.707  # RMS = Peak / sqrt(2)
        write_word(30, vrms_x, scale=0.1)
        
        # VRMSY (Offset 54) - Y轴速度RMS
        vrms_y = vrms_x * 0.8
        write_word(54, vrms_y, scale=0.1)
        
        # VRMGZ (Offset 78) - Z轴速度RMS
        vrms_z = vrms_x * 1.2
        write_word(78, vrms_z, scale=0.1)
        
        return bytes(buffer)

    def generate_db4(self) -> bytes:
        """生成DB4完整数据 (144 bytes)"""
        data = b''
        # Offset 0: PM10 (2)
        data += self.generate_pm10()
        
        # Offset 2: Temp (2)
        data += self.generate_temperature()
        
        # Offset 4: Elec (56)
        data += self.generate_electricity()
        
        # Offset 60: Vib (84)
        data += self.generate_vibration()
        
        return data

    def generate_all_db_data(self) -> Dict[int, bytes]:
        """生成所有DB块数据 (供 polling_service 调用)"""
        self.tick()
        return {
            4: self.generate_db4()
        }
