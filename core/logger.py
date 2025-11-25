"""
日誌配置模塊
"""
import logging
import sys
from config import LOG_FILE
from pathlib import Path
from datetime import datetime

def setup_logger(name="market_maker", log_dir="logs"):
    """
    設置並返回一個配置好的logger實例
    
    Args:
        name: 日誌記錄器名稱
        log_dir: 日誌目錄路徑
    """
    # 嘗試使用新的日誌系統
    try:
        from core.log_manager import get_logger
        # 使用新的日誌系統，支持基於時間的輪轉和日期目錄
        return get_logger(name, log_dir)
    except ImportError:
        # 如果新的日誌系統不可用，回退到舊的實現
        logger = logging.getLogger(name)
        
        # 防止重複配置
        if logger.handlers:
            return logger
            
        logger.setLevel(logging.INFO)
        
        # 使用基於時間的目錄結構
        current_date = datetime.now().strftime('%Y-%m-%d')
        date_dir = Path(log_dir) / current_date
        date_dir.mkdir(exist_ok=True)
        log_file = date_dir / f"{name}.log"
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # 文件處理器（設置flushOn=INFO級別，確保每次日誌都立即寫入磁盤）
        # 創建自定義Handler以實現行緩衝
        class LineBufferedFileHandler(logging.FileHandler):
            def __init__(self, filename, mode='a', encoding=None, delay=False):
                super().__init__(filename, mode, encoding, delay)
                # 設置為行緩衝模式（buffering=1）
                import io
                if isinstance(self.stream, io.TextIOWrapper):
                    try:
                        # Python 3.7+ 支持 reconfigure
                        self.stream.reconfigure(line_buffering=True)
                    except (AttributeError, ValueError):
                        # 對於不支持的版本，創建新的行緩衝流
                        pass
            
            def emit(self, record):
                super().emit(record)
                # 強制刷新到磁盤
                if self.stream:
                    self.stream.flush()
                    try:
                        os.fsync(self.stream.fileno())
                    except (AttributeError, OSError):
                        pass
        
        import os
        file_handler = LineBufferedFileHandler(log_file, encoding='utf-8', delay=False)
        file_handler.setFormatter(formatter)
        
        # 控制台處理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # 添加處理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger