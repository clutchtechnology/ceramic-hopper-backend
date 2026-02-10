@echo off
chcp 65001 >nul
echo ========================================
echo  HopperBackend - PyInstaller 打包脚本
echo ========================================
echo.

REM 1. 检查 PyInstaller
echo [1/5] 检查 PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller 未安装, 正在安装...
    pip install pyinstaller
    if errorlevel 1 (
        echo 安装 PyInstaller 失败!
        pause
        exit /b 1
    )
) else (
    echo PyInstaller 已安装
)
echo.

REM 2. 清理旧的打包文件
echo [2/5] 清理旧的打包文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo 清理完成
echo.

REM 3. 开始打包
echo [3/5] 开始打包...
echo 这可能需要几分钟时间, 请耐心等待...
echo.
pyinstaller build_exe.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo 打包失败! 请检查错误信息。
    pause
    exit /b 1
)
echo.

REM 4. 复制配置文件到 dist 目录
echo [4/5] 复制配置文件...
if not exist dist\HopperBackend\configs mkdir dist\HopperBackend\configs
xcopy /E /I /Y configs dist\HopperBackend\configs
if exist .env copy /Y .env dist\HopperBackend\.env
echo 配置文件复制完成
echo.

REM 5. 打包完成
echo [5/5] 打包完成!
echo.
echo ========================================
echo 打包结果:
echo   可执行文件: dist\HopperBackend\HopperBackend.exe
echo   配置文件: dist\HopperBackend\configs\
echo   环境变量: dist\HopperBackend\.env
echo   数据目录: dist\HopperBackend\data\
echo   日志目录: dist\HopperBackend\logs\ (运行时自动创建)
echo.
echo 目录结构:
echo   dist\HopperBackend\
echo     ├── _internal\      (依赖库)
echo     ├── configs\        (配置文件)
echo     ├── data\           (数据库缓存)
echo     ├── logs\           (日志文件, 运行时创建)
echo     ├── HopperBackend.exe
echo     └── .env            (环境变量)
echo.
dir dist\HopperBackend | find "个文件"
echo ========================================
echo.
echo 提示:
echo   1. 运行前请确保 .env 配置正确
echo   2. 如需连接真实 PLC, 请修改 .env 中 mock_mode=false
echo   3. 确保 InfluxDB 服务已启动
echo   4. 首次运行会自动创建 logs 目录
echo.
pause
