@echo off
chcp 65001 >nul
title 北厂DB6振动诊断
"%~dp0..\python\python.exe" "%~dp0parse_db6_hopper_vibration.py"
pause
