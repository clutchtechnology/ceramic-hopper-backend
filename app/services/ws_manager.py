"""
WebSocket 连接管理器 - 料仓监控系统

功能:
    1. 管理所有 WebSocket 连接
    2. 订阅/取消订阅频道
    3. 广播消息给订阅者
    4. 后台推送任务 (realtime_data)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

HEARTBEAT_TIMEOUT = 45  # 心跳超时时间
# 事件等待超时 (超过此时间无新数据则继续循环检查)
_EVENT_WAIT_TIMEOUT = 5.0


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # websocket -> 订阅的频道集合
        self.active_connections: Dict[WebSocket, Set[str]] = {}
        # websocket -> 最后心跳时间
        self.last_heartbeat: Dict[WebSocket, datetime] = {}
        # 推送任务
        self._push_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
        # 推送计数器 (每50次输出一次摘要日志)
        self._push_count = 0
        self._push_log_interval = 50

    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections[websocket] = set()
        self.last_heartbeat[websocket] = datetime.now(timezone.utc)
        client_host = websocket.client.host if websocket.client else "unknown"
        logger.info(f"[WS] 新连接建立 (来自 {client_host})，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """移除 WebSocket 连接"""
        channels = self.active_connections.get(websocket, set())
        if websocket in self.active_connections:
            del self.active_connections[websocket]
        if websocket in self.last_heartbeat:
            del self.last_heartbeat[websocket]
        logger.info(f"[WS] 连接断开 (订阅频道: {channels or '无'})，剩余连接数: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, channel: str) -> bool:
        """订阅频道"""
        valid_channels = {"realtime"}
        if channel not in valid_channels:
            logger.warning(f"[WS] 无效的订阅频道: {channel}")
            return False
        if websocket in self.active_connections:
            self.active_connections[websocket].add(channel)
            logger.info(f"[WS] 客户端订阅频道: {channel}, 当前该频道订阅数: {self.get_channel_subscribers(channel)}")
            return True
        return False

    def unsubscribe(self, websocket: WebSocket, channel: str):
        """取消订阅频道"""
        if websocket in self.active_connections:
            self.active_connections[websocket].discard(channel)
            logger.info(f"[WS] 客户端取消订阅: {channel}")

    def update_heartbeat(self, websocket: WebSocket):
        """更新心跳时间"""
        self.last_heartbeat[websocket] = datetime.now(timezone.utc)
        logger.debug(f"[WS] 收到心跳，连接数: {len(self.active_connections)}")

    async def broadcast(self, channel: str, message: dict):
        """向指定频道的所有订阅者广播消息"""
        disconnected = []
        for ws, channels in self.active_connections.items():
            if channel in channels:
                try:
                    if ws.application_state != WebSocketState.CONNECTED or ws.client_state != WebSocketState.CONNECTED:
                        disconnected.append(ws)
                        continue
                    await ws.send_json(message)
                except WebSocketDisconnect:
                    disconnected.append(ws)
                except Exception as e:
                    logger.warning(f"[WS] 发送消息失败: {e}")
                    disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            self.disconnect(ws)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """发送消息给单个客户端"""
        try:
            if websocket.application_state != WebSocketState.CONNECTED or websocket.client_state != WebSocketState.CONNECTED:
                self.disconnect(websocket)
                return
            await websocket.send_json(message)
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except Exception as e:
            logger.warning(f"[WS] 发送消息失败: {e}")
            self.disconnect(websocket)

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.active_connections)

    def get_channel_subscribers(self, channel: str) -> int:
        """获取指定频道的订阅者数量"""
        count = 0
        for channels in self.active_connections.values():
            if channel in channels:
                count += 1
        return count

    # ========================================
    # 后台推送任务
    # ========================================
    async def start_push_tasks(self):
        """启动后台推送任务"""
        if self._is_running:
            return

        self._is_running = True
        self._push_task = asyncio.create_task(self._push_loop(), name="ws_push_loop")
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(), name="ws_cleanup_loop")
        logger.info(f"[WS] 推送任务已启动 (事件驱动, 心跳超时: {HEARTBEAT_TIMEOUT}s)")

    async def stop_push_tasks(self):
        """停止后台推送任务"""
        self._is_running = False

        for task in [self._push_task, self._cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._push_task = None
        self._cleanup_task = None
        logger.info("[WS] 推送任务已停止")

    async def _push_loop(self):
        """数据推送主循环 (事件驱动: 等待轮询服务通知新数据)"""
        from app.services.polling_service import get_data_updated_event
        event = get_data_updated_event()

        while self._is_running:
            try:
                # 等待轮询服务通知有新数据
                await asyncio.wait_for(event.wait(), timeout=_EVENT_WAIT_TIMEOUT)
                event.clear()

                # 检查是否有订阅者
                realtime_subs = self.get_channel_subscribers("realtime")
                if realtime_subs > 0:
                    timestamp = datetime.now(timezone.utc).isoformat()
                    await self._push_realtime_data(timestamp)

            except asyncio.TimeoutError:
                # 超时无新数据，继续循环 (正常情况: 轮询服务未启动或暂停)
                continue
            except Exception as e:
                logger.error(f"[WS] 推送任务异常: {e}", exc_info=True)
                await asyncio.sleep(1)  # 异常时短暂等待防止busy loop

    async def _push_realtime_data(self, timestamp: str):
        """推送实时数据 (realtime_data)"""
        from app.services.polling_service import get_latest_data
        
        # 从轮询服务的内存缓存获取最新数据
        latest = get_latest_data()
        
        # 如果缓存为空，返回空数据
        if not latest:
            logger.warning("[WS] 轮询服务缓存为空，无法推送数据")
            return
        
        source = "mock" if settings.mock_mode else "plc"

        message = {
            "type": "realtime_data",
            "success": True,
            "timestamp": timestamp,
            "source": source,
            "data": latest,
        }

        subs = self.get_channel_subscribers("realtime")
        await self.broadcast("realtime", message)

        # 推送计数日志 (每 _push_log_interval 次输出一次摘要)
        self._push_count += 1
        if self._push_count % self._push_log_interval == 0:
            device_ids = list(latest.keys()) if isinstance(latest, dict) else []
            module_keys = []
            for dev_data in (latest.values() if isinstance(latest, dict) else []):
                if isinstance(dev_data, dict) and "modules" in dev_data:
                    module_keys = list(dev_data["modules"].keys())
                    break
            logger.info(
                f"[WS] 推送统计: 第{self._push_count}次, "
                f"订阅者={subs}, 设备={device_ids}, "
                f"模块={module_keys}, source={source}"
            )

    async def _cleanup_loop(self):
        """清理超时连接的循环"""
        while self._is_running:
            await asyncio.sleep(10)  # 每 10 秒检查一次

            now = datetime.now(timezone.utc)
            disconnected = []

            for ws, last_hb in self.last_heartbeat.items():
                delta = (now - last_hb).total_seconds()
                if delta > HEARTBEAT_TIMEOUT:
                    logger.warning(f"[WS] 客户端心跳超时 ({delta:.0f}s)，断开连接")
                    disconnected.append(ws)

            for ws in disconnected:
                try:
                    await ws.close(code=1000, reason="Heartbeat timeout")
                except Exception:
                    pass
                self.disconnect(ws)
            
            # 清理已断开但未正确移除的连接
            stale_connections = []
            for ws in self.active_connections.keys():
                if ws.application_state != WebSocketState.CONNECTED or ws.client_state != WebSocketState.CONNECTED:
                    stale_connections.append(ws)
            
            for ws in stale_connections:
                logger.warning("[WS] 清理僵尸连接")
                self.disconnect(ws)


# 全局单例
_manager: Optional[ConnectionManager] = None


def get_ws_manager() -> ConnectionManager:
    """获取 WebSocket 连接管理器单例"""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager

