# PLC 长连接优化报告

## 优化目标

1. 保持 PLC 长连接，避免频繁连接/断开
2. 减少失败重试频率，避免过度重连
3. 提高连接稳定性和可靠性

## 优化内容

### 1. plc_manager.py 优化

#### 1.1 重试机制优化

**优化前**：
```python
self._reconnect_interval: float = 5.0  # 重连间隔（秒）
self._max_reconnect_attempts: int = 3  # 最大重连次数
self._health_check_interval: float = 30.0  # 健康检查间隔
self._max_consecutive_errors: int = 10  # 连续错误达到此值则强制重连
time.sleep(0.5)  # 重试延迟 0.5 秒
```

**优化后**：
```python
self._reconnect_interval: float = 10.0  # 重连间隔（秒）- 增加到 10s
self._max_reconnect_attempts: int = 2  # 最大重连次数 - 减少到 2 次
self._health_check_interval: float = 60.0  # 健康检查间隔 - 增加到 60s
self._max_consecutive_errors: int = 20  # 连续错误达到此值则强制重连 - 增加到 20 次
self._retry_delay: float = 2.0  # 重试延迟（秒）- 增加到 2s
time.sleep(self._retry_delay)  # 使用配置的重试延迟
```

**优化效果**：
- 重连间隔从 5s 增加到 10s，减少频繁重连
- 最大重连次数从 3 次减少到 2 次，快速失败
- 健康检查间隔从 30s 增加到 60s，减少不必要的检查
- 连续错误阈值从 10 次增加到 20 次，更宽容的容错
- 重试延迟从 0.5s 增加到 2s，给 PLC 更多恢复时间

#### 1.2 连接状态管理优化

**优化前**：
```python
self._connected = True
self._error_count = 0  # 只重置总错误计数
```

**优化后**：
```python
self._connected = True
self._consecutive_error_count = 0  # 连接成功后重置连续错误计数
print(f"✅ PLC 已连接 ({self._ip}) [第 {self._connect_count} 次] - 保持长连接")
```

**优化效果**：
- 连接成功后立即重置连续错误计数
- 日志明确标注"保持长连接"

### 2. s7_client.py 优化

#### 2.1 长连接机制

**优化前**：
```python
def connect(self) -> bool:
    # 每次都创建新连接
    self.client.connect(self.ip, self.rack, self.slot)
    return True

def read_db_block(self, db_number: int, start: int, size: int) -> bytes:
    if not self.client or not self.client.get_connected():
        raise ConnectionError("PLC未连接")
    # 读取后不管连接状态
```

**优化后**：
```python
def connect(self) -> bool:
    # 如果已连接，检查连接是否有效
    if self._connected and self.client:
        try:
            if self.client.get_connected():
                return True  # 复用现有连接
        except Exception:
            self._connected = False
    
    # 建立新连接
    self.client.connect(self.ip, self.rack, self.slot)
    self._connected = True
    print(f"✅ PLC 长连接已建立: {self.ip}")
    return True

def read_db_block(self, db_number: int, start: int, size: int) -> bytes:
    # 带自动重连的读取
    for attempt in range(self._max_retry_attempts):
        try:
            # 确保连接
            if not self._connected or not self.client or not self.client.get_connected():
                self.connect()
            
            # 读取数据
            return self.client.db_read(db_number, start, size)
        except Exception as e:
            if attempt >= self._max_retry_attempts - 1:
                raise Exception(f"读取DB{db_number}失败（已重试{self._max_retry_attempts}次）: {e}")
            
            # 重试前断开连接，等待后重连
            self._connected = False
            time.sleep(self._retry_delay)
```

**优化效果**：
- 连接建立后保持长连接，不主动断开
- 读取数据时自动检查连接状态，必要时重连
- 重试机制更加智能，避免频繁重连

#### 2.2 单例模式优化

**优化前**：
```python
def get_s7_client() -> S7Client:
    global _s7_client
    if _s7_client is None:
        _s7_client = S7Client(...)
    return _s7_client
```

**优化后**：
```python
def get_s7_client() -> S7Client:
    global _s7_client
    if _s7_client is None:
        with _s7_client_lock:
            if _s7_client is None:
                _s7_client = S7Client(...)
                # 自动建立长连接
                try:
                    _s7_client.connect()
                except Exception as e:
                    print(f"⚠️ 初始化 PLC 连接失败: {e}")
    return _s7_client
```

