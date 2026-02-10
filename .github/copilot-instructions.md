# 料仓监控系统后端开发规则

## 项目标识

- **项目名称**: ceramic-hopper-backend
- **技术栈**: FastAPI + WebSocket + InfluxDB + Snap7
- **核心理念**: WebSocket 实时推送 + 本地 InfluxDB 部署 + 高可靠性轮询

---

## 架构原则

### 1. WebSocket 优先策略

- **实时推送**: 所有实时数据必须通过 WebSocket (`ws://host:port/ws/realtime`) 推送
- **推送间隔**: 0.1s (100ms) 极快响应
- **HTTP 降级**: HTTP API 仅用于历史数据查询和配置管理
- **连接管理**: 使用 `ws_manager.py` 统一管理连接、订阅和推送任务

### 2. 本地部署优先

- **InfluxDB**: 推荐本地安装，避免 Docker 网络延迟
- **配置**: `INFLUX_URL=http://localhost:8088`
- **性能**: 本地部署提供更快的数据写入和查询响应

### 3. 数据流架构

```
PLC/Mock → Polling Service (5s) → Memory Cache → WebSocket Push (0.1s) → Clients
                                 ↓
                            InfluxDB (批量写入) → HTTP Query
```

### 4. 配置驱动

- **config_hopper_4.yaml**: 唯一设备配置文件，定义4类传感器的内存映射
- **原则**: 新增传感器或调整参数时，优先修改 YAML，避免硬编码

---

## 核心组件

### WebSocket 层

**文件**: `app/services/ws_manager.py`, `app/routers/websocket.py`

- **ConnectionManager**: 单例模式，管理所有 WebSocket 连接
- **订阅频道**: `realtime` (实时数据)
- **心跳机制**: 客户端 15s 发送，服务端 45s 超时断开
- **推送任务**: `asyncio.create_task()` 异步推送，避免阻塞

**消息模型**: `app/models/ws_messages.py`
- 使用 Pydantic v2 进行消息验证
- 所有消息必须包含 `type` 字段
- 消息类型: `subscribe`, `unsubscribe`, `heartbeat`, `realtime_data`, `error`

### 轮询服务层

**文件**: `app/services/polling_service.py`

- **轮询间隔**: 5 秒
- **内存缓存**: 全局变量缓存最新数据，供 WebSocket 推送使用
- **双重写入**: 
  1. 更新内存缓存 (实时推送)
  2. 批量写入 InfluxDB (历史查询)
- **错误隔离**: 单个设备失败不影响整体轮询
- **Mock 模式**: `mock_mode=true` 时使用模拟数据

### PLC 通信层

**文件**: `app/plc/plc_manager.py`, `app/plc/parser_hopper_4.py`

- **连接管理**: 自动重连机制
- **数据解析**: 基于 YAML 配置的偏移量解析
- **长连接**: 单例维护 S7 连接，避免频繁握手

**python-snap7 库破坏性变更 (2.0.2)**:
```python
#  旧版 (1.x)
from snap7.types import PingTimeout
timeout = 9

#  新版 (2.0.2)
from snap7.type import Parameter
timeout = Parameter.PingTimeout  # 值为 3
```
- 参数 API 从 `snap7.types` 改为 `snap7.type.Parameter`
- `PingTimeout` 默认值从 9 改为 3
- 升级时需要更新 PLC 连接配置和超时设置

### 数据库层

**文件**: `app/core/influxdb.py`

- **Measurement**: `sensor_data`
- **Tags**: `device_id`, `device_type`, `module_type`
- **Fields**: 动态字段 (pm10, temperature, voltage, current, vibration, etc.)
- **批量写入**: 减少网络开销
- **本地降级**: InfluxDB 不可用时自动降级写入 SQLite (`LocalCache`)

---

## 设备数据结构

### 料仓传感器单元 (hopper_sensor_unit)

**设备**: 4号料仓综合监测单元 (`hopper_unit_4`)

**模块** (仅支持4类传感器):

1. **PM10 粉尘浓度** (`pm10`)
   - 字段: `pm10_value` (μg/m³)

2. **温度传感器** (`temperature`)
   - 字段: `temperature_value` (°C)

