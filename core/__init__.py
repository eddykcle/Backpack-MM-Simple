"""
核心模块
包含日志管理、守护进程管理等核心功能
"""
from .logger import setup_logger
from .log_manager import StructuredLogger, ProcessManager, get_logger
from .daemon_manager import TradingBotDaemon

__all__ = [
    'setup_logger',
    'StructuredLogger',
    'ProcessManager',
    'get_logger',
    'TradingBotDaemon',
]

