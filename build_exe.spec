# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# 1. 获取 snap7.dll 的路径
_snap7_dll = os.path.join(sys.prefix, 'Lib', 'site-packages', 'snap7', 'lib', 'snap7.dll')

# 2. 分析阶段
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(_snap7_dll, 'snap7/lib')],
    datas=[
        ('configs', 'configs'),
        ('data', 'data'),
        ('.env', '.'),
    ],
    hiddenimports=[
        # FastAPI / Uvicorn
        'uvicorn',
        'fastapi',
        # PyQt5 (系统托盘)
        'PyQt5',
        # Snap7 (PLC通信) - python-snap7 2.0.2 使用 snap7.type (非 types)
        'snap7',
        'snap7.client',
        'snap7.common',
        'snap7.util',
        'snap7.error',
        'snap7.type',
        # InfluxDB
        'influxdb_client',
        'influxdb_client.client',
        'influxdb_client.client.write_api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthooks/pyi_rth_snap7.py'],
    excludes=['sqlalchemy'],
    noarchive=False,
    optimize=0,
)

# 3. 打包阶段
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HopperBackend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# 4. 收集所有文件到 dist/HopperBackend 目录
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HopperBackend',
)

# 5. 打包后处理：复制配置文件到根目录（用户可修改）
# 说明：
# - PyInstaller 会把 datas 放到 _internal/ 目录
# - 我们需要额外复制一份到根目录，供用户修改
# - 程序会优先读取根目录的配置文件
import shutil
from pathlib import Path

dist_dir = Path('dist/HopperBackend')

# 复制 .env 文件到根目录
if Path('.env').exists():
    shutil.copy('.env', dist_dir / '.env')
    print(f"[打包] 已复制 .env 到根目录")

# 复制 configs 目录到根目录
if Path('configs').exists():
    if (dist_dir / 'configs').exists():
        shutil.rmtree(dist_dir / 'configs')
    shutil.copytree('configs', dist_dir / 'configs')
    print(f"[打包] 已复制 configs/ 到根目录")

# 创建 data 目录（用于存放 cache.db）
(dist_dir / 'data').mkdir(exist_ok=True)
print(f"[打包] 已创建 data/ 目录")

# 创建 logs 目录（用于存放日志）
(dist_dir / 'logs').mkdir(exist_ok=True)
print(f"[打包] 已创建 logs/ 目录")

print(f"\n[打包完成] 目录结构:")
print(f"  dist/HopperBackend/")
print(f"  ├── HopperBackend.exe       # 主程序")
print(f"  ├── .env                    # 配置文件（用户可修改）✅")
print(f"  ├── configs/                # 配置目录（用户可修改）✅")
print(f"  ├── data/                   # 数据目录")
print(f"  ├── logs/                   # 日志目录")
print(f"  └── _internal/              # PyInstaller 内部文件（不要修改）")
print(f"      ├── configs/            # 配置备份（fallback）")
print(f"      └── ...")
print(f"\n[使用说明] 修改根目录的 .env 和 configs/ 后，重启程序即可生效")