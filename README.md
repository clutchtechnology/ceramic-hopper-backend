# 料仓监控系统后端 (Ceramic Hopper Backend)

基于 FastAPI + WebSocket + InfluxDB + Snap7 的料仓实时监控系统后端。

## 特性

- **WebSocket 实时推送**: 0.1s 级别的实时数据推送
- **高性能架构**: 内存缓存 + 后台异步写入
- **Mock 模式**: 支持模拟数据，便于开发测试
- **批量写入**: 减少数据库压力，提高性能
- **自动重连**: PLC 连接自动重连机制
- **本地缓存**: InfluxDB 故障时自动降级到 SQLite
- **心跳检测**: 自动清理超时连接

## 技术栈

- **Python**: 3.12+
- **FastAPI**: 0.109.0
- **WebSocket**: 实时双向通信
- **InfluxDB**: 2.x 时序数据库
- **Snap7**: PLC 通信库
- **Pydantic**: v2 数据验证

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 InfluxDB

```bash
# 启动 InfluxDB (本地安装)
influxd
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
# 复制配置文件
copy .env.example .env

# 编辑配置文件
notepad .env
```

**主要配置项**：

```bash
# Mock 模式 (开发环境)
MOCK_MODE=true

# PLC 配置 (生产环境)
MOCK_MODE=false
PLC_IP=192.168.50.235
PLC_RACK=0
PLC_SLOT=1

# InfluxDB 配置
INFLUX_URL=http://localhost:8088
INFLUX_TOKEN=ceramic-workshop-token
INFLUX_ORG=ceramic-workshop
INFLUX_BUCKET=sensor_data

# 批量写入配置
BATCH_WRITE_SIZE=12
PLC_POLL_INTERVAL=5
```

完整配置说明请查看 `.env.example` 文件。

### 4. 启动服务

#### Mock 模式 (推荐用于开发)

```bash
# Windows
start_mock.bat

# Linux/Mac
python main.py
```

#### 生产模式 (连接真实 PLC)

```bash
# Windows
start_production.bat

# Linux/Mac
mock_mode=false python main.py
```

### 5. 测试 WebSocket

```bash
# 使用 Python 测试脚本
python test_websocket.py

# 或使用 websocat
websocat ws://localhost:8080/ws/realtime
```

## API 文档

### HTTP API

启动服务后访问: http://localhost:8080/docs

主要端点：
- `GET /api/health` - 健康检查
- `GET /api/hopper/realtime/batch` - 批量实时数据
- `GET /api/hopper/{device_id}/history` - 历史数据查询
- `GET /ws/status` - WebSocket 连接统计

### WebSocket API

**端点**: `ws://localhost:8080/ws/realtime`

**订阅消息**:
```json
{"type": "subscribe", "channel": "realtime"}
```

**心跳消息**:
```json
{"type": "heartbeat", "timestamp": "2026-02-09T10:30:00Z"}
```

**实时数据推送** (0.1s 间隔):
```json
{
  "type": "realtime_data",
  "success": true,
  "timestamp": "2026-02-09T10:30:00.000Z",
  "source": "plc",
  "data": {
    "hopper_unit_4": {
      "device_id": "hopper_unit_4",
      "device_name": "4号料仓综合监测单元",
      "device_type": "hopper_sensor_unit",
      "modules": {
        "pm10": {"fields": {"pm10_value": 45.2}},
        "temperature": {"fields": {"temperature_value": 28.5}},
        "electricity": {"fields": {"Pt": 5.6, "ImpEp": 1234.5}},
        "vibration_selected": {"fields": {"vrms_x": 1.5, "vrms_y": 1.4}}
      }
    }
  }
}
```

详细协议规范: [docs/WEBSOCKET_PROTOCOL.md](docs/WEBSOCKET_PROTOCOL.md)

## 项目结构

