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
    
    def __init__(self, filename, maxBytes=0, backupCount=0, time_based=False):
        """初始化輪轉處理器
        
        Args:
            filename: 日誌文件名
            maxBytes: 最大字節數
            backupCount: 備份文件數量
            time_based: 是否啟用基於時間的輪轉（每天一個新文件）
        """
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount)
        self.time_based = time_based
        self.current_date = datetime.now().date()
        
        # 如果啟用基於時間的輪轉，修改文件名以包含日期
        if self.time_based:
            self.baseFilename = str(self.baseFilename)
            self.date_filename = f"{self.baseFilename}.{self.current_date.strftime('%Y-%m-%d')}"
            # 立即使用帶日期的文件名
            self.baseFilename = self.date_filename
    
    def emit(self, record):
        """發出日誌記錄，檢查是否需要輪轉"""
        try:
            # 如果啟用基於時間的輪轉，檢查日期是否變化
            if self.time_based:
                today = datetime.now().date()
                if today != self.current_date:
                    self._time_based_rollover()
                    self.current_date = today
                    # 更新baseFilename為新的日期文件名
                    self.baseFilename = f"{self.baseFilename.split('.')[0]}.{today.strftime('%Y-%m-%d')}"
            
            # 調用父類的emit方法
            super().emit(record)
        except Exception:
            self.handleError(record)
    
    def _time_based_rollover(self):
        """執行基於時間的輪轉"""
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # 獲取基礎文件名和日誌目錄
        base_name = Path(self.baseFilename).name
        log_dir = Path(self.baseFilename).parent
        
        # 壓縮昨天的日誌文件（如果存在）
        yesterday_date = self.current_date.strftime('%Y-%m-%d')
        yesterday_dir = log_dir.parent / yesterday_date
        if yesterday_dir.exists():
            for log_file in yesterday_dir.glob(f"{base_name}*"):
                if not log_file.name.endswith('.gz'):
                    # 壓縮昨天的日誌文件
                    gz_file = log_file.with_suffix(f"{log_file.suffix}.gz")
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(gz_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()
        
        # 更新新的日期和目錄
        self.current_date = datetime.now().date()
        new_date_str = self.current_date.strftime('%Y-%m-%d')
        new_dir = log_dir.parent / new_date_str
        new_dir.mkdir(exist_ok=True)
        
        # 更新文件路徑
        self.baseFilename = str(new_dir / base_name)
        
        # 重新打開日誌文件
        self.mode = 'a'  # 追加模式
        self.stream = self._open()
    
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
        
        # 獲取當前日期並創建日期目錄
        current_date = datetime.now().strftime('%Y-%m-%d')
        date_dir = self.log_dir / current_date
        date_dir.mkdir(exist_ok=True)
        
        # 1. 主要日誌文件（所有級別）- 使用基於時間的輪轉
        main_handler = CompressedRotatingFileHandler(
            date_dir / f"{self.name}.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            time_based=True  # 啟用基於時間的輪轉
        )
        main_handler.setLevel(logging.DEBUG)
        main_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        main_handler.setFormatter(main_formatter)
        self.logger.addHandler(main_handler)
        
        # 2. 錯誤日誌文件（只包含ERROR及以上）- 使用基於時間的輪轉
        error_handler = CompressedRotatingFileHandler(
            date_dir / f"{self.name}_errors.log",
            maxBytes=max_bytes // 2,
            backupCount=backup_count,
            time_based=True  # 啟用基於時間的輪轉
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
        
        # 3. 結構化JSON日誌（便於程序解析）- 使用基於時間的輪轉
        json_handler = CompressedRotatingFileHandler(
            date_dir / f"{self.name}_structured.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            time_based=True  # 啟用基於時間的輪轉
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
    
    def info(self, message: str, *args, **kwargs):
        if args:
            # 如果有位置參數，使用傳統格式化
            try:
                formatted_message = message % args
            except (TypeError, ValueError):
                # 如果格式化失敗，使用原始消息
                formatted_message = message
            self.log_structured('INFO', formatted_message, kwargs)
        else:
            # 沒有位置參數，使用現有邏輯
            self.log_structured('INFO', message, kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        if args:
            # 如果有位置參數，使用傳統格式化
            try:
                formatted_message = message % args
            except (TypeError, ValueError):
                # 如果格式化失敗，使用原始消息
                formatted_message = message
            self.log_structured('WARNING', formatted_message, kwargs)
        else:
            # 沒有位置參數，使用現有邏輯
            self.log_structured('WARNING', message, kwargs)
    
    def error(self, message: str, *args, **kwargs):
        if args:
            # 如果有位置參數，使用傳統格式化
            try:
                formatted_message = message % args
            except (TypeError, ValueError):
                # 如果格式化失敗，使用原始消息
                formatted_message = message
            self.log_structured('ERROR', formatted_message, kwargs)
        else:
            # 沒有位置參數，使用現有邏輯
            self.log_structured('ERROR', message, kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        if args:
            # 如果有位置參數，使用傳統格式化
            try:
                formatted_message = message % args
            except (TypeError, ValueError):
                # 如果格式化失敗，使用原始消息
                formatted_message = message
            self.log_structured('DEBUG', formatted_message, kwargs)
        else:
            # 沒有位置參數，使用現有邏輯
            self.log_structured('DEBUG', message, kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        if args:
            # 如果有位置參數，使用傳統格式化
            try:
                formatted_message = message % args
            except (TypeError, ValueError):
                # 如果格式化失敗，使用原始消息
                formatted_message = message
            self.log_structured('CRITICAL', formatted_message, kwargs)
        else:
            # 沒有位置參數，使用現有邏輯
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
def cleanup_old_logs(log_dir: str = "logs", days_to_keep: int = 2, cleanup_root_logs: bool = True):
    """清理超過指定天數的舊日誌文件
    
    Args:
        log_dir: 日誌目錄路徑，默認為 "logs"
        days_to_keep: 保留天數，默認為2天
        cleanup_root_logs: 是否清理根目錄的log檔案，默認為True
    """
    import glob
    from datetime import datetime, timedelta
    
    # 獲取日誌記錄器
    logger = get_logger("log_cleanup")
    
    # 清理指定日誌目錄
    _cleanup_log_directory(log_dir, days_to_keep, logger)
    
    # 清理根目錄的log檔案
    if cleanup_root_logs:
        _cleanup_root_logs(days_to_keep, logger)

def _cleanup_log_directory(log_dir: str, days_to_keep: int, logger):
    """清理指定目錄的日誌檔案"""
    import glob
    from datetime import datetime, timedelta
    
    log_path = Path(log_dir)
    if not log_path.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    cleaned_count = 0
    
    # 清理所有.log和.gz文件，但跳過當前正在使用的日誌文件
    current_log_files = set()
    current_date_dirs = set()
    
    # 獲取所有已知的當前日誌文件和日期目錄
    for logger_name in _loggers:
        if _loggers[logger_name].logger.handlers:
            for handler in _loggers[logger_name].logger.handlers:
                if hasattr(handler, 'baseFilename'):
                    file_path = Path(handler.baseFilename)
                    current_log_files.add(file_path.name)
                    # 添加當前日期目錄到保護列表
                    if file_path.parent.name and file_path.parent.name.count('-') == 2:  # YYYY-MM-DD格式
                        current_date_dirs.add(file_path.parent.name)
    
    # 添加當前日期到保護列表
    current_date_dirs.add(datetime.now().strftime('%Y-%m-%d'))
    
    # 首先清理日期目錄中的舊日誌
    for date_dir in log_path.iterdir():
        if not date_dir.is_dir() or not date_dir.name.count('-') == 2:  # 不是YYYY-MM-DD格式
            continue
            
        # 跳過當前日期目錄
        if date_dir.name in current_date_dirs:
            logger.debug("跳過當前日期目錄", date_dir=str(date_dir))
            continue
            
        try:
            # 嘗試解析目錄名中的日期
            dir_date = datetime.strptime(date_dir.name, '%Y-%m-%d').date()
            dir_datetime = datetime.combine(dir_date, datetime.min.time())
            
            if dir_datetime < cutoff_date:
                # 整個目錄都超過保留期限，刪除整個目錄
                shutil.rmtree(date_dir)
                logger.info("刪除舊日誌目錄", directory=str(date_dir))
                cleaned_count += 1
            else:
                # 目錄在保留期限內，但可能需要清理其中的舊文件
                for file_path in date_dir.glob('*'):
                    try:
                        # 跳過當前正在使用的日誌文件
                        if file_path.name in current_log_files:
                            logger.debug("跳過當前使用的日誌文件", file_path=str(file_path))
                            continue
                            
                        # 壓縮舊的日誌文件
                        if file_path.suffix == '.log' and not file_path.name.endswith('.gz'):
                            gz_file = file_path.with_suffix(f"{file_path.suffix}.gz")
                            if not gz_file.exists():
                                with open(file_path, 'rb') as f_in:
                                    with gzip.open(gz_file, 'wb') as f_out:
                                        shutil.copyfileobj(f_in, f_out)
                                file_path.unlink()
                                logger.info("壓縮日誌文件", file_path=str(file_path))
                    except Exception as e:
                        logger.error("處理日誌文件失敗", file_path=str(file_path), error=str(e))
        except ValueError:
            # 如果目錄名不是有效的日期，跳過
            continue
    
    # 清理根目錄下的舊日誌文件（兼容舊版本）
    for pattern in ['*.log', '*.log.*', '*.gz']:
        for file_path in log_path.glob(pattern):
            try:
                # 跳過當前正在使用的日誌文件
                if file_path.name in current_log_files:
                    logger.debug("跳過當前使用的日誌文件", file_path=str(file_path))
                    continue
                
                # 對於基於日期的日誌文件，從文件名中提取日期
                if '.log.' in file_path.name and any(char.isdigit() for char in file_path.name):
                    # 嘗試從文件名中提取日期 (格式: filename.YYYY-MM-DD)
                    try:
                        date_part = file_path.name.split('.')[-2]  # 獲取日期部分
                        file_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                        file_datetime = datetime.combine(file_date, datetime.min.time())
                        
                        if file_datetime < cutoff_date:
                            file_path.unlink()
                            logger.info("刪除舊日誌文件", file_path=str(file_path))
                            cleaned_count += 1
                    except (ValueError, IndexError):
                        # 如果無法解析日期，回退到使用文件修改時間
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if mtime < cutoff_date:
                            file_path.unlink()
                            logger.info("刪除舊日誌文件", file_path=str(file_path))
                            cleaned_count += 1
                else:
                    # 對於其他文件，使用文件修改時間
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        file_path.unlink()
                        logger.info("刪除舊日誌文件", file_path=str(file_path))
                        cleaned_count += 1
            except Exception as e:
                logger.error("刪除文件失敗", file_path=str(file_path), error=str(e))
    
    if cleaned_count > 0:
        logger.info("已清理日誌目錄下的舊日誌文件", directory=log_dir, count=cleaned_count)

def _cleanup_root_logs(days_to_keep: int, logger):
    """清理根目錄的日誌檔案"""
    from datetime import datetime, timedelta
    
    # 獲取根目錄路徑（當前工作目錄）
    root_path = Path.cwd()
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    cleaned_count = 0
    
    # 要清理的根目錄log檔案模式
    root_log_patterns = [
        'market_maker.log',  # 主要的根目錄log檔案
        '*.log',             # 其他可能的log檔案
    ]
    
    # 排除的檔案（系統重要檔案）
    exclude_files = {
        'setup.py', 'requirements.txt', 'README.md', '.gitignore',
        'LICENSE', 'Dockerfile', 'docker-compose.yml'
    }
    
    for pattern in root_log_patterns:
        for file_path in root_path.glob(pattern):
            # 跳過排除的檔案和目錄
            if (file_path.name in exclude_files or
                file_path.is_dir() or
                str(file_path).startswith('./logs/')):
                continue
                
            try:
                # 檢查檔案修改時間
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    # 額外安全檢查：確保這真的是log檔案
                    if _is_safe_to_delete_log(file_path):
                        file_path.unlink()
                        logger.info("刪除根目錄舊日誌文件", file_path=str(file_path))
                        cleaned_count += 1
                    else:
                        logger.info("跳過非日誌文件", file_path=str(file_path))
            except Exception as e:
                logger.error("刪除根目錄文件失敗", file_path=str(file_path), error=str(e))
    
    if cleaned_count > 0:
        logger.info("已清理根目錄下的舊日誌文件", count=cleaned_count)

def _is_safe_to_delete_log(file_path: Path) -> bool:
    """檢查檔案是否安全刪除（確保是log檔案）"""
    
    # 檢查檔案副檔名
    if file_path.suffix != '.log':
        return False
    
    # 檢查檔案大小（避免刪除重要的配置檔案）
    try:
        file_size = file_path.stat().st_size
        if file_size == 0:
            return True  # 空檔案可以安全刪除
        
        # 檢查檔案內容是否包含日誌特徵
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # 讀取前幾行檢查是否包含日誌特徵
                first_lines = [f.readline().strip() for _ in range(3)]
                
                # 日誌檔案的特徵關鍵字
                log_keywords = [
                    ' - INFO - ', ' - ERROR - ', ' - WARNING - ', ' - DEBUG - ',
                    '[INFO]', '[ERROR]', '[WARNING]', '[DEBUG]',
                    'timestamp', 'level', 'message'
                ]
                
                for line in first_lines:
                    if line and any(keyword in line for keyword in log_keywords):
                        return True
                        
        except (UnicodeDecodeError, IOError):
            # 無法讀取的檔案，不刪除
            return False
            
    except OSError:
        return False
    
    # 已知的根目錄log檔案名稱
    known_root_logs = {'market_maker.log'}
    if file_path.name in known_root_logs:
        return True
    
    return False

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