3. **三相电表** (`electricity`)
   - 字段: `Pt` (总功率), `ImpEp` (累计电量), `Ua_0`, `I_0`, `I_1`, `I_2` (电压电流)

4. **振动传感器** (`vibration_selected`)
   - 速度幅值: `vx`, `vy`, `vz`
   - 速度RMS: `vrms_x`, `vrms_y`, `vrms_z`
   - 波峰因素: `cf_x`, `cf_y`, `cf_z`
   - 峭度: `k_x`, `k_y`, `k_z`
   - 频率: `freq_x`, `freq_y`, `freq_z`
   - 温度: `temperature`
   - 故障诊断: `err_x`, `err_y`, `err_z`

---

## 编码规范

### 1. 命名规范

- **文件名**: 小写下划线 `snake_case.py`
- **类名**: 大驼峰 `PascalCase`
- **函数/变量**: 小写下划线 `snake_case`
- **常量**: 大写下划线 `UPPER_SNAKE_CASE`

### 2. 注释规范

**使用序号+注释风格**：

```python
# 1. 初始化 WebSocket 连接管理器
def __init__(self):
    self.active_connections = {}
    self.last_heartbeat = {}

# 2. 处理客户端连接
async def connect(self, websocket: WebSocket):
    await websocket.accept()
    self.active_connections[websocket] = set()
```

**文件头部注释**：
```python
"""
WebSocket 连接管理器 - 管理所有客户端连接和消息推送
"""
```

**禁止使用 Emoji 表情符号**：
- 原因: 编码兼容性、代码审查、专业性、版本控制、跨平台
- 正确: `# 1. 初始化连接管理器`
- 错误: `# 🚀 初始化连接管理器`

### 3. 代码设计原则 (奥卡姆剃刀)

**避免过度抽象**：
- 不要提前抽象：需要用的时候再抽象
- 避免冗余方法：一个文件不要抽象出太多方法
- 实用主义：能直接写就直接写

✅ **好的做法**：
```python
# 1. 推送实时数据
async def push_realtime_data(self, timestamp: str):
    latest = get_latest_data()
    message = {
        "type": "realtime_data",
        "timestamp": timestamp,
        "data": latest
    }
    await self.broadcast("realtime", message)
```

❌ **过度抽象**：
```python
def _format_timestamp(self, ts):
    return ts

def _create_message_header(self, msg_type):
    return {"type": msg_type}

def _add_timestamp(self, msg, ts):
    msg["timestamp"] = ts
    return msg

async def push_realtime_data(self, timestamp: str):
    latest = get_latest_data()
    header = self._create_message_header("realtime_data")
    message = self._add_timestamp(header, self._format_timestamp(timestamp))
    message["data"] = latest
    await self.broadcast("realtime", message)
```

### 4. WebSocket 代码规范

```python
# ✅ 正确：处理连接断开
try:
    await websocket.send_json(message)
except WebSocketDisconnect:
    manager.disconnect(websocket)
except Exception as e:
    logger.warning(f"发送失败: {e}")
    manager.disconnect(websocket)

# ✅ 正确：检查连接状态
if ws.application_state != WebSocketState.CONNECTED:
    manager.disconnect(ws)
    return

# ❌ 错误：不处理异常
await websocket.send_json(message)  # 可能导致服务崩溃
```

### 5. 异步任务规范

```python
# ✅ 正确：使用 asyncio.create_task
self._push_task = asyncio.create_task(self._push_loop())

# ✅ 正确：优雅停止任务
if self._push_task:
    self._push_task.cancel()
    try:
        await self._push_task
    except asyncio.CancelledError:
        pass

# ❌ 错误：直接 await 会阻塞
await self._push_loop()  # 会阻塞主线程
```

### 6. 内存缓存规范

```python
# ✅ 正确：使用全局缓存
_latest_data: Dict[str, Any] = {}

def get_latest_data() -> Dict[str, Any]:
    return _latest_data.copy()

# ✅ 正确：线程安全更新
def update_cache(device_id: str, data: dict):
    _latest_data[device_id] = data

# ❌ 错误：每次查询数据库
data = query_influxdb()  # 性能差
```

### 7. 日志规范

