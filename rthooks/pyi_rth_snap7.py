"""
PyInstaller runtime hook for snap7
"""
import os
import sys

# 1. 获取 _internal 目录路径
if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# 2. 添加 snap7/lib 目录到 DLL 搜索路径
snap7_lib_path = os.path.join(base_path, 'snap7', 'lib')

if os.path.exists(snap7_lib_path):
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(snap7_lib_path)
    os.environ['PATH'] = snap7_lib_path + os.pathsep + os.environ.get('PATH', '')
