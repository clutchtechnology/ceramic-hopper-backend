"""
数据轮询服务 - 料仓监控系统

功能:
    1. PLC 长连接 (避免频繁连接/断开)
    2. 批量写入 (12 次轮询后批量写入)
    3. 本地降级缓存 (InfluxDB 故障时写入 SQLite)
    4. 自动重试机制 (缓存数据自动重试)
    5. 内存缓存 (供 WebSocket 推送和 API 读取)
    6. Mock模式支持 (使用模拟数据替代真实PLC)
    7. 后台异步写入 (不阻塞轮询和推送)
"""

import asyncio
import yaml
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from collections import deque

from config import get_settings, get_config_path
from app.core.timezone_utils import now_beijing, beijing_isoformat
from app.core.influxdb import build_point, write_points_batch, check_influx_health
from app.core.local_cache import get_local_cache, CachedPoint
from app.plc.plc_manager import get_plc_manager
from app.plc.parser_hopper_4 import Hopper4Parser
from app.plc.parser_vib_db6 import VibDB6Parser
from app.tools import get_converter, CONVERTER_MAP

settings = get_settings()

# 轮询任务句柄
_polling_task: Optional[asyncio.Task] = None
_retry_task: Optional[asyncio.Task] = None
_cleanup_task: Optional[asyncio.Task] = None
_write_task: Optional[asyncio.Task] = None
_is_running = False

# 解析器实例
_parsers: Dict[int, Any] = {}

# DB映射配置
_db_mappings: List[Dict[str, Any]] = []

# ============================================================
# 内存缓存 (供 WebSocket 推送和 API 读取)
# ============================================================
_data_lock = threading.Lock()
_latest_data: Dict[str, Any] = {}  # {device_id: device_data}
_latest_timestamp: Optional[datetime] = None

# 数据更新事件 (通知 WS 推送)
_data_updated_event: Optional[asyncio.Event] = None


def get_data_updated_event() -> asyncio.Event:
    """获取数据更新事件 (延迟创建, 须在事件循环内调用)"""
    global _data_updated_event
    if _data_updated_event is None:
        _data_updated_event = asyncio.Event()
    return _data_updated_event

# ============================================================
# 批量写入缓存
# ============================================================
_point_buffer: deque = deque(maxlen=1000)
_buffer_count = 0
_batch_size = 12  # 12次轮询后批量写入（约60秒一次）
_poll_interval = settings.plc_poll_interval

# 后台写入任务控制
_write_queue: Optional[asyncio.Queue] = None
_write_in_progress = False

# ============================================================
# 统计信息
# ============================================================
_stats = {
    "total_polls": 0,
    "successful_writes": 0,
    "failed_writes": 0,
    "cached_points": 0,
    "retry_success": 0,
    "last_write_time": None,
    "last_retry_time": None,
}