```python
# ✅ 正确：WebSocket 日志
logger.info(f"[WS] 新连接建立，当前连接数: {count}")
logger.debug(f"[WS] 推送 realtime_data -> {subs} 个订阅者")
logger.warning(f"[WS] 客户端心跳超时 ({delta:.0f}s)")

# ✅ 正确：错误日志包含 traceback
logger.error(f"[WS] 推送任务异常: {e}", exc_info=True)

# ❌ 错误：缺少上下文
logger.error("错误")  # 无法定位问题
```

### 8. 配置驱动规范

```python
# ✅ 正确：从 YAML 读取配置
config = load_yaml("configs/config_hopper_4.yaml")
offset = config["modules"][0]["offset"]

# ❌ 错误：硬编码
offset = 0  # 难以维护
```

---

## API 接口规范

### WebSocket 接口 (主要)

**端点**: `ws://localhost:8080/ws/realtime`

**客户端消息**:
```json
{"type": "subscribe", "channel": "realtime"}
{"type": "heartbeat", "timestamp": "2026-02-09T10:30:00Z"}
```

**服务端推送**:
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
      "timestamp": "2026-02-09T10:30:00.000Z",
      "modules": {
        "pm10": {
          "module_type": "pm10",
          "fields": {"pm10_value": 45.2}
        },
        "temperature": {
          "module_type": "temperature",
          "fields": {"temperature_value": 28.5}
        },
        "electricity": {
          "module_type": "electricity",
          "fields": {
            "Pt": 5.6,
            "ImpEp": 1234.5,
            "Ua_0": 380.5,
            "I_0": 12.3,
            "I_1": 12.1,
            "I_2": 12.4
          }
        },
        "vibration_selected": {
          "module_type": "vibration_selected",
          "fields": {
            "vx": 2.3,
            "vy": 2.1,
            "vz": 1.8,
            "vrms_x": 1.5,
            "vrms_y": 1.4,
            "vrms_z": 1.2,
            "freq_x": 50.2,
            "freq_y": 50.1,
            "freq_z": 50.3,
            "temperature": 45.6
          }
        }
      }
    }
  }
}
```

### HTTP 接口 (降级)

**Base URL**: `http://localhost:8080/api`

- `GET /hopper/realtime/batch`: 批量实时数据
- `GET /hopper/{device_id}/history`: 历史数据查询
- `GET /health`: 健康检查
- `GET /ws/status`: WebSocket 连接统计

**历史数据查询示例**:
```yaml
GET /api/hopper/{device_id}/history:
  参数:
    - sensor_type: string (pm10|temperature|electricity|vibration)
    - start: ISO 8601 datetime
    - end: ISO 8601 datetime
    - interval: string (5s|1m|5m|1h|1d)
  返回: [{ timestamp: '2026-02-09T10:00:00Z', value: 45.2 }, ...]
```

---

## 性能优化

### 1. 内存缓存优先

```python
# 优先级 1: 内存缓存 (最快)
cached_data = get_latest_data()

# 优先级 2: Mock 数据 (开发模式)
if settings.mock_mode:
    data = MockService.generate_hopper_data()

# 优先级 3: InfluxDB 查询 (降级)
data = query_data(measurement="sensor_data", ...)
```

### 2. 批量写入

```python
# ✅ 正确：批量写入 InfluxDB
points = []
for device_id, data in devices.items():
    points.append(Point("sensor_data").tag("device_id", device_id).field("pm10_value", data["pm10"]))
write_api.write(bucket=bucket, record=points)

# ❌ 错误：逐条写入
for device_id, data in devices.items():
    write_api.write(...)  # 性能差
```

### 3. 异步推送

```python
# ✅ 正确：异步推送，不阻塞
async def broadcast(self, channel: str, message: dict):
    tasks = []
    for ws, channels in self.active_connections.items():
        if channel in channels:
            tasks.append(ws.send_json(message))
    await asyncio.gather(*tasks, return_exceptions=True)

# ❌ 错误：同步推送，阻塞
for ws in connections:
    await ws.send_json(message)  # 串行执行
```

### 4. 批量写入大小优化

