# ============================================================
# 文件说明: config.py - 应用配置管理
# ============================================================
# 使用 pydantic-settings 管理配置，支持环境变量和配置文件
# 数据库架构: 仅使用 InfluxDB (时序数据) + YAML 文件 (配置数据)
# ============================================================

import os
import sys
from pathlib import Path
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional


# ------------------------------------------------------------
# 获取应用根目录（支持打包后的 .exe）
# ------------------------------------------------------------
def get_app_root() -> Path:
    """获取应用根目录
    
    开发模式: 返回项目根目录
    打包模式: 返回 .exe 所在目录
    """
    if getattr(sys, 'frozen', False):
        # 打包后: sys.executable 是 .exe 的路径
        return Path(sys.executable).parent
    else:
        # 开发模式: __file__ 是 config.py 的路径
        return Path(__file__).parent


def get_internal_root() -> Path:
    """获取 PyInstaller 内部资源目录
    
    开发模式: 返回项目根目录
    打包模式: 返回 _internal 目录
    """
    if getattr(sys, 'frozen', False):
        # 打包后: sys._MEIPASS 是 _internal 目录
        return Path(getattr(sys, '_MEIPASS', sys.executable))
    else:
        # 开发模式: 与 APP_ROOT 相同
        return Path(__file__).parent


# 应用根目录（.exe 所在目录）
APP_ROOT = get_app_root()

# 内部资源目录（_internal 目录）
INTERNAL_ROOT = get_internal_root()


class Settings(BaseSettings):
    """应用配置
    
    配置优先级（从高到低）:
    1. .env 文件（最高优先级）
    2. 环境变量
    3. 默认值
    
    注意: YAML 配置文件中的 polling_config 会被 .env 覆盖
    """
    
    # 服务器配置
    server_host: str = "0.0.0.0"
    server_port: int = 8082
    debug: bool = False
    
    # 轮询开关
    enable_polling: bool = True
    
    # Mock模式 (使用模拟数据而非真实PLC)
    mock_mode: bool = True
    
    # 详细轮询日志 (True: 显示每个设备的详细数据, False: 仅显示写入数量)
    # Release模式下建议设为False，只输出error级别和API请求日志
    verbose_polling_log: bool = False
    
    # PLC 配置（.env 优先级最高）
    plc_ip: str = "192.168.50.235"
    plc_rack: int = 0
    plc_slot: int = 1
    plc_timeout: int = 5000  # ms
    plc_poll_interval: float = 1  # seconds (轮询间隔，.env 优先，支持小数如0.5)
    
    # 批量写入配置（.env 优先级最高）
    # [CRITICAL] 多少次轮询后批量写入 InfluxDB
    batch_write_size: int = 12  # 多少次轮询后批量写入 InfluxDB
    
    # 振动传感器精度模式 (true=高精度, false=低精度)
    vib_high_precision: bool = False
    
    # 本地缓存配置
    local_cache_path: str = "data/cache.db"  # SQLite 缓存文件路径
    
    # InfluxDB 配置 (唯一数据库)
    influx_url: str = "http://localhost:8086"
    influx_token: str = "8Ba0ioTKL1sP2v7M60fmJKcjxyva8Xd7Q-0u1HmQvxYcbKjJN0lnpnWRT1ZWTi9Cv6TqtjKrnXzorunF45Pj8Q=="
    influx_org: str = "clutchtech"
    influx_bucket: str = "hopper"
    
    # 配置文件路径
    config_dir: str = "configs"
    sensors_config_file: str = "configs/sensors.yaml"
    devices_config_file: str = "configs/devices.yaml"
    
    @field_validator('debug', 'mock_mode', 'enable_polling', 'verbose_polling_log', 'vib_high_precision', mode='before')
    @classmethod
    def parse_bool(cls, v):
        """解析布尔值（兼容多种格式）"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ('true', '1', 'yes', 'on'):
                return True
            elif v_lower in ('false', '0', 'no', 'off', ''):
                return False
            else:
                # 无效值，返回 False（避免报错）
                print(f"[配置警告] 无效的布尔值: {v}，使用默认值 False")
                return False
        return bool(v)
    
    class Config:
        # 优先从应用根目录读取 .env 文件
        env_file = str(APP_ROOT / ".env")
        env_file_encoding = "utf-8"
        # 允许环境变量覆盖
        case_sensitive = False


# ------------------------------------------------------------
# 获取配置单例
# ------------------------------------------------------------
@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    settings = Settings()
    
    # 打印配置加载信息（仅首次加载时）
    print(f"[配置] 应用根目录: {APP_ROOT}")
    print(f"[配置] .env 文件路径: {APP_ROOT / '.env'}")
    print(f"[配置] .env 文件存在: {(APP_ROOT / '.env').exists()}")
    print(f"[配置] PLC 轮询间隔: {settings.plc_poll_interval}s (from .env)")
    print(f"[配置] 批量写入间隔: {settings.batch_write_size}次 (from .env)")
    print(f"[配置] PLC IP: {settings.plc_ip} (from .env)")
    print(f"[配置] Mock 模式: {settings.mock_mode}")
    
    return settings


# ------------------------------------------------------------
# 获取配置文件路径（支持打包后，优先使用根目录的配置）
# ------------------------------------------------------------
def get_config_path(relative_path: str) -> Path:
    """获取配置文件的绝对路径（支持用户修改）
    
    查找顺序:
    1. 根目录（.exe 旁边）- 用户可修改 ✅ 优先
    2. _internal 目录 - 打包时的备份（fallback）
    
    Args:
        relative_path: 相对路径，例如 "configs/db_mappings.yaml"
    
    Returns:
        绝对路径
    
    示例:
        打包后目录结构:
        dist/HopperBackend/
        ├── HopperBackend.exe
        ├── .env                    # 优先使用
        ├── configs/                # 优先使用（用户可修改）
        │   └── db_mappings.yaml
        └── _internal/
            ├── configs/            # fallback（打包时的备份）
            │   └── db_mappings.yaml
            └── ...
    """
    # 1. 优先使用根目录的配置文件（用户可修改）
    root_path = APP_ROOT / relative_path
    if root_path.exists():
        return root_path
    
    # 2. fallback: 使用 _internal 目录的配置文件（打包时的备份）
    internal_path = INTERNAL_ROOT / relative_path
    if internal_path.exists():
        print(f"[配置] 使用内部配置文件: {internal_path}")
        return internal_path
    
    # 3. 都不存在，返回根目录路径（让调用者处理文件不存在的情况）
    print(f"[配置警告] 配置文件不存在: {relative_path}")
    return root_path
