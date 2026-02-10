"""
FastAPI 应用入口 - 料仓监控系统

功能:
    1. 创建FastAPI应用实例
    2. 应用生命周期管理
    3. 启动轮询服务
    4. 启动 WebSocket 推送任务
"""

from contextlib import asynccontextmanager
import logging
import logging.handlers
import sys
import io
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, config, hopper_4, alarms, websocket
from app.services.polling_service import start_polling, stop_polling
from app.services.ws_manager import get_ws_manager
from config import get_settings

# 0. 设置控制台输出编码为 UTF-8（解决 Windows 乱码问题）
if sys.platform == 'win32':
    try:
        # 设置标准输出和错误输出为 UTF-8
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # 如果设置失败，继续运行

# 1. 配置日志系统（支持日志轮转和自动清理）
def setup_logging():
    import datetime
    
    # 创建 logs 目录
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # 日志文件路径（直接使用日期命名）
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"app.log.{today}"
    
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除已有的处理器
    root_logger.handlers.clear()
    
    # 1. 控制台处理器（只显示 WARNING 及以上级别）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 2. 文件处理器（按天轮转，保留 30 天）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file),
        when='midnight',        # 每天午夜轮转
        interval=1,             # 每 1 天
        backupCount=30,         # 保留 30 个备份文件
        encoding='utf-8',
        delay=False
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    
    # 设置日志文件名后缀格式（例如：app.log.2026-02-09.2026-02-10）
    file_handler.suffix = "%Y-%m-%d"
    
    root_logger.addHandler(file_handler)
    
    # 3. 限制日志总大小（定期清理超过 50GB 的旧日志）
    import threading
    import time
    
    def cleanup_old_logs():
        """定期清理超过 30 天或超过 50GB 的旧日志文件"""
        while True:
            try:
                time.sleep(3600)  # 每小时检查一次
                
                # 获取所有日志文件（按修改时间排序）
                log_files = sorted(log_dir.glob("app.log.*"), key=lambda p: p.stat().st_mtime)
                
                # 1. 删除超过 30 天的日志
                now = datetime.datetime.now()
                for log_file in log_files[:]:
                    file_age_days = (now - datetime.datetime.fromtimestamp(log_file.stat().st_mtime)).days
                    if file_age_days > 30:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        log_files.remove(log_file)
                        logging.info(f"[日志清理] 删除过期日志: {log_file.name} (已保存 {file_age_days} 天)")
                
                # 2. 如果总大小超过 50GB，删除最旧的文件
                total_size = sum(f.stat().st_size for f in log_files)
                max_size = 50 * 1024 * 1024 * 1024  # 50GB
                
                while total_size > max_size and len(log_files) > 1:
                    oldest_file = log_files.pop(0)
                    file_size = oldest_file.stat().st_size
                    oldest_file.unlink()
                    total_size -= file_size
                    logging.info(f"[日志清理] 删除旧日志（超过大小限制）: {oldest_file.name} ({file_size / 1024 / 1024:.2f} MB)")
            except Exception as e:
                logging.error(f"[日志清理] 清理失败: {e}")
    
    # 启动后台清理线程
    cleanup_thread = threading.Thread(target=cleanup_old_logs, daemon=True)
    cleanup_thread.start()
    
    logging.info(f"[日志系统] 日志目录: {log_dir}")
    logging.info(f"[日志系统] 当前日志文件: {log_file.name}")
    logging.info(f"[日志系统] 日志轮转: 每天午夜自动创建新文件")
    logging.info(f"[日志系统] 保留策略: 最近 30 天，总大小不超过 50GB")

# 初始化日志系统
setup_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


# ------------------------------------------------------------
# 应用生命周期管理
# ------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时
    logger.info("Starting hopper backend...")
    
    # 1. 加载配置文件
    logger.info("[启动] 初始化配置...")
    logger.info("[启动] 配置加载完成")
    
    # 2. 自动迁移 InfluxDB Schema
    logger.info("\n[启动] 检查 InfluxDB Schema...")
    from app.core.influx_migration import auto_migrate_on_startup
    if auto_migrate_on_startup():
        logger.info("[启动] InfluxDB Schema 迁移完成\n")
    else:
        logger.info("[启动] InfluxDB 迁移失败，但服务继续启动\n")
    
    # 3. 启动轮询服务 (根据环境变量决定是否启用)
    if settings.enable_polling:
        await start_polling()
        logger.info("[启动] 轮询服务已启动")
    else:
        logger.info("[启动] 轮询服务已禁用 (ENABLE_POLLING=false)")
    
    # 4. 启动 WebSocket 推送任务
    ws_manager = get_ws_manager()
    await ws_manager.start_push_tasks()
    logger.info("[启动] WebSocket 推送任务已启动")
    
    yield
    
    # 关闭时
    logger.info("[关闭] 应用关闭中...")
    
    # 1. 停止 WebSocket 推送任务
    await ws_manager.stop_push_tasks()
    logger.info("[关闭] WebSocket 推送任务已停止")
    
    # 2. 停止轮询服务
    if settings.enable_polling:
        await stop_polling()
    
    # 3. 关闭 InfluxDB 客户端
    from app.core.influxdb import close_influx_client
    close_influx_client()
    
    # 4. 关闭本地缓存数据库连接
    from app.core.local_cache import get_local_cache
    get_local_cache().close()
    
    logger.info("[关闭] 所有资源已释放")


# ------------------------------------------------------------
# 创建FastAPI应用实例
# ------------------------------------------------------------
def create_app() -> FastAPI:
    """创建并配置FastAPI应用"""
    app = FastAPI(
        title="Ceramic Hopper Backend",
        description="陶瓷料仓监控系统后端API",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS 配置 - 允许前端访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 局域网部署，允许所有来源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(health.router)
    app.include_router(hopper_4.router)
    app.include_router(alarms.router, prefix="/api/alarms", tags=["报警管理"])
    app.include_router(config.router, prefix="/api/config", tags=["系统配置"])
    app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
    
    return app


app = create_app()


if __name__ == "__main__":
    # Launch desktop tray + log viewer when running as a script
    from scripts.tray_app import run_tray_app

    run_tray_app()