**问题**: 原磨料车间项目 `batch_write_size=30`，导致批量写入时 API 响应 2-5 秒延迟。

**解决方案**:
```python
# config.py
batch_write_size: int = 10  # 从30降到10，减少阻塞时间
```

---

## 错误处理

### 1. WebSocket 错误

```python
# ✅ 必须处理的异常
try:
    await websocket.send_json(message)
except WebSocketDisconnect:
    # 客户端主动断开
    manager.disconnect(websocket)
except RuntimeError as e:
    # 连接已关闭
    if "WebSocket is not connected" in str(e):
        manager.disconnect(websocket)
except Exception as e:
    # 其他未知错误
    logger.error(f"发送失败: {e}", exc_info=True)
    manager.disconnect(websocket)
```

### 2. 轮询错误 (防止服务崩溃)

```python
# ✅ 正确：宽泛的异常捕获，防止服务崩溃
async def polling_loop():
    while is_running():
        try:
            data = await poll_plc()
            update_cache(data)
            await asyncio.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.error(f"轮询异常: {e}", exc_info=True)
            await asyncio.sleep(POLL_INTERVAL)  # 继续运行，不退出
```

### 3. 数据库错误 (降级策略)

```python
# ✅ 正确：降级到本地缓存
try:
    write_api.write(bucket=bucket, record=points)
except Exception as e:
    logger.error(f"InfluxDB 写入失败: {e}")
    # 降级到 SQLite 本地缓存
    local_cache.save(points)
```

### 4. PLC 重连机制

```python
#  PLCManager 必须实现自动重连
def reconnect(self):
    max_retries = 3
    for i in range(max_retries):
        try:
            self._client.connect()
            logger.info("PLC reconnected successfully")
            return True
        except Exception as e:
            logger.warning(f"Reconnect attempt {i+1} failed: {e}")
            time.sleep(2 ** i)  # 指数退避
    return False
```

---

## 开发流程

### 1. 启动服务

```bash
# 本地开发 (推荐)
uvicorn main:create_app --factory --host 0.0.0.0 --port 8080 --reload

# Mock 模式
python main.py

# 生产模式
mock_mode=false python main.py
```

### 2. 测试 WebSocket

```bash
# 使用 websocat 测试
websocat ws://localhost:8080/ws/realtime

# 发送订阅消息
{"type": "subscribe", "channel": "realtime"}

# 发送心跳
{"type": "heartbeat", "timestamp": "2026-02-09T10:30:00Z"}
```

### 3. 查看日志

```bash
# 查看 WebSocket 连接日志
grep "[WS]" logs/app.log

# 查看推送日志
grep "推送" logs/app.log
```

---

## 常见问题

### 1. WebSocket 连接断开

**原因**: 心跳超时、网络中断、客户端崩溃

**解决**:
- 检查客户端心跳间隔 (应 < 45s)
- 实现客户端重连机制 (指数退避)
- 查看服务端日志 `[WS]` 标记

### 2. 推送延迟高

**原因**: 推送间隔过大、数据库查询慢、内存缓存未命中

**解决**:
- 检查 `PUSH_INTERVAL` 配置 (默认 0.1s)
- 确保轮询服务正常运行
- 优先使用内存缓存，避免查询数据库

### 3. 内存持续增长

**原因**: WebSocket 连接未清理、缓存无限增长

**解决**:
- 检查 `disconnect()` 是否正确调用
- 实现心跳超时清理机制
- 限制缓存大小 (如只保留最新 1000 条)

### 4. InfluxDB 连接失败

**原因**: 服务未启动、端口错误、认证失败

**解决**:
- 检查 InfluxDB 服务状态
- 确认 `INFLUX_URL=http://localhost:8088`
- 验证 Token 和 Bucket 配置

---

## 文件结构速查

