@echo off
chcp 65001 >nul
title DB4 料仓传感器 (南厂 PLC: 192.168.50.224)
"%~dp0..\python\python.exe" "%~dp0parse_db4_hopper_sensors.py"
pause
