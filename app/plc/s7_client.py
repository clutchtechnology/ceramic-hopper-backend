# ============================================================
# 文件说明: s7_client.py - Siemens S7-1200 PLC 通信客户端（长连接版本）
# ============================================================
# 方法列表:
# 1. connect()              - 连接到PLC（保持长连接）
# 2. disconnect()           - 断开PLC连接
# 3. read_db_block()        - 读取整个DB块数据（自动重连）
# 4. is_connected()         - 检查连接状态
# 5. reconnect()            - 手动重连
# ============================================================

import snap7
from snap7.util import get_real, get_int, get_dint, get_bool
from typing import Optional, Tuple
from config import get_settings
import time


# ------------------------------------------------------------
# S7Client - S7 PLC 客户端（长连接）
# ------------------------------------------------------------
class S7Client:
    """Siemens S7-1200 PLC 客户端（长连接版本）"""
    
    def __init__(self, ip: str, rack: int = 0, slot: int = 1, timeout_ms: int = 5000):
        """
        初始化S7客户端
        
        Args:
            ip: PLC IP地址
            rack: 机架号 (S7-1200固定为0)
            slot: 插槽号 (S7-1200固定为1)
            timeout_ms: 超时时间 (毫秒)
        """
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self.timeout_ms = timeout_ms
        self.client: Optional[snap7.client.Client] = None
        self._connected: bool = False
        
        # 重试配置（优化：减少重试频率）
        self._max_retry_attempts: int = 2  # 最大重试次数
        self._retry_delay: float = 2.0  # 重试延迟（秒）
    
    # ------------------------------------------------------------
    # 1. connect() - 连接到PLC（保持长连接）
    # ------------------------------------------------------------
    def connect(self) -> bool:
        """
        连接到PLC（保持长连接，不主动断开）
        
        Returns:
            bool: 连接成功返回True
        
        Raises:
            ConnectionError: 连接失败时抛出
        """
        # 如果已连接，检查连接是否有效
        if self._connected and self.client:
            try:
                if self.client.get_connected():
                    return True
            except Exception:
                self._connected = False
        
        try:
            if self.client is None:
                self.client = snap7.client.Client()
            
            # 连接到PLC
            self.client.connect(self.ip, self.rack, self.slot)
            
            if not self.client.get_connected():
                raise ConnectionError(f"无法连接到PLC {self.ip}")
            
            self._connected = True
            print(f"✅ PLC 长连接已建立: {self.ip}")
            return True
            
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"PLC连接失败: {e}")
    
    # ------------------------------------------------------------
    # 2. disconnect() - 断开PLC连接
    # ------------------------------------------------------------
    def disconnect(self) -> None:
        """断开PLC连接"""
        if self.client and self._connected:
            try:
                if self.client.get_connected():
                    self.client.disconnect()
                    print(f"🔌 PLC 连接已断开: {self.ip}")
            except Exception:
                pass
        self._connected = False
    
    # ------------------------------------------------------------
    # 3. read_db_block() - 读取整个DB块数据（自动重连）
    # ------------------------------------------------------------
    def read_db_block(self, db_number: int, start: int, size: int) -> bytes:
        """
        读取整个DB块数据（带自动重连机制）
        
        Args:
            db_number: DB块编号
            start: 起始字节地址
            size: 读取字节数
        
        Returns:
            bytes: 读取的字节数据
        
        Raises:
            ConnectionError: PLC未连接
            Exception: 读取失败
        """
        # 尝试读取（带重试）
        for attempt in range(self._max_retry_attempts):
            try:
                # 确保连接
                if not self._connected or not self.client or not self.client.get_connected():
                    self.connect()
                
                # 读取数据
                data = self.client.db_read(db_number, start, size)
                return data
                
            except Exception as e:
                # 最后一次尝试失败，抛出异常
                if attempt >= self._max_retry_attempts - 1:
                    raise Exception(f"读取DB{db_number}失败（已重试{self._max_retry_attempts}次）: {e}")
                
                # 重试前断开连接，等待后重连
                print(f"⚠️ DB{db_number} 读取失败（尝试 {attempt+1}/{self._max_retry_attempts}）: {e}")
                self._connected = False
                time.sleep(self._retry_delay)
    
    # ------------------------------------------------------------
    # 4. is_connected() - 检查连接状态
    # ------------------------------------------------------------
    def is_connected(self) -> bool:
        """检查PLC是否已连接"""
        if not self._connected or not self.client:
            return False
        try:
            return self.client.get_connected()
        except Exception:
            self._connected = False
            return False
    
    # ------------------------------------------------------------
    # 5. reconnect() - 手动重连
    # ------------------------------------------------------------
    def reconnect(self) -> bool:
        """
        手动重连PLC
        
        Returns:
            bool: 重连成功返回True
        """
        self.disconnect()
        time.sleep(1.0)
        try:
            return self.connect()
        except Exception:
            return False

# ------------------------------------------------------------
# 全局客户端实例（单例模式，保持长连接）
# ------------------------------------------------------------
import threading

_s7_client: Optional[S7Client] = None
_s7_client_lock = threading.Lock()


def get_s7_client() -> S7Client:
    """获取S7客户端单例（线程安全，自动建立长连接）"""
    global _s7_client
    if _s7_client is None:
        with _s7_client_lock:
            if _s7_client is None:
                settings = get_settings()
                _s7_client = S7Client(
                    ip=settings.plc_ip,
                    rack=settings.plc_rack,
                    slot=settings.plc_slot,
                    timeout_ms=settings.plc_timeout
                )
                # 自动建立长连接
                try:
                    _s7_client.connect()
                except Exception as e:
                    print(f"⚠️ 初始化 PLC 连接失败: {e}")
    return _s7_client


def reset_s7_client() -> None:
    """重置S7客户端（用于配置更新后重新连接）"""
    global _s7_client
    if _s7_client is not None:
        try:
            _s7_client.disconnect()
        except:
            pass
        _s7_client = None


def update_s7_client(ip: str = None, rack: int = None, slot: int = None, timeout_ms: int = None) -> S7Client:
    """更新S7客户端配置并重新创建实例（会断开旧连接，建立新连接）
    
    Args:
        ip: 新的 PLC IP 地址
        rack: 新的机架号
        slot: 新的插槽号
        timeout_ms: 新的超时时间
        
    Returns:
        S7Client: 新的客户端实例
    """
    global _s7_client
    
    # 断开旧连接
    if _s7_client is not None:
        try:
            _s7_client.disconnect()
        except:
            pass
    
    # 获取当前配置作为默认值
    settings = get_settings()
    
    # 创建新实例
    _s7_client = S7Client(
        ip=ip if ip is not None else settings.plc_ip,
        rack=rack if rack is not None else settings.plc_rack,
        slot=slot if slot is not None else settings.plc_slot,
        timeout_ms=timeout_ms if timeout_ms is not None else settings.plc_timeout
    )
    
    # 建立长连接
    try:
        _s7_client.connect()
    except Exception as e:
        print(f"⚠️ 更新 PLC 连接失败: {e}")
    
    return _s7_client