```
ceramic-hopper-backend/
├── main.py                           # 应用入口
├── config.py                         # 全局配置
├── start_mock.bat                    # Mock 模式启动脚本
├── start_production.bat              # 生产模式启动脚本
├── test_websocket.py                 # WebSocket 测试脚本
├── configs/                          # 配置文件
│   ├── config_hopper_4.yaml          # 料仓设备配置
│   ├── db_mappings.yaml              # DB 块映射
│   └── plc_modules.yaml              # 模块定义
├── app/
│   ├── models/
│   │   ├── ws_messages.py            # WebSocket 消息模型
│   │   └── response.py               # HTTP 响应模型
│   ├── services/
│   │   ├── ws_manager.py             # WebSocket 连接管理器
│   │   ├── polling_service.py        # 轮询服务
│   │   └── mock_service.py           # Mock 数据生成
│   ├── routers/
│   │   ├── websocket.py              # WebSocket 路由
│   │   ├── hopper_4.py               # HTTP API
│   │   ├── health.py                 # 健康检查
│   │   ├── config.py                 # 配置管理
│   │   └── alarms.py                 # 报警管理
│   ├── plc/
│   │   ├── plc_manager.py            # PLC 连接管理
│   │   └── parser_hopper_4.py        # 数据解析器
│   └── core/
│       ├── influxdb.py               # InfluxDB 封装
│       └── local_cache.py            # SQLite 降级缓存
├── docs/
│   └── WEBSOCKET_PROTOCOL.md         # WebSocket 协议规范
└── vdoc/
    ├── WEBSOCKET_REFACTOR_COMPLETE.md # 重构完成报告
    └── WEBSOCKET_TEST_GUIDE.md        # 测试指南
```

## 数据流架构

```
PLC/Mock → 轮询服务(5s) → 内存缓存 → WebSocket 推送(0.1s) → 客户端
                        ↓
                   InfluxDB (批量写入 60s)
```

## 设备数据

### 4号料仓综合监测单元

**设备ID**: `hopper_unit_4`

**模块**:
1. **PM10 粉尘浓度** (`pm10`)
   - `pm10_value`: PM10 浓度 (μg/m³)

2. **温度传感器** (`temperature`)
   - `temperature_value`: 温度 (°C)

3. **三相电表** (`electricity`)
   - `Pt`: 总功率 (kW)
   - `ImpEp`: 累计电量 (kWh)
   - `Ua_0`, `I_0`, `I_1`, `I_2`: 电压电流

4. **振动传感器** (`vibration_selected`)
   - 速度幅值: `vx`, `vy`, `vz`
   - 速度RMS: `vrms_x`, `vrms_y`, `vrms_z`
   - 波峰因素: `cf_x`, `cf_y`, `cf_z`
   - 峭度: `k_x`, `k_y`, `k_z`
   - 频率: `freq_x`, `freq_y`, `freq_z`
   - 温度: `temperature`
   - 故障诊断: `err_x`, `err_y`, `err_z`

## 性能指标

- **推送延迟**: < 200ms
- **推送频率**: 10 次/秒 (0.1s 间隔)
- **轮询间隔**: 5 秒
- **批量写入**: 60 秒 (12 次轮询)
- **心跳超时**: 45 秒
- **内存占用**: < 100MB
- **CPU 占用**: < 10%

## 开发指南

### 添加新设备

1. 在 `configs/` 中创建设备配置文件
2. 在 `app/plc/` 中创建解析器
3. 在 `configs/db_mappings.yaml` 中注册设备
4. 重启服务

### 添加新模块

1. 在 `configs/plc_modules.yaml` 中定义模块
2. 在 `app/tools/` 中创建转换器（如需要）
3. 更新设备配置文件

### 调试技巧

```bash
# 查看实时日志
tail -f logs/app.log

# 查看轮询统计
curl http://localhost:8080/api/health | python -m json.tool

# 查看 WebSocket 连接
curl http://localhost:8080/ws/status | python -m json.tool

# 启用详细日志
verbose_polling_log=true python main.py
```

## 常见问题

### Q: WebSocket 连接失败？

A: 检查后端服务是否启动，端口是否被占用：
```bash
netstat -ano | findstr :8080
```

### Q: 数据不推送？

A: 检查轮询服务是否运行：
```bash
curl http://localhost:8080/api/health
```

### Q: InfluxDB 连接失败？

A: 检查 InfluxDB 服务状态和配置：
```bash
curl http://localhost:8088/health
```

### Q: 如何切换到生产模式？

A: 修改环境变量：
```bash
mock_mode=false
plc_ip=192.168.50.235
```

## 部署

### 生产部署

1. 安装依赖: `pip install -r requirements.txt`
2. 配置环境变量
3. 启动 InfluxDB
4. 启动服务: `python main.py`
5. 配置反向代理 (Nginx)
6. 配置系统服务 (systemd)

## 许可证

MIT License

## 联系方式

- 项目地址: https://github.com/your-org/ceramic-hopper-backend
- 问题反馈: https://github.com/your-org/ceramic-hopper-backend/issues

---

**版本**: 1.0.0  
**更新日期**: 2026-02-09  
**维护者**: ClutchTech Team
