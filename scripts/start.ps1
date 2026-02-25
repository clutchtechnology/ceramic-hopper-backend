# ============================================================
# 一键启动脚本 (PowerShell)
# ============================================================
# 使用方法: .\start.ps1
# ============================================================

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "   陶瓷车间数字孪生系统 - 一键启动" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

Write-Host "[提示] 请确保本地 InfluxDB 已启动并可访问" -ForegroundColor Yellow
Write-Host "[提示] 默认地址: http://localhost:8086" -ForegroundColor Yellow

# 检查Python环境
Write-Host "`n[检查] Python环境..." -ForegroundColor Yellow
try {
    python --version
    Write-Host "[成功] Python环境正常" -ForegroundColor Green
}
catch {
    Write-Host "[错误] 未找到Python，请先安装Python 3.11+" -ForegroundColor Red
    exit 1
}

# 安装依赖
Write-Host "`n[检查] Python依赖..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt --quiet
    Write-Host "[成功] 依赖安装完成" -ForegroundColor Green
}
else {
    Write-Host "[警告] 未找到requirements.txt" -ForegroundColor Yellow
}

# 启动后端服务
Write-Host "`n[启动] FastAPI后端服务..." -ForegroundColor Yellow
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "[地址] API文档: " -NoNewline -ForegroundColor Cyan
Write-Host "http://localhost:8080/docs" -ForegroundColor White
Write-Host "[地址] 健康检查: " -NoNewline -ForegroundColor Cyan
Write-Host "http://localhost:8080/api/health" -ForegroundColor White
Write-Host "[模式] 运行模式: " -NoNewline -ForegroundColor Cyan
Write-Host "Mock模式 (无需PLC)" -ForegroundColor White
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "`n按 Ctrl+C 停止服务`n" -ForegroundColor Yellow

python main.py