```
ceramic-hopper-backend/
├── main.py                           # 入口 (Lifespan 管理)
├── config.py                         # 全局配置
├── configs/                          # YAML 配置文件
│   ├── config_hopper_4.yaml          # ★ 料仓设备数据点映射
│   ├── db_mappings.yaml              # DB 块映射
│   └── plc_modules.yaml              # 模块定义
├── app/
│   ├── models/
│   │   ├── ws_messages.py            # ★ WebSocket 消息模型
│   │   └── response.py               # HTTP 响应模型
│   ├── services/
│   │   ├── ws_manager.py             # ★ WebSocket 连接管理器
│   │   ├── polling_service.py        # ★ 轮询服务
│   │   └── mock_service.py           # Mock 数据生成
│   ├── routers/
│   │   ├── websocket.py              # ★ WebSocket 路由
│   │   ├── hopper_4.py               # HTTP 实时数据接口
│   │   ├── health.py                 # 健康检查
│   │   ├── config.py                 # 配置管理
│   │   └── alarms.py                 # 报警管理
│   ├── plc/
│   │   ├── plc_manager.py            # PLC 连接管理
│   │   └── parser_hopper_4.py        # 数据解析器
│   └── core/
│       ├── influxdb.py               # InfluxDB 封装
│       └── local_cache.py            # SQLite 降级缓存
└── docs/
    └── WEBSOCKET_PROTOCOL.md         # ★ WebSocket 协议规范
```

---

## Mock 数据生成 (开发模式)

```python
# 当 mock_mode=true 时，自动生成模拟数据
def generate_mock_data():
    return {
        "pm10": {"pm10_value": random.uniform(20, 50)},
        "temperature": {"temperature_value": random.uniform(25, 35)},
        "electricity": {
            "Pt": random.uniform(5, 10),
            "Ua_0": random.uniform(370, 390),
            "I_0": random.uniform(10, 20),
        },
        "vibration": {
            "vx": random.uniform(0.3, 0.8),
            "vy": random.uniform(0.2, 0.6),
            "vz": random.uniform(0.3, 0.7),
        },
    }
```

---

## 代码审查清单

- [ ] 所有轮询逻辑都有 `try-except` 保护
- [ ] `batch_write_size` 设置为 10 (不超过 20)
- [ ] InfluxDB 客户端使用 `@lru_cache()` 单例
- [ ] PLC 连接失败时有重连机制
- [ ] API 响应时间 < 200ms (批量写入不阻塞)
- [ ] 日志包含时间戳和 traceback
- [ ] 配置文件中没有硬编码 IP 地址
- [ ] Mock 模式可以独立运行
- [ ] WebSocket 连接正确处理断开、超时和重连
- [ ] 所有异步任务使用 `asyncio.create_task()`
- [ ] 内存缓存优先于数据库查询
- [ ] 错误日志包含 `exc_info=True`

---

## AI 编码指令

1. **WebSocket 优先**: 实时数据推送必须使用 WebSocket，HTTP 仅作降级
2. **本地部署**: 推荐本地 InfluxDB，避免 Docker 延迟
3. **内存缓存**: 优先使用内存缓存，减少数据库查询
4. **异常处理**: 所有 I/O 操作必须有异常处理和重试机制
5. **连接管理**: WebSocket 连接必须正确处理断开、超时和重连
6. **批量写入**: InfluxDB 写入使用批量模式，减少网络开销
7. **异步推送**: 使用 `asyncio.create_task()` 异步推送，避免阻塞
8. **日志规范**: 关键操作必须记录日志，错误日志包含 traceback
9. **配置驱动**: 优先修改 YAML 配置，避免硬编码
10. **协议规范**: 严格遵循 `docs/WEBSOCKET_PROTOCOL.md` 定义的消息格式
11. **简单至上**: 能用简单逻辑实现的，不要引入复杂的类层次结构
12. **防崩溃**: 任何涉及 I/O (网络, 数据库, PLC) 的操作必须有超时和重试机制
13. **清晰日志**: 报错时产生的日志必须包含 traceback 和上下文信息
14. **删除冗余**: 删除所有不需要的设备类型和代码
15. **不使用emoji** :任何时候不适用emoji表情做注释或者是log等一些,我的项目不允许出现emoji.
16. **每次回复** :喊我大王.
---

## 参考文档

- `docs/WEBSOCKET_PROTOCOL.md` - WebSocket 协议规范
- `README.md` - 项目说明
- `configs/*.yaml` - 设备配置文件
- `.cursor/rules/hopper.mdc` - 完整开发规则

---

**使用中文回复。**

