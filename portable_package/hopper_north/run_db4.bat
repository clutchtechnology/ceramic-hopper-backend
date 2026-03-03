@echo off
chcp 65001 >nul
echo === DB4 料仓传感器 (北厂) ===
"%~dp0..\python\python.exe" "%~dp0parse_db4_hopper_sensors.py"
pause