**优化效果**：
- 单例创建时自动建立长连接
- 线程安全的双重检查锁定
- 连接失败不影响单例创建

#### 2.3 新增手动重连方法

```python
def reconnect(self) -> bool:
    """手动重连PLC"""
    self.disconnect()
    time.sleep(1.0)
    try:
        return self.connect()
    except Exception:
        return False
```

**优化效果**：
- 提供手动重连接口，方便外部调用
- 重连前先断开旧连接，确保干净的连接状态

## 优化参数对比

| 参数 | 优化前 | 优化后 | 说明 |
|-----|-------|-------|------|
| 重连间隔 | 5s | 10s | 减少频繁重连 |
| 最大重连次数 | 3 次 | 2 次 | 快速失败 |
| 健康检查间隔 | 30s | 60s | 减少不必要的检查 |
| 连续错误阈值 | 10 次 | 20 次 | 更宽容的容错 |
| 重试延迟 | 0.5s | 2s | 给 PLC 更多恢复时间 |

## 使用建议

### 1. 推荐使用 plc_manager.py

```python
from app.plc.plc_manager import get_plc_manager

# 获取 PLC 管理器（单例，自动建立长连接）
plc_manager = get_plc_manager()

# 读取数据（自动重连）
success, data, error = plc_manager.read_db(db_number=8, start=0, size=100)
if success:
    print(f"读取成功: {len(data)} 字节")
else:
    print(f"读取失败: {error}")

# 检查连接状态
if plc_manager.is_connected():
    print("PLC 已连接")

# 获取详细状态
status = plc_manager.get_status()
print(f"连接次数: {status['connect_count']}")
print(f"错误次数: {status['error_count']}")
```

### 2. 备用方案：使用 s7_client.py

```python
from app.plc.s7_client import get_s7_client

# 获取 S7 客户端（单例，自动建立长连接）
client = get_s7_client()

# 读取数据（自动重连）
try:
    data = client.read_db_block(db_number=8, start=0, size=100)
    print(f"读取成功: {len(data)} 字节")
except Exception as e:
    print(f"读取失败: {e}")

# 检查连接状态
if client.is_connected():
    print("PLC 已连接")

# 手动重连
if not client.is_connected():
    client.reconnect()
```

## 注意事项

1. **长连接维护**：连接建立后会一直保持，直到程序退出或手动断开
2. **自动重连**：读取失败时会自动尝试重连，最多重试 2 次
3. **线程安全**：两个实现都是线程安全的，可以在多线程环境中使用
4. **错误容忍**：连续 20 次错误后才会强制重连，避免频繁重连
5. **重试延迟**：每次重试前会等待 2 秒，给 PLC 足够的恢复时间

## 测试建议

### 1. 正常连接测试

```bash
# 启动后端服务
python main.py

# 观察日志，应该看到：
# ✅ PLC 已连接 (192.168.x.x) [第 1 次] - 保持长连接
```

### 2. 断线重连测试

```bash
# 1. 启动服务
python main.py

# 2. 断开 PLC 网络连接

# 3. 观察日志，应该看到：
# ⚠️ DB8 读取失败 (尝试 1/2): ...
# ⚠️ 连续 X 次错误，强制重连 PLC...

# 4. 恢复 PLC 网络连接

# 5. 观察日志，应该看到：
# ✅ PLC 已连接 (192.168.x.x) [第 2 次] - 保持长连接
```

### 3. 性能测试

```python
import time
from app.plc.plc_manager import get_plc_manager

plc_manager = get_plc_manager()

# 测试连续读取性能
start_time = time.time()
success_count = 0
error_count = 0

for i in range(100):
    success, data, error = plc_manager.read_db(8, 0, 100)
    if success:
        success_count += 1
    else:
        error_count += 1

elapsed = time.time() - start_time
print(f"总耗时: {elapsed:.2f}s")
print(f"成功: {success_count} 次")
print(f"失败: {error_count} 次")
print(f"平均耗时: {elapsed/100*1000:.2f}ms/次")
```

## 总结

通过本次优化，PLC 连接机制已经从短连接改为长连接，并且大幅减少了重试频率：

1. 连接建立后保持长连接，不主动断开
2. 重连间隔从 5s 增加到 10s
3. 最大重连次数从 3 次减少到 2 次
4. 重试延迟从 0.5s 增加到 2s
5. 连续错误阈值从 10 次增加到 20 次

这些优化将显著提高 PLC 连接的稳定性和可靠性，减少不必要的网络开销。

