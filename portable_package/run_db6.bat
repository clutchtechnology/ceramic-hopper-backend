@echo off
chcp 65001 >nul
title DB6 振动传感器完整数据解析

echo ========================================
echo   DB6 振动传感器完整数据解析
echo   PLC: 192.168.50.235
echo   DB: 6 (38 bytes)
echo ========================================
echo.

python\python.exe parse_db6_hopper_vib.py

pause

