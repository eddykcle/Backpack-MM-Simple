"""
高級日誌管理系統
替代 nohup.out，提供結構化日誌、輪轉和壓縮功能
"""
import logging
import logging.handlers
import os
import sys
import json
import gzip
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import threading
import queue
import time

class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """支持壓縮的日誌輪轉處理器"""
    
    def doRollover(self):
        """執行日誌輪轉並壓縮舊文件"""
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # 重命名當前日誌文件
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = f"{self.baseFilename}.{i}.gz"
                dfn = f"{self.baseFilename}.{i + 1}.gz"
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            
            # 壓縮最新的備份文件
            dfn = f"{self.baseFilename}.1.gz"
            if os.path.exists(dfn):
                os.remove(dfn)
            
            # 壓縮當前日誌文件
            with open(self.baseFilename, 'rb') as f_in:
                with gzip.open(dfn, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # 刪除原始文件
            os.remove(self.baseFilename)
        
        # 重新打開日誌文件
        self.mode = 'w'
        self.stream = self._open()

class AsyncLogHandler(logging.Handler):
    """異步日誌處理器，避免阻塞主線程"""
    
    def __init__(self, filename: str, max_bytes: int = 10*1024*1024, backup_count: int = 5):
        super().__init__()
        self.filename = filename
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.log_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        self._start_worker()
    
    def _start_worker(self):
        """啟動異步寫入線程"""
        self.running = True
        self.worker_thread = threading.Thread(target=self._write_worker, daemon=True)
        self.worker_thread.start()
    
    def _write_worker(self):
        """異步寫入工作線程"""
        # 創建文件處理器
        file_handler = CompressedRotatingFileHandler(
            self.filename,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        while self.running or not self.log_queue.empty():
            try:
                # 等待日誌記錄，超時1秒
                record = self.log_queue.get(timeout=1)
                file_handler.emit(record)
            except queue.Empty:
                continue
            except Exception as e:
                # 如果出錯，記錄到stderr
                print(f"異步日誌寫入錯誤: {e}", file=sys.stderr)
    
    def emit(self, record):
        """發送日誌記錄到隊列"""
        try:
            self.log_queue.put(record)
        except Exception:
            self.handleError(record)
    
    def close(self):
        """關閉異步處理器"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        super().close()

class StructuredLogger:
    """結構化日誌記錄器"""
    
    def __init__(self, name: str, log_dir: str = "logs", max_bytes: int = 50*1024*1024, backup_count: int = 10):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 創建logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 清除現有的處理器
        self.logger.handlers.clear()
        
        # 創建不同類型的日誌處理器
        self._setup_handlers(max_bytes, backup_count)
    
    def _setup_handlers(self, max_bytes: int, backup_count: int):
        """設置各種日誌處理器"""
        
        # 1. 主要日誌文件（所有級別）
        main_handler = CompressedRotatingFileHandler(
            self.log_dir / f"{self.name}.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        main_handler.setLevel(logging.DEBUG)
        main_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        main_handler.setFormatter(main_formatter)
        self.logger.addHandler(main_handler)
        
        # 2. 錯誤日誌文件（只包含ERROR及以上）
        error_handler = CompressedRotatingFileHandler(
            self.log_dir / f"{self.name}_errors.log",
            maxBytes=max_bytes // 2,
            backupCount=backup_count
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
        
        # 3. 結構化JSON日誌（便於程序解析）
        json_handler = CompressedRotatingFileHandler(
            self.log_dir / f"{self.name}_structured.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        json_handler.setLevel(logging.INFO)
        json_formatter = logging.Formatter('%(message)s')  # 純JSON格式
        json_handler.setFormatter(json_formatter)
        
        # 包裝emit方法以輸出JSON
        original_emit = json_handler.emit
        def json_emit(record):
            try:
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                
                # 如果有額外數據，也包含進去
                if hasattr(record, 'extra_data'):
                    log_entry['data'] = record.extra_data
                
                record.msg = json.dumps(log_entry, ensure_ascii=False)
                record.args = ()  # 清除args避免重複格式化
                original_emit(record)
            except Exception as e:
                print(f"JSON日誌格式化錯誤: {e}", file=sys.stderr)
        
        json_handler.emit = json_emit
        self.logger.addHandler(json_handler)
        
        # 4. 控制台輸出（可選）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def log_structured(self, level: str, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """記錄結構化日誌"""
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        
        if extra_data:
            # 創建一個特殊的記錄對象
            record = self.logger.makeRecord(
                self.name,
                getattr(logging, level.upper(), logging.INFO),
                '', 0, message, (), None
            )
            record.extra_data = extra_data
            self.logger.handle(record)
        else:
            log_method(message)
    
    def info(self, message: str, **kwargs):
        self.log_structured('INFO', message, kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log_structured('WARNING', message, kwargs)
    
    def error(self, message: str, **kwargs):
        self.log_structured('ERROR', message, kwargs)
    
    def debug(self, message: str, **kwargs):
        self.log_structured('DEBUG', message, kwargs)
    
    def critical(self, message: str, **kwargs):
        self.log_structured('CRITICAL', message, kwargs)

class ProcessManager:
    """進程管理器，替代nohup的功能"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.pid_file = self.log_dir / "process.pid"
        self.logger = StructuredLogger("process_manager", log_dir)
    
    def daemonize(self):
        """將進程轉為守護進程"""
        try:
            # 第一次fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            self.logger.error(f"第一次fork失敗: {e}")
            sys.exit(1)
        
        # 脫離父進程環境
        os.chdir("/")
        os.setsid()
        os.umask(0)
        
        try:
            # 第二次fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            self.logger.error(f"第二次fork失敗: {e}")
            sys.exit(1)
        
        # 重定向標準文件描述符
        sys.stdout.flush()
        sys.stderr.flush()
        
        # 打開日誌文件
        si = open(os.devnull, 'r')
        so = open(self.log_dir / "stdout.log", 'a+')
        se = open(self.log_dir / "stderr.log", 'a+')
        
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
    
    def write_pid_file(self):
        """寫入PID文件"""
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
    
    def remove_pid_file(self):
        """刪除PID文件"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception as e:
            self.logger.error(f"刪除PID文件失敗: {e}")
    
    def is_running(self) -> bool:
        """檢查進程是否在運行"""
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 檢查進程是否存在
            os.kill(pid, 0)
            return True
        except (ValueError, OSError, ProcessLookupError):
            return False
    
    def get_pid(self) -> Optional[int]:
        """獲取進程PID"""
        if not self.pid_file.exists():
            return None
        
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (ValueError, OSError):
            return None
    
    def stop_process(self) -> bool:
        """停止進程"""
        pid = self.get_pid()
        if not pid:
            return False
        
        try:
            # 先發送SIGTERM，給進程優雅退出的機會
            os.kill(pid, 15)  # SIGTERM
            
            # 等待進程結束
            for _ in range(10):  # 最多等待10秒
                time.sleep(1)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    # 進程已結束
                    self.remove_pid_file()
                    return True
            
            # 如果進程還在，發送SIGKILL
            os.kill(pid, 9)  # SIGKILL
            self.remove_pid_file()
            return True
            
        except ProcessLookupError:
            # 進程已不存在
            self.remove_pid_file()
            return True
        except OSError as e:
            self.logger.error(f"停止進程失敗: {e}")
            return False

# 全局日誌管理器實例字典（每個name對應一個logger）
_loggers: Dict[str, StructuredLogger] = {}

def get_logger(name: str = "trading_bot", log_dir: str = "logs") -> StructuredLogger:
    """獲取日誌記錄器實例（每個name一個實例）
    
    Args:
        name: 日誌記錄器名稱，用於區分不同的日誌源
        log_dir: 日誌目錄路徑，默認為 "logs"
    
    Returns:
        StructuredLogger: 對應名稱的日誌記錄器實例
        
    Note:
        相同名稱的多次調用會返回同一個實例（單例模式）
        不同名稱會創建不同的實例，各自有獨立的日誌文件
    """
    global _loggers
    
    # 如果該名稱的logger已存在，直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 創建新的logger實例
    logger = StructuredLogger(name, log_dir=log_dir)
    _loggers[name] = logger
    
    return logger

def get_process_manager() -> ProcessManager:
    """獲取進程管理器實例"""
    return ProcessManager()

# 清理舊日誌的函數
def cleanup_old_logs(log_dir: str = "logs", days_to_keep: int = 30):
    """清理超過指定天數的舊日誌文件"""
    import glob
    from datetime import datetime, timedelta
    
    log_path = Path(log_dir)
    if not log_path.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    # 清理所有.log和.gz文件
    for pattern in ['*.log', '*.log.*', '*.gz']:
        for file_path in log_path.glob(pattern):
            try:
                # 獲取文件修改時間
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    file_path.unlink()
                    print(f"刪除舊日誌文件: {file_path}")
            except Exception as e:
                print(f"刪除文件失敗 {file_path}: {e}")

if __name__ == "__main__":
    # 測試日誌系統
    logger = get_logger("test")
    
    logger.info("日誌系統測試開始")
    logger.debug("這是一條調試信息", component="test", value=42)
    logger.warning("這是一條警告信息", user_id="12345")
    logger.error("這是一條錯誤信息", error_code="E001", details={"field": "value"})
    
    # 測試結構化日誌
    logger.log_structured("INFO", "結構化日誌測試", {
        "event": "test_event",
        "data": {"key": "value", "number": 123},
        "user": {"id": "user123", "name": "測試用戶"}
    })
    
    print("日誌測試完成，請查看 logs/ 目錄")