# ------------------------------------------------------------
# 1. _load_db_mappings() - 加载DB映射配置
# ------------------------------------------------------------
def _load_db_mappings() -> List[Tuple[int, int]]:
    """从配置文件加载DB映射
    
    配置优先级:
    1. .env 文件中的 PLC_POLL_INTERVAL 和 BATCH_WRITE_SIZE（最高优先级）
    2. db_mappings.yaml 中的 polling_config（作为 fallback）
    3. 代码中的默认值
    
    Returns:
        List[Tuple[int, int]]: [(db_number, total_size), ...]
    """
    global _db_mappings, _batch_size, _poll_interval
    
    # 使用 get_config_path 获取配置文件路径（支持打包后）
    config_path = get_config_path("configs/db_mappings.yaml")
    
    if not config_path.exists():
        print(f"⚠️  配置文件不存在: {config_path}，使用默认配置")
        # 使用 .env 中的配置
        _poll_interval = settings.plc_poll_interval
        _batch_size = settings.batch_write_size
        print(f"[轮询] 轮询间隔: {_poll_interval}秒 (from .env)")
        print(f"[轮询] 批量写入间隔: {_batch_size}次 (from .env)")
        return [(4, 144)]
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        _db_mappings = config.get('db_mappings', [])

        # ============================================================
        # 配置优先级: .env > YAML > 默认值
        # ============================================================
        polling_config = config.get('polling_config', {})
        yaml_poll_interval = polling_config.get('poll_interval', None)
        yaml_batch_size = polling_config.get('batch_write_size', None)

        # .env 的 PLC_POLL_INTERVAL 优先于 YAML
        _poll_interval = settings.plc_poll_interval
        if yaml_poll_interval is not None and yaml_poll_interval != _poll_interval:
            print(f"[配置优先级] YAML poll_interval={yaml_poll_interval}, .env PLC_POLL_INTERVAL={settings.plc_poll_interval}")
            print(f"[配置优先级] 使用 .env 值: {_poll_interval}秒")

        # .env 的 BATCH_WRITE_SIZE 优先于 YAML
        _batch_size = settings.batch_write_size
        if yaml_batch_size is not None and yaml_batch_size != _batch_size:
            print(f"[配置优先级] YAML batch_write_size={yaml_batch_size}, .env BATCH_WRITE_SIZE={settings.batch_write_size}")
            print(f"[配置优先级] 使用 .env 值: {_batch_size}次")

        print(f"[轮询] 轮询间隔: {_poll_interval}秒 (from .env, 最高优先级)")
        print(f"[轮询] 批量写入间隔: {_batch_size}次 (from .env, 最高优先级)")
        
        # 只返回启用的DB块配置
        enabled_configs = [
            (mapping['db_number'], mapping['total_size'])
            for mapping in _db_mappings
            if mapping.get('enabled', True)
        ]
        
        print(f"[轮询] 加载DB映射配置: {len(enabled_configs)}个DB块")
        for db_num, size in enabled_configs:
            mapping = next(m for m in _db_mappings if m['db_number'] == db_num)
            print(f"   - DB{db_num}: {mapping['db_name']} ({size}字节)")
        
        return enabled_configs
    
    except Exception as e:
        print(f"❌ 加载DB映射配置失败: {e}，使用默认配置")
        # 使用 .env 中的配置
        _poll_interval = settings.plc_poll_interval
        _batch_size = settings.batch_write_size
        return [(4, 144)]


# ------------------------------------------------------------
# 2. _init_parsers() - 初始化解析器（动态）
# ------------------------------------------------------------
def _init_parsers():
    """根据配置文件动态初始化解析器"""
    global _parsers, _db_mappings
    
    parser_classes = {
        'Hopper4Parser': Hopper4Parser,
        'VibDB6Parser': VibDB6Parser,
    }
    
    _parsers = {}
    
    for mapping in _db_mappings:
        if not mapping.get('enabled', True):
            continue
        
        db_number = mapping['db_number']
        parser_class_name = mapping.get('parser_class')
        
        if parser_class_name in parser_classes:
            _parsers[db_number] = parser_classes[parser_class_name]()
            print(f"   ✅ DB{db_number} -> {parser_class_name}")
        else:
            print(f"   ⚠️  未知的解析器类: {parser_class_name}")


# ============================================================
# 批量写入 & 本地缓存
# ============================================================
def _flush_buffer():
    """刷新缓存：将数据放入异步写入队列（不阻塞）"""
    global _buffer_count, _write_queue
    
    if len(_point_buffer) == 0:
        return
    
    # 转换为 Point 列表
    points = list(_point_buffer)
    _point_buffer.clear()
    _buffer_count = 0
    
    # 将数据放入异步队列，不阻塞当前线程
    if _write_queue is not None:
        try:
            _write_queue.put_nowait(points)
            print(f"[轮询] 已将 {len(points)} 个数据点加入写入队列")
        except asyncio.QueueFull:
            print(f"[轮询] 写入队列已满，数据转存到本地缓存")
            _save_to_local_cache(points)
    else:
        # 队列未初始化，使用同步写入（降级）
        _sync_write_to_influx(points)


