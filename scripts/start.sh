#!/bin/bash
# ============================================================
# 启动脚本 - 启动后端服务
# ============================================================

set -e

echo "=========================================="
echo "陶瓷车间后端服务启动脚本"
echo "=========================================="
echo "[提示] 请确保本地 InfluxDB 已启动 (http://localhost:8086)"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] Python 3 未安装"
    exit 1
fi

# 检查依赖
if [ ! -d "venv" ]; then
    echo "[步骤] 创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "[步骤] 安装依赖..."
pip install -r requirements.txt > /dev/null

# 启动后端
echo "[步骤] 启动后端服务..."
echo "=========================================="
uvicorn main:app --reload --host 0.0.0.0 --port 8080
