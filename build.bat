@echo off
chcp 65001 >nul
echo ============================================================
echo 料仓监控系统 - 打包脚本
echo ============================================================
echo.

echo [1/4] 清理旧的打包文件...
if exist dist\HopperBackend (
    rmdir /s /q dist\HopperBackend
    echo   已删除 dist\HopperBackend
)
if exist build (
    rmdir /s /q build
    echo   已删除 build
)
echo.

echo [2/4] 开始打包...
pyinstaller build_exe.spec --clean
if %errorlevel% neq 0 (
    echo.
    echo ❌ 打包失败！
    pause
    exit /b 1
)
echo.

echo [3/4] 验证打包结果...
if not exist dist\HopperBackend\HopperBackend.exe (
    echo ❌ 打包失败：找不到 HopperBackend.exe
    pause
    exit /b 1
)
if not exist dist\HopperBackend\.env (
    echo ❌ 打包失败：找不到 .env 文件
    pause
    exit /b 1
)
if not exist dist\HopperBackend\configs (
    echo ❌ 打包失败：找不到 configs 目录
    pause
    exit /b 1
)
echo   ✅ HopperBackend.exe
echo   ✅ .env
echo   ✅ configs/
echo   ✅ data/
echo   ✅ logs/
echo.

echo [4/4] 打包完成！
echo.
echo ============================================================
echo 打包后目录: dist\HopperBackend\
echo ============================================================
echo   HopperBackend.exe       主程序（双击启动）
echo   .env                    配置文件（用户可修改）✅
echo   configs\                配置目录（用户可修改）✅
echo   data\                   数据目录
echo   logs\                   日志目录
echo   _internal\              内部文件（不要修改）
echo ============================================================
echo.
echo 使用说明:
echo   1. 修改 .env 文件切换 Mock 模式或 PLC IP
echo   2. 修改 configs\ 目录下的 YAML 配置文件
echo   3. 重启 HopperBackend.exe 使配置生效
echo.
echo 详细说明: 查看 vdoc\PACKAGED_CONFIG_GUIDE.md
echo ============================================================
echo.
pause