def _sync_write_to_influx(points: List):
    """同步写入 InfluxDB（降级模式）"""
    global _stats
    
    healthy, msg = check_influx_health()
    
    if healthy:
        success, err = write_points_batch(points)
        if success:
            _stats["successful_writes"] += len(points)
            _stats["last_write_time"] = beijing_isoformat()
            print(f"[轮询] 批量写入 {len(points)} 个数据点到 InfluxDB")
        else:
            print(f"[轮询] InfluxDB 写入失败: {err}，转存到本地缓存")
            _save_to_local_cache(points)
    else:
        print(f"[轮询] InfluxDB 不可用 ({msg})，数据写入本地缓存")
        _save_to_local_cache(points)


async def _background_writer():
    """后台写入任务 - 异步处理写入队列，不阻塞轮询和推送"""
    global _stats, _write_in_progress, _write_queue
    
    print("[后台写入] 任务已启动")
    
    while _is_running:
        try:
            # 等待队列中的数据（最多等待 1 秒）
            try:
                points = await asyncio.wait_for(_write_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            if not points:
                continue
            
            _write_in_progress = True
            
            # 检查 InfluxDB 健康状态
            healthy, msg = check_influx_health()
            
            if healthy:
                # 尝试写入 InfluxDB
                success, err = write_points_batch(points)
                
                if success:
                    _stats["successful_writes"] += len(points)
                    _stats["last_write_time"] = beijing_isoformat()
                    print(f"[后台写入] 批量写入 {len(points)} 个数据点到 InfluxDB")
                else:
                    print(f"[后台写入] InfluxDB 写入失败: {err}，转存到本地缓存")
                    _save_to_local_cache(points)
            else:
                # InfluxDB 不可用，保存到本地
                print(f"[后台写入] InfluxDB 不可用 ({msg})，数据写入本地缓存")
                _save_to_local_cache(points)
            
            _write_in_progress = False
            _write_queue.task_done()
            
        except asyncio.CancelledError:
            print("[后台写入] 任务已取消")
            break
        except Exception as e:
            print(f"[后台写入] 任务异常: {e}")
            _write_in_progress = False
            await asyncio.sleep(1)
    
    print("[后台写入] 任务已停止")


def _save_to_local_cache(points: List):
    """保存数据点到本地 SQLite 缓存"""
    global _stats
    
    cache = get_local_cache()
    cached_points = []
    
    for point in points:
        # 提取 Point 对象的信息
        cached_point = CachedPoint(
            measurement=point._name,
            tags={k: v for k, v in point._tags.items()},
            fields={k: v for k, v in point._fields.items()},
            timestamp=point._time.isoformat() if point._time else beijing_isoformat()
        )
        cached_points.append(cached_point)
    
    saved_count = cache.save_points(cached_points)
    _stats["cached_points"] += saved_count
    _stats["failed_writes"] += len(points)
    
    print(f"[本地缓存] 已保存 {saved_count} 个数据点到本地缓存")


# ============================================================
# 缓存重试任务
# ============================================================
async def _retry_cached_data():
    """定期重试本地缓存的数据"""
    global _stats
    
    cache = get_local_cache()
    retry_interval = 60  # 每 60 秒重试一次
    
    while _is_running:
        await asyncio.sleep(retry_interval)
        
        # 检查 InfluxDB 健康状态
        healthy, _ = check_influx_health()
        if not healthy:
            continue
        
        # 获取待重试数据
        pending = cache.get_pending_points(limit=100, max_retry=5)
        
        if not pending:
            continue
        
        print(f"[缓存重试] 开始重试 {len(pending)} 条缓存数据...")
        
        # 重新构建 Point 对象
        points = []
        ids = []
        
        for point_id, cached_point in pending:
            try:
                point = build_point(
                    cached_point.measurement,
                    cached_point.tags,
                    cached_point.fields,
                    datetime.fromisoformat(cached_point.timestamp)
                )
                if point:
                    points.append(point)
                    ids.append(point_id)
            except Exception as e:
                print(f"[缓存重试] 重建 Point 失败: {e}")
        
        if not points:
            continue
        
        # 批量写入
        success, err = write_points_batch(points)
        
        if success:
            cache.mark_success(ids)
            _stats["retry_success"] += len(points)
            _stats["last_retry_time"] = beijing_isoformat()
            print(f"[缓存重试] 重试成功: {len(points)} 条数据已写入 InfluxDB")
        else:
            cache.mark_retry(ids)
            print(f"[缓存重试] 重试失败: {err}")


# ============================================================
# 定期清理任务（每小时执行）
# ============================================================
async def _periodic_cleanup():
    """定期清理过期缓存和执行内存维护"""
    cleanup_interval = 3600  # 每小时清理一次
    
    while _is_running:
        await asyncio.sleep(cleanup_interval)
        
        try:
            # 清理本地缓存中超过7天的失败记录
            cache = get_local_cache()
            cache.cleanup_old(days=7)
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            print(f"[定期清理] 清理完成 | 设备缓存: {len(_latest_data)}")
        except Exception as e:
            print(f"[定期清理] 任务异常: {e}")


# ============================================================
# 主轮询循环
# ============================================================
async def _poll_data():
    """轮询DB块数据并写入InfluxDB（动态配置）
    
    支持两种模式:
    - 正常模式: 从真实PLC读取数据
    - Mock模式: 使用MockService生成模拟数据
    """
    global _buffer_count, _stats, _latest_data, _latest_timestamp
    
    # 从配置文件加载DB块配置
    db_configs = _load_db_mappings()
    
    poll_count = 0
    
    # 根据模式初始化数据源
    if settings.mock_mode:
        # Mock模式：使用模拟数据生成器
        from app.services.mock_service import MockService
        print("[轮询] Mock模式已启用 - 使用模拟数据")
        plc = None
    else:
        # 正常模式：使用真实PLC
        plc = get_plc_manager()
    
    while _is_running:
        poll_count += 1
        timestamp = now_beijing()
        _stats["total_polls"] += 1
        
        try:
            # ============================================================
            # Step 1: 读取所有 DB 块数据
            # ============================================================
            all_devices = []
            
            if settings.mock_mode:
                # Mock模式：生成模拟数据 (PLC原始格式)
                mock_data = MockService.generate_hopper_data()
                
                # 与真实PLC相同的处理流程: converter转换 -> 更新缓存
                for device_id, device_data in mock_data.items():
                    all_devices.append(device_data)
                    _update_latest_data(device_data, 4, timestamp)
                
                _latest_timestamp = timestamp
                # 通知 WS 推送新数据已就绪
                get_data_updated_event().set()
            else:
                # 正常模式：从PLC读取数据
                for db_num, size in db_configs:
                    # 使用长连接读取
                    success, db_data, err = plc.read_db(db_num, 0, size)
                    
                    if not success:
                        print(f"[轮询] DB{db_num} 读取失败: {err}")
                        continue
                    
                    # 解析设备数据
                    if db_num in _parsers:
                        devices = _parsers[db_num].parse_all(db_data)
                        all_devices.extend(devices)
                        
                        # 更新内存缓存
                        for device in devices:
                            _update_latest_data(device, db_num, timestamp)
                
                # 更新时间戳
                _latest_timestamp = timestamp
                # 通知 WS 推送新数据已就绪
                get_data_updated_event().set()
            
            # ============================================================
            # Step 2: 将数据加入写入缓冲区
            # ============================================================
            written_count = 0
            for device in all_devices:
                db_num = device.get('db_number', 4) if isinstance(device, dict) else 4
                count = _add_device_to_buffer(device, db_num, timestamp)
                written_count += count
            
            # 检查是否需要批量写入
            _buffer_count += 1
            
            # 缓冲区告警阈值
            buffer_usage = len(_point_buffer) / 1000
            if buffer_usage > 0.5:
                print(f"[轮询] 缓冲区使用率过高: {buffer_usage*100:.1f}% (将触发批量写入)")
            
            # 触发批量写入：达到批次数或缓冲区>500个点
            if _buffer_count >= _batch_size or len(_point_buffer) >= 500:
                _flush_buffer()
            
            # 日志输出
            if settings.verbose_polling_log or poll_count % 10 == 0:
                cache_stats = get_local_cache().get_stats()
                print(f"[轮询 #{poll_count}] "
                      f"设备: {len(all_devices)} | "
                      f"数据点: {written_count} | "
                      f"缓冲区={len(_point_buffer)}/{_batch_size} | "
                      f"待重试={cache_stats['pending_count']}")
        
        except Exception as e:
            print(f"[轮询 #{poll_count}] 轮询异常: {e}")
            import traceback
            traceback.print_exc()
        
        # 使用配置的轮询间隔
        await asyncio.sleep(_poll_interval)


# ============================================================
# 更新内存缓存（供 WebSocket 推送和 API 读取）
# ============================================================
def _update_latest_data(device_data: Dict[str, Any], db_number: int, timestamp: datetime):
    """更新内存缓存中的最新数据
    
    Args:
        device_data: 解析后的设备数据
        db_number: DB块号
        timestamp: 时间戳
    """
    global _latest_data
    
    device_id = device_data['device_id']
    device_type = device_data['device_type']
    device_name = device_data.get('device_name', device_id)
    
    # 转换所有模块数据
    modules_data = {}
    
    for module_tag, module_data in device_data['modules'].items():
        module_type = module_data['module_type']
        raw_fields = module_data['fields']
        
        # 使用转换器转换数据
        if module_type in CONVERTER_MAP:
            converter = get_converter(module_type)
            fields = converter.convert(raw_fields)
        else:
            # 未知模块类型，直接提取原始值
            fields = {}
            for field_name, field_info in raw_fields.items():
                fields[field_name] = field_info['value']
        
        modules_data[module_tag] = {
            "module_type": module_type,
            "fields": fields
        }
    
    # 更新内存缓存
    with _data_lock:
        _latest_data[device_id] = {
            "device_id": device_id,
            "device_name": device_name,
            "device_type": device_type,
            "timestamp": timestamp.isoformat(),
            "modules": modules_data
        }


# ============================================================
# 将设备数据加入写入缓冲区
# ============================================================
def _add_device_to_buffer(device_data: Dict[str, Any], db_number: int, timestamp: datetime) -> int:
    """将设备数据加入写入缓冲区
    
    Args:
        device_data: 解析后的设备数据
        db_number: DB块号
        timestamp: 时间戳
    
    Returns:
        添加的数据点数量
    """
    device_id = device_data['device_id']
    device_type = device_data['device_type']
    point_count = 0
    
    # 遍历所有模块
    for module_tag, module_data in device_data['modules'].items():
        module_type = module_data['module_type']
        raw_fields = module_data['fields']
        
        # 使用转换器转换数据
        if module_type in CONVERTER_MAP:
            converter = get_converter(module_type)
            fields = converter.convert(raw_fields)
        else:
            # 未知模块类型，直接提取原始值
            fields = {}
            for field_name, field_info in raw_fields.items():
                fields[field_name] = field_info['value']
        
        # 跳过空字段
        if not fields:
            continue
        
        # 构建 Point 对象
        point = build_point(
            measurement="sensor_data",
            tags={
                "device_id": device_id,
                "device_type": device_type,
                "module_type": module_type,
                "module_tag": module_tag,
                "db_number": str(db_number)
            },
            fields=fields,
            timestamp=timestamp
        )
        
        if point:
            _point_buffer.append(point)
            point_count += 1
    
    return point_count


# ------------------------------------------------------------
# 启动数据轮询任务
# ------------------------------------------------------------
async def start_polling():
    """启动数据轮询任务（从配置文件动态加载）"""
    global _polling_task, _retry_task, _cleanup_task, _write_task, _is_running, _batch_size, _poll_interval, _write_queue
    
    if _is_running:
        print("[轮询] 轮询服务已在运行")
        return
    
    # 加载DB映射配置
    _load_db_mappings()
    
    # 动态初始化解析器
    print("[轮询] 初始化解析器:")
    _init_parsers()
    
    _is_running = True
    
    # 初始化异步写入队列（最多缓存 10 批数据）
    _write_queue = asyncio.Queue(maxsize=10)
    
    # 根据模式启动
    if settings.mock_mode:
        print("[轮询] Mock模式 - 跳过PLC连接")
    else:
        # 启动 PLC 长连接
        plc = get_plc_manager()
        success, err = plc.connect()
        if success:
            print("[轮询] PLC 长连接已建立")
        else:
            print(f"[轮询] PLC 连接失败: {err}，将在轮询时重试")
    
    # 启动后台写入任务（关键：不阻塞轮询和推送）
    _write_task = asyncio.create_task(_background_writer())
    
    # 启动轮询任务
    _polling_task = asyncio.create_task(_poll_data())
    _retry_task = asyncio.create_task(_retry_cached_data())
    _cleanup_task = asyncio.create_task(_periodic_cleanup())
    
    mode_str = "Mock模式" if settings.mock_mode else "正常模式"
    print(f"[轮询] 轮询服务已启动 ({mode_str}, 间隔: {_poll_interval}s, 批量: {_batch_size}次)")
    print("[轮询] 后台写入模式已启用 - 不会阻塞推送")


# ------------------------------------------------------------
# 停止数据轮询任务
# ------------------------------------------------------------
async def stop_polling():
    """停止数据轮询任务"""
    global _polling_task, _retry_task, _cleanup_task, _write_task, _is_running, _write_queue
    
    _is_running = False
    
    # 刷新缓冲区（将剩余数据放入队列）
    print("[轮询] 正在刷新缓冲区...")
    _flush_buffer()
    
    # 等待写入队列处理完成（最多等待 10 秒）
    if _write_queue is not None:
        try:
            await asyncio.wait_for(_write_queue.join(), timeout=10.0)
            print("[轮询] 写入队列已清空")
        except asyncio.TimeoutError:
            print("[轮询] 写入队列清空超时，部分数据可能丢失")
    
    # 取消所有任务，添加超时保护
    tasks_to_cancel = [
        ("polling", _polling_task), 
        ("retry", _retry_task), 
        ("cleanup", _cleanup_task),
        ("writer", _write_task)
    ]
    
    for task_name, task in tasks_to_cancel:
        if task:
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                print(f"[轮询] {task_name} 任务取消超时，强制终止")
    
    _polling_task = None
    _retry_task = None
    _cleanup_task = None
    _write_task = None
    _write_queue = None
    
    # 断开 PLC 长连接
    if not settings.mock_mode:
        plc = get_plc_manager()
        plc.disconnect()
    
    print("[轮询] 轮询服务已停止")


# ============================================================
# API 查询函数（供 Router 使用）
# ============================================================
def get_latest_data() -> Dict[str, Any]:
    """获取所有设备的最新数据（从内存缓存）
    
    Returns:
        {device_id: {device_id, device_type, timestamp, modules: {...}}}
    """
    with _data_lock:
        return _latest_data.copy()


def get_latest_device_data(device_id: str) -> Optional[Dict[str, Any]]:
    """获取单个设备的最新数据（从内存缓存）
    
    Args:
        device_id: 设备ID
    
    Returns:
        设备数据或 None
    """
    with _data_lock:
        return _latest_data.get(device_id)


def get_latest_devices_by_type(device_type: str) -> List[Dict[str, Any]]:
    """获取指定类型的所有设备最新数据
    
    Args:
        device_type: 设备类型 (hopper_sensor_unit, etc.)
    
    Returns:
        设备数据列表
    """
    with _data_lock:
        return [
            data for data in _latest_data.values()
            if data.get('device_type') == device_type
        ]


def get_latest_timestamp() -> Optional[str]:
    """获取最新数据的时间戳"""
    return _latest_timestamp.isoformat() if _latest_timestamp else None


def is_polling_running() -> bool:
    """检查轮询服务是否在运行"""
    return _is_running


def get_polling_stats() -> Dict[str, Any]:
    """获取轮询统计信息"""
    cache_stats = get_local_cache().get_stats()
    
    plc_status = {"connected": False, "mode": "mock"}
    if not settings.mock_mode:
        plc_status = get_plc_manager().get_status()
    
    return {
        **_stats,
        "buffer_size": len(_point_buffer),
        "batch_size": _batch_size,
        "devices_in_cache": len(_latest_data),
        "latest_timestamp": get_latest_timestamp(),
        "cache_stats": cache_stats,
        "plc_status": plc_status
    }
