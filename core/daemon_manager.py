import os
import sys
import time
import signal
import argparse
import subprocess
import atexit
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import psutil
from datetime import datetime

# 支持相對導入和絕對導入
try:
    # 作為模塊導入時使用相對導入
    from .log_manager import StructuredLogger, ProcessManager, get_logger, cleanup_old_logs, _loggers
    from .instance_manager import InstanceRegistry
except ImportError:
    # 直接運行時使用絕對導入
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.log_manager import StructuredLogger, ProcessManager, get_logger, cleanup_old_logs, _loggers
    from core.instance_manager import InstanceRegistry

class TradingBotDaemon:
    """交易機器人守護進程管理器"""

    def __init__(self, config_file: str = "config/daemon_config.json", instance_id: Optional[str] = None):
        self.config_file = Path(config_file)
        # 檢查是否為新的多配置格式
        self.is_multi_config = self._is_multi_config_format(config_file)

        # 確定實例 ID（優先級：參數 > 配置 > 文件名）
        if instance_id:
            self.instance_id = instance_id
        elif self.is_multi_config:
            # 從配置文件讀取 instance_id
            config_data = self._load_config_for_instance_id()
            self.instance_id = config_data.get('metadata', {}).get('instance_id') or self.config_file.stem
        else:
            # 傳統配置，使用文件名作為 instance_id
            self.instance_id = self.config_file.stem

        # 實例專用日誌目錄
        self.log_dir = Path(f"logs/{self.instance_id}")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 使用高級日誌系統（傳遞實例專用日誌目錄）
        self.logger = get_logger("trading_bot_daemon", log_dir=str(self.log_dir))
        self.process_manager = ProcessManager(str(self.log_dir))
        self.registry = InstanceRegistry()

        # 配置
        self.config = self.load_config()

        # 信號處理
        self.running = True
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # 子進程管理（防止資源泄漏）- 使用實例專用 PID 文件
        self._bot_process: Optional[subprocess.Popen] = None
        self._bot_pid_file = self.log_dir / "bot.pid"

        # 註冊退出時的清理函數
        atexit.register(self._cleanup_bot_process)
        
        # 注意：不在 __init__ 中註冊實例，只在 start() 時才註冊
        # 避免 status/stop 等查詢命令也產生註冊記錄
    
    def _is_multi_config_format(self, config_file: str) -> bool:
        """檢查是否為新的多配置格式"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
                # 新格式包含 metadata, daemon_config, exchange_config, strategy_config
                return all(key in config_data for key in ["metadata", "daemon_config", "exchange_config", "strategy_config"])
        except:
            return False

    def _load_config_for_instance_id(self) -> Dict[str, Any]:
        """提前加載配置以獲取 instance_id（不展開環境變量）"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            # 如果加載失敗，返回空字典
            return {}
    
    def load_config(self) -> Dict[str, Any]:
        """載入配置文件"""
        if self.is_multi_config:
            return self._load_multi_config()
        else:
            return self._load_legacy_config()
    
    def _load_legacy_config(self) -> Dict[str, Any]:
        """載入傳統配置格式"""
        default_config = {
            "python_path": sys.executable,
            "script_path": "run.py",
            "working_dir": str(Path.cwd()),
            "log_dir": str(self.log_dir),
            "max_restart_attempts": 3,
            "restart_delay": 60,
            "health_check_interval": 30,
            "memory_limit_mb": 2048,
            "cpu_limit_percent": 80,
            "auto_restart": True,
            "environment": {},
            "bot_stop_timeout": 25,
            "bot_kill_timeout": 5,
            "log_cleanup_interval": 86400,  # 日誌清理間隔（秒），默認為24小時
            "log_retention_days": 2  # 日誌保留天數，默認為2天
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # 合併配置
                    default_config.update(loaded_config)
                    self.logger.info("傳統配置已載入", config_file=str(self.config_file))
            except Exception as e:
                self.logger.error("載入傳統配置文件失敗，使用默認配置", error=str(e))
        
        return default_config
    
    def _load_multi_config(self) -> Dict[str, Any]:
        """載入新的多配置格式"""
        try:
            # 導入配置管理器
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            
            # 加載配置文件（不展開環境變量，先驗證）
            config_data = config_manager.load_config(self.config_file, expand_vars=False)
            
            # 驗證配置
            validation_result = config_manager.validate_config(config_data)
            if not validation_result.is_valid:
                self.logger.error("配置驗證失敗:")
                for error in validation_result.errors:
                    self.logger.error(f"  - {error}")
                raise ValueError("配置驗證失敗")
            
            if validation_result.warnings:
                self.logger.warning("配置驗證警告:")
                for warning in validation_result.warnings:
                    self.logger.warning(f"  - {warning}")
            
            # 驗證通過後，再展開環境變量
            config_data_expanded = config_manager.expand_env_vars(config_data)
            
            # 提取守護進程配置
            daemon_config = config_data_expanded.get("daemon_config", {})
            exchange_config = config_data_expanded.get("exchange_config", {})
            strategy_config = config_data.get("strategy_config", {})  # 使用未展開的策略配置
            metadata = config_data.get("metadata", {})
            
            # 構建 bot_args
            bot_args = self._build_bot_args(metadata, strategy_config)
            
            # 合併配置
            final_config = {
                "python_path": daemon_config.get("python_path", sys.executable),
                "script_path": daemon_config.get("script_path", "run.py"),
                "working_dir": daemon_config.get("working_dir", str(Path.cwd())),
                "log_dir": daemon_config.get("log_dir", str(self.log_dir)),
                "db_path": daemon_config.get("db_path", "database/trade.db"),
                "web_port": daemon_config.get("web_port", 5000),
                "max_restart_attempts": daemon_config.get("max_restart_attempts", 3),
                "restart_delay": daemon_config.get("restart_delay", 60),
                "health_check_interval": daemon_config.get("health_check_interval", 30),
                "memory_limit_mb": daemon_config.get("memory_limit_mb", 2048),
                "cpu_limit_percent": daemon_config.get("cpu_limit_percent", 80),
                "auto_restart": daemon_config.get("auto_restart", True),
                "environment": exchange_config,
                "bot_stop_timeout": 25,
                "bot_kill_timeout": 5,
                "log_cleanup_interval": daemon_config.get("log_cleanup_interval", 86400),
                "log_retention_days": daemon_config.get("log_retention_days", 2),
                "bot_args": bot_args
            }
            
            self.logger.info("多配置格式已載入",
                          config_file=str(self.config_file),
                          exchange=metadata.get("exchange"),
                          symbol=metadata.get("symbol"),
                          strategy=metadata.get("strategy"))
            
            return final_config
            
        except Exception as e:
            self.logger.error("載入多配置文件失敗，使用默認配置", error=str(e))
            # 回退到默認配置
            return self._load_legacy_config()
    
    def _build_bot_args(self, metadata: Dict, strategy_config: Dict) -> List[str]:
        """根據配置構建 bot_args
        
        支持多種鍵名格式，以兼容不同版本的配置文件：
        - grid_upper_price 和 grid_upper 都能識別為 --grid-upper
        - grid_lower_price 和 grid_lower 都能識別為 --grid-lower
        """
        args = []
        
        # 基本參數
        args.extend([
            "--exchange", metadata.get("exchange", "backpack"),
            "--symbol", metadata.get("symbol", ""),
            "--strategy", metadata.get("strategy", "standard")
        ])
        
        # 市場類型
        if metadata.get("market_type"):
            args.extend(["--market-type", metadata["market_type"]])
        
        # 策略特定參數
        strategy = metadata.get("strategy", "")
        
        if strategy in ["grid", "perp_grid"]:
            # 網格策略參數 - 支持多種鍵名格式
            # 鍵名映射：命令行參數 -> [配置文件可能的鍵名列表]
            grid_param_mapping = {
                "grid-upper": ["grid_upper_price", "grid_upper"],
                "grid-lower": ["grid_lower_price", "grid_lower"],
                "grid-num": ["grid_num"],
                "grid-mode": ["grid_mode"],
                "grid-type": ["grid_type"],
                "max-position": ["max_position"],
                "quantity": ["order_quantity", "quantity"],
                "stop-loss": ["stop_loss"],
                "take-profit": ["take_profit"],
                "boundary-action": ["boundary_action"],
                "boundary-tolerance": ["boundary_tolerance"],
                "enable-boundary-check": ["enable_boundary_check"],
                "duration": ["duration"],
                "interval": ["interval"]
            }
            
            for param, possible_keys in grid_param_mapping.items():
                # 嘗試所有可能的鍵名
                value = None
                for key in possible_keys:
                    if key in strategy_config:
                        value = strategy_config[key]
                        break
                
                if value is not None:
                    if isinstance(value, bool):
                        if value:
                            args.extend([f"--{param}"])
                        elif param.startswith("enable"):
                            args.extend([f"--disable-{param[7:]}"])
                    else:
                        args.extend([f"--{param}", str(value)])
        
        elif strategy in ["standard", "perp_standard", "maker_hedge"]:
            # 標準策略參數
            standard_params = [
                "spread", "quantity", "max-orders", "target-position",
                "max-position", "position-threshold", "inventory-skew",
                "stop-loss", "take-profit", "duration", "interval"
            ]
            
            for param in standard_params:
                key = param.replace("-", "_")
                if key in strategy_config:
                    value = strategy_config[key]
                    if value is not None:
                        args.extend([f"--{param}", str(value)])
        
        return args
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info("配置已保存", config_file=str(self.config_file))
        except Exception as e:
            self.logger.error("保存配置文件失敗", error=str(e))

    def _register_instance(self):
        """使用 InstanceRegistry 註冊實例"""
        try:
            self.registry.register(self.instance_id, {
                "config_file": str(self.config_file),
                "pid": os.getpid(),
                "log_dir": str(self.log_dir),
                "web_port": self.config.get("web_port"),
                "started_at": datetime.now().isoformat(),
                "status": "starting"
            })
            self.logger.info("實例已註冊", instance_id=self.instance_id, pid=os.getpid())
        except Exception as e:
            self.logger.warning("註冊實例失敗", error=str(e))

    def _unregister_instance(self):
        """使用 InstanceRegistry 註銷實例"""
        try:
            if self.registry.unregister(self.instance_id):
                self.logger.info("實例已註銷", instance_id=self.instance_id)
        except Exception as e:
            self.logger.warning("註銷實例失敗", error=str(e))

    def _signal_handler(self, signum, frame):
        """信號處理函數
        
        收到 SIGTERM/SIGINT 時執行優雅停止：
        1. 設置停止標誌
        2. 先停止 bot 進程（讓它有機會取消訂單）
        3. 然後退出主循環
        """
        self.logger.info("收到停止信號", signal=signum)
        self.running = False
        
        # 優雅停止 bot 進程（讓它有機會取消訂單）
        self.logger.info("正在優雅停止 bot 進程...")
        try:
            self._stop_bot_process()
            self.logger.info("Bot 進程已停止")
        except Exception as e:
            self.logger.warning("停止 bot 進程時發生錯誤", error=str(e))
    
    def start(self, daemonize: bool = True) -> bool:
        """啟動守護進程"""
        try:
            # 清除日誌記錄器緩存，確保使用新的配置
            _loggers.clear()
            
            # 重新創建日誌記錄器（使用實例專用的日誌目錄）
            self.logger = get_logger("trading_bot_daemon", log_dir=str(self.log_dir))
            self.process_manager = ProcessManager(str(self.log_dir))
            
            # 檢查是否已經在運行
            if self.process_manager.is_running():
                pid = self.process_manager.get_pid()
                self.logger.warning("進程已在運行中", pid=pid)
                return False
            
            self.logger.info("開始啟動守護進程")
            
            if daemonize:
                # 創建子進程來運行守護進程，確保SSH斷開後繼續運行
                daemon_pid = os.fork()
                if daemon_pid > 0:
                    # 父進程退出，讓子進程成為孤兒進程
                    self.logger.info("守護進程已啟動在後台", child_pid=daemon_pid)
                    return True
                
                # 子進程繼續執行
                os.setsid()  # 創建新會話
                os.umask(0)  # 清除文件模式創建掩碼
                
                # 重要：fork 後子進程必須重新初始化日誌器和進程管理器
                # 因為父進程的文件描述符和日誌處理器可能已關閉或有衝突
                # 這是多實例能夠同時運行的關鍵
                _loggers.clear()
                self.logger = get_logger("trading_bot_daemon", log_dir=str(self.log_dir))
                self.process_manager = ProcessManager(str(self.log_dir))
            
            # 此時已在最終守護進程中（daemonize=True 時為子進程，否則為原進程）
            # 使用正確的 PID 註冊實例到全局註冊表
            self._register_instance()
            
            # 寫入PID文件
            self.process_manager.write_pid_file()
            
            self.logger.info("守護進程已啟動", pid=self.process_manager.get_pid())
            
            # 啟動主循環
            self._main_loop()
            
            return True
            
        except Exception as e:
            self.logger.error("啟動守護進程失敗", error=str(e))
            return False
    
    def stop(self) -> bool:
        """停止本實例的守護進程和 bot
        
        只會停止自己實例的進程，不會影響其他實例。
        
        優雅停止流程：
        1. 先發送 SIGTERM 給 bot 進程，讓它有時間取消訂單
        2. 等待足夠時間讓 bot 完成清理工作
        3. 再停止守護進程
        """
        try:
            # 獲取配置的超時時間
            bot_cleanup_timeout = self.config.get("bot_stop_timeout", 25)
            
            # 1. 先發送 SIGTERM 給 bot 進程
            self.logger.info("正在停止本實例的交易機器人進程...", instance_id=self.instance_id)
            self.logger.info(f"等待 bot 進程完成清理（取消訂單等），超時時間: {bot_cleanup_timeout} 秒")
            
            # 停止 bot 進程（_stop_bot_process 內部會等待進程退出）
            bot_stopped = self._stop_bot_process()
            
            if bot_stopped:
                self.logger.info("Bot 進程已停止，訂單應已取消")
            else:
                self.logger.warning("未找到運行中的 bot 進程")
            
            # 2. 額外等待一小段時間確保清理完成
            time.sleep(2)

            # 3. 檢查守護進程是否在運行
            if not self.process_manager.is_running():
                self.logger.warning("守護進程未在運行")
                # 清理註冊（即使進程未運行，也應該清理註冊表）
                self._unregister_instance()
                return True  # bot 已停止，視為成功

            pid = self.process_manager.get_pid()
            self.logger.info("正在停止守護進程", pid=pid)

            # 停止守護進程本身
            success = self.process_manager.stop_process()

            if success:
                self.logger.info("守護進程已停止")
                # 清理註冊
                self._unregister_instance()
            else:
                self.logger.error("停止守護進程失敗")

            return success

        except Exception as e:
            self.logger.error("停止守護進程失敗", error=str(e), exc_info=True)
            return False
    
    def restart(self) -> bool:
        """重啟守護進程"""
        self.logger.info("開始重啟守護進程")
        
        # 先停止
        self.stop()
        
        # 等待一下
        time.sleep(2)
        
        # 再啟動
        return self.start()
    
    def status(self) -> Dict[str, Any]:
        """獲取進程狀態"""
        status = {
            "running": self.process_manager.is_running(),
            "timestamp": datetime.now().isoformat(),
            "config": self.config
        }
        
        if status["running"]:
            pid = self.process_manager.get_pid()
            status["pid"] = pid
            
            try:
                # 獲取進程詳細信息
                process = psutil.Process(pid)
                status["process_info"] = {
                    "name": process.name(),
                    "cmdline": process.cmdline(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
                    "cpu_percent": process.cpu_percent(),
                    "memory_info": {
                        "rss": process.memory_info().rss,
                        "vms": process.memory_info().vms,
                        "rss_mb": process.memory_info().rss / 1024 / 1024
                    },
                    "status": process.status(),
                    "num_threads": process.num_threads()
                }
                
                # 檢查資源使用情況
                memory_mb = status["process_info"]["memory_info"]["rss_mb"]
                cpu_percent = status["process_info"]["cpu_percent"]
                
                if memory_mb > self.config.get("memory_limit_mb", 2048):
                    status["resource_warning"] = f"內存使用超過限制: {memory_mb:.1f}MB > {self.config['memory_limit_mb']}MB"
                
                if cpu_percent > self.config.get("cpu_limit_percent", 80):
                    status["resource_warning"] = f"CPU使用超過限制: {cpu_percent:.1f}% > {self.config['cpu_limit_percent']}%"
                
            except psutil.NoSuchProcess:
                status["error"] = "進程不存在"
            except Exception as e:
                status["error"] = f"獲取進程信息失敗: {e}"
        
        return status
    
    def _main_loop(self):
        """主循環，監控和重啟交易機器人
        
        首次啟動時會無條件啟動 bot，之後根據 auto_restart 設置決定是否自動重啟。
        - auto_restart: 控制 bot 崩潰後是否自動重啟（不影響首次啟動）
        """
        restart_count = 0
        last_restart_time = 0
        last_log_cleanup_time = time.time()  # 記錄上次日誌清理時間
        first_start = True  # 標記是否為首次啟動
        
        while self.running:
            try:
                # 檢查交易機器人進程
                bot_running = self._is_bot_running()
                
                if bot_running:
                    # 如果機器人在運行，重置重啟計數器和首次啟動標記
                    first_start = False
                    if restart_count > 0:
                        self.logger.info("交易機器人已恢復運行，重置重啟計數器", 
                                       previous_restart_count=restart_count)
                        restart_count = 0
                elif first_start or self.config.get("auto_restart", True):
                    # 首次啟動時無條件啟動 bot，或者 auto_restart 為 True 時自動重啟
                    current_time = time.time()
                    
                    # 首次啟動不受重啟次數限制
                    if not first_start:
                        # 檢查重啟次數限制（僅對非首次啟動生效）
                        if restart_count >= self.config.get("max_restart_attempts", 3):
                            self.logger.error("達到最大重啟次數，停止自動重啟", 
                                            max_attempts=self.config["max_restart_attempts"])
                            break
                        
                        # 檢查重啟間隔（僅對非首次啟動生效）
                        if current_time - last_restart_time < self.config.get("restart_delay", 60):
                            time.sleep(10)
                            continue
                    
                    if first_start:
                        self.logger.info("首次啟動交易機器人")
                    else:
                        self.logger.warning("交易機器人未運行，正在重啟", 
                                          restart_count=restart_count + 1)
                    
                    # 啟動/重啟交易機器人
                    if self._start_bot():
                        if first_start:
                            self.logger.info("交易機器人首次啟動成功")
                            first_start = False
                        else:
                            restart_count += 1
                            self.logger.info("交易機器人重啟成功")
                        last_restart_time = current_time
                    else:
                        if first_start:
                            self.logger.error("交易機器人首次啟動失敗")
                            # 首次啟動失敗後，轉為重啟模式（如果 auto_restart 為 True）
                            first_start = False
                            restart_count = 1
                        else:
                            self.logger.error("交易機器人重啟失敗")
                
                # 健康檢查
                self._health_check()
                
                # 檢查是否需要清理日誌
                current_time = time.time()
                log_cleanup_interval = self.config.get("log_cleanup_interval", 86400)  # 默認24小時
                if current_time - last_log_cleanup_time >= log_cleanup_interval:
                    self._cleanup_logs()
                    last_log_cleanup_time = current_time
                
                # 等待下一個檢查週期
                time.sleep(self.config.get("health_check_interval", 30))
                
            except Exception as e:
                self.logger.error("主循環錯誤", error=str(e))
                time.sleep(10)
        
        self.logger.info("主循環已停止")
    
    def _is_bot_running(self) -> bool:
        """檢查本實例的交易機器人是否在運行
        
        只檢查自己實例的 bot，不會誤判其他實例的狀態。
        """
        # 優先檢查進程是否存在（更可靠）
        if self._check_bot_process():
            return True
        
        # 如果進程不存在，再檢查健康檢查端點（可能Web服務器還沒啟動）
        try:
            import requests
            # 使用配置的端口，而不是硬編碼 5000
            web_port = self.config.get("web_port", 5000)
            health_url = f"http://localhost:{web_port}/health"
            response = requests.get(health_url, timeout=5)
            # 即使返回503，只要進程存在就認為在運行
            return response.status_code in [200, 503]
        except Exception:
            # 如果健康檢查也失敗，返回False（進程已經檢查過不存在）
            return False
    
    def _check_bot_process(self) -> bool:
        """通過 bot.pid 檢查本實例的交易機器人是否在運行
        
        只檢查自己實例的 bot 進程（通過 bot.pid 文件追蹤），
        不會影響其他實例的進程。
        """
        try:
            # 只檢查自己的 bot.pid 文件
            if not self._bot_pid_file.exists():
                return False
            
            with open(self._bot_pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 檢查該 PID 是否存在且正在運行
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            
            return False
            
        except (ValueError, FileNotFoundError):
            # PID 文件內容無效或不存在
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # 進程不存在或無權限訪問
            return False
        except Exception as e:
            self.logger.error("檢查進程失敗", error=str(e))
            return False
    
    def _stop_bot_process(self) -> int:
        """只停止本實例的 bot 進程（通過 bot.pid 追蹤）
        
        只會停止自己實例啟動的 bot 進程，不會影響其他實例。
        
        Returns:
            int: 停止的進程數量（0 或 1）
        """
        try:
            # 檢查 bot.pid 文件是否存在
            if not self._bot_pid_file.exists():
                self.logger.debug("沒有 bot.pid 文件，無需停止進程")
                return 0
            
            # 讀取 PID
            try:
                with open(self._bot_pid_file, 'r') as f:
                    pid = int(f.read().strip())
            except (ValueError, FileNotFoundError):
                self.logger.debug("bot.pid 文件內容無效或不存在")
                self._remove_bot_pid_file()
                return 0
            
            # 檢查進程是否存在
            if not psutil.pid_exists(pid):
                self.logger.debug("bot.pid 中的進程不存在", pid=pid)
                self._remove_bot_pid_file()
                return 0
            
            # 獲取進程對象
            try:
                proc = psutil.Process(pid)
            except psutil.NoSuchProcess:
                self.logger.debug("進程已不存在", pid=pid)
                self._remove_bot_pid_file()
                return 0
            
            stop_timeout = max(1, int(self.config.get("bot_stop_timeout", 20)))
            kill_timeout = max(1, int(self.config.get("bot_kill_timeout", 5)))
            
            self.logger.info("正在停止本實例的 bot 進程", pid=pid, instance_id=self.instance_id)
            
            # 優雅停止：先發送 SIGTERM
            try:
                proc.terminate()
                if self._wait_process_exit(proc, stop_timeout):
                    self.logger.info("進程已優雅停止", pid=pid)
                else:
                    self.logger.warning(
                        f"進程未在 {stop_timeout} 秒內終止，強制殺掉",
                        pid=pid
                    )
                    proc.kill()
                    if not self._wait_process_exit(proc, kill_timeout):
                        self.logger.error(
                            f"強制殺掉後 {kill_timeout} 秒內仍未退出",
                            pid=pid
                        )
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                # 進程可能已經停止
                self.logger.debug("進程已不存在或無權限", pid=pid, error=str(e))
            
            # 清理 PID 文件
            self._remove_bot_pid_file()
            
            # 等待一下讓進程完全停止
            time.sleep(1)
            return 1
            
        except Exception as e:
            self.logger.error("停止 bot 進程時出錯", error=str(e))
            return 0

    def _wait_process_exit(self, proc: psutil.Process, timeout: int) -> bool:
        """等待指定進程在 timeout 秒內退出"""
        try:
            proc.wait(timeout=timeout)
            return True
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return True
        except psutil.TimeoutExpired:
            return False
    
    def _start_bot(self) -> bool:
        """啟動本實例的交易機器人"""
        try:
            # 先停止本實例之前的 bot 進程（防止重複運行）
            self._stop_bot_process()
            
            # 清理之前的進程引用
            if self._bot_process is not None:
                try:
                    if self._bot_process.poll() is None:
                        self.logger.warning("發現之前的子進程仍在運行，正在停止", 
                                          pid=self._bot_process.pid)
                        self._bot_process.terminate()
                        try:
                            self._bot_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            self._bot_process.kill()
                            self._bot_process.wait()
                except Exception as e:
                    self.logger.warning("清理舊進程時出錯", error=str(e))
                finally:
                    self._bot_process = None
            
            self.logger.info("正在啟動交易機器人")
            
            # 構建命令
            cmd = [
                self.config["python_path"],
                self.config["script_path"]
            ]
            
            # 添加參數
            if "bot_args" in self.config:
                cmd.extend(self.config["bot_args"])
            
            # 設置環境變量
            env = os.environ.copy()
            env.update(self.config.get("environment", {}))

            # 添加 Web 端口環境變量
            if "web_port" in self.config:
                env['WEB_PORT'] = str(self.config['web_port'])
                self.logger.info("設置 Web 端口環境變量", web_port=self.config['web_port'])

            # 添加數據庫路徑環境變量
            if "db_path" in self.config:
                env['DB_PATH'] = str(self.config['db_path'])
                self.logger.info("設置數據庫路徑環境變量", db_path=self.config['db_path'])

            # 準備輸出重定向文件（避免使用PIPE導致阻塞）
            # 子進程的stdout/stderr重定向到日誌文件，避免SSH斷開時管道阻塞
            # 使用基於時間的目錄結構
            current_date = datetime.now().strftime('%Y-%m-%d')
            date_dir = self.log_dir / current_date
            date_dir.mkdir(exist_ok=True)
            
            stdout_log = date_dir / "bot_stdout.log"
            stderr_log = date_dir / "bot_stderr.log"
            
            # 以追加模式打開日誌文件，確保SSH斷開後仍能正常寫入
            stdout_file = open(stdout_log, 'a', buffering=1)  # 行緩衝
            stderr_file = open(stderr_log, 'a', buffering=1)  # 行緩衝
            
            try:
                # 啟動進程，重定向到文件而不是PIPE
                process = subprocess.Popen(
                    cmd,
                    cwd=self.config["working_dir"],
                    env=env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    # 確保進程獨立於父進程，SSH斷開不會影響
                    start_new_session=True
                )
            finally:
                # 關閉文件描述符（子進程已經繼承了副本）
                stdout_file.close()
                stderr_file.close()
            
            # 保存進程引用（防止資源泄漏）
            self._bot_process = process
            
            # 保存子進程PID到文件（用於恢復和追蹤）
            try:
                with open(self._bot_pid_file, 'w') as f:
                    f.write(str(process.pid))
                    f.flush()
                    os.fsync(f.fileno())  # 確保寫入磁盤
                self.logger.debug("已保存子進程PID到文件", pid=process.pid, 
                                pid_file=str(self._bot_pid_file))
            except Exception as e:
                self.logger.warning("保存子進程PID文件失敗", error=str(e))
            
            self.logger.info("交易機器人進程已啟動", 
                            pid=process.pid, 
                            cmd=" ".join(cmd),
                            stdout_log=str(stdout_log),
                            stderr_log=str(stderr_log))
            
            # 等待一下讓進程啟動
            time.sleep(5)
            
            # 檢查進程是否還在運行
            if process.poll() is None:
                return True
            else:
                # 進程已經退出，讀取錯誤日誌
                try:
                    with open(stderr_log, 'r') as f:
                        stderr_content = f.read()
                    with open(stdout_log, 'r') as f:
                        stdout_content = f.read()
                except Exception:
                    stderr_content = "無法讀取錯誤日誌"
                    stdout_content = "無法讀取輸出日誌"
                
                self.logger.error("交易機器人啟動失敗", 
                                return_code=process.returncode,
                                stdout=stdout_content[-1000:] if stdout_content else "",  # 只顯示最後1000字符
                                stderr=stderr_content[-1000:] if stderr_content else "")  # 只顯示最後1000字符
                # 清理引用
                self._bot_process = None
                self._remove_bot_pid_file()
                return False
                
        except Exception as e:
            self.logger.error("啟動交易機器人失敗", error=str(e), exc_info=True)
            # 清理引用
            self._bot_process = None
            self._remove_bot_pid_file()
            return False
    
    def _cleanup_bot_process(self):
        """清理子進程資源（防止資源泄漏）"""
        try:
            # 清理進程引用
            if self._bot_process is not None:
                try:
                    if self._bot_process.poll() is None:
                        # 進程仍在運行，嘗試優雅停止
                        self.logger.info("清理子進程資源", pid=self._bot_process.pid)
                        self._bot_process.terminate()
                        try:
                            self._bot_process.wait(timeout=5)
                            self.logger.debug("子進程已優雅停止", pid=self._bot_process.pid)
                        except subprocess.TimeoutExpired:
                            # 強制停止
                            self.logger.warning("子進程未在5秒內停止，強制殺掉", 
                                              pid=self._bot_process.pid)
                            self._bot_process.kill()
                            self._bot_process.wait(timeout=2)
                except Exception as e:
                    self.logger.warning("清理子進程時出錯", error=str(e))
                finally:
                    self._bot_process = None
            
            # 清理PID文件
            self._remove_bot_pid_file()
            
        except Exception as e:
            self.logger.error("清理子進程資源失敗", error=str(e))
    
    def _remove_bot_pid_file(self):
        """刪除子進程PID文件"""
        try:
            if self._bot_pid_file.exists():
                self._bot_pid_file.unlink()
                self.logger.debug("已刪除子進程PID文件", pid_file=str(self._bot_pid_file))
        except Exception as e:
            self.logger.warning("刪除子進程PID文件失敗", error=str(e))
    
    def _health_check(self):
        """健康檢查"""
        try:
            # 檢查磁盤空間
            disk_usage = psutil.disk_usage(self.config["working_dir"])
            if disk_usage.percent > 90:
                self.logger.warning("磁盤空間不足", 
                                  percent=disk_usage.percent,
                                  free_gb=disk_usage.free / 1024 / 1024 / 1024)
            
            # 檢查內存使用
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                self.logger.warning("系統內存使用率過高", 
                                  percent=memory.percent)
            
            # 檢查系統負載
            load_avg = psutil.getloadavg()
            cpu_count = psutil.cpu_count()
            if load_avg[0] > cpu_count * 2:
                self.logger.warning("系統負載過高", 
                                  load_avg=load_avg[0],
                                  cpu_count=cpu_count)
            
        except Exception as e:
            self.logger.error("健康檢查失敗", error=str(e))
    
    def _cleanup_logs(self):
        """清理舊日誌文件"""
        try:
            log_retention_days = self.config.get("log_retention_days", 2)
            self.logger.info("開始清理舊日誌文件", retention_days=log_retention_days)
            
            # 調用日誌清理函數
            cleanup_old_logs(
                log_dir=self.config["log_dir"],
                days_to_keep=log_retention_days,
                cleanup_root_logs=True
            )
            
            self.logger.info("舊日誌文件清理完成", retention_days=log_retention_days)
            
        except Exception as e:
            self.logger.error("清理舊日誌文件失敗", error=str(e))

def list_instances():
    """列出所有運行中的實例"""
    try:
        registry_file = Path("logs/instances.json")
        if not registry_file.exists():
            print("沒有運行中的實例")
            return

        with open(registry_file, 'r') as f:
            registry = json.load(f)

        if not registry:
            print("沒有運行中的實例")
            return

        print(f"\n{'實例ID':<20} {'PID':<10} {'Web端口':<10} {'配置文件':<50} {'啟動時間':<25}")
        print("-" * 115)
        for instance_id, info in registry.items():
            # 檢查進程是否還在運行
            status = "🟢"
            pid = info.get('pid')
            try:
                if pid and psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    if not proc.is_running():
                        status = "🔴"
                else:
                    status = "🔴"
            except:
                status = "🔴"

            # 安全獲取各個字段，處理 None 值
            pid_str = str(pid) if pid is not None else 'N/A'
            web_port = info.get('web_port')
            web_port_str = str(web_port) if web_port is not None else 'N/A'
            config_file = info.get('config_file') or 'N/A'
            started_at = info.get('started_at') or 'N/A'

            print(f"{status} {instance_id:<18} {pid_str:<10} {web_port_str:<10} "
                  f"{config_file:<50} {started_at:<25}")

        print()

    except Exception as e:
        print(f"錯誤: 列出實例失敗 - {e}")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='交易機器人守護進程管理器')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status', 'list'],
                       help='操作: start(啟動), stop(停止), restart(重啟), status(狀態), list(列表)')
    parser.add_argument('--daemon', '-d', action='store_true',
                       help='以守護進程方式運行')
    parser.add_argument('--config', '-c', default='config/daemon_config.json',
                       help='配置文件路徑')
    parser.add_argument('--instance-id', help='實例 ID（可選，默認從配置文件讀取）')
    parser.add_argument('--log-dir', default='logs',
                       help='日誌目錄')

    args = parser.parse_args()

    # list 命令不需要創建守護進程實例
    if args.action == 'list':
        list_instances()
        sys.exit(0)

    # 創建守護進程管理器（傳遞 instance_id）
    daemon = TradingBotDaemon(args.config, instance_id=args.instance_id)

    if args.action == 'start':
        success = daemon.start(daemonize=args.daemon)
        sys.exit(0 if success else 1)

    elif args.action == 'stop':
        success = daemon.stop()
        sys.exit(0 if success else 1)

    elif args.action == 'restart':
        success = daemon.restart()
        sys.exit(0 if success else 1)

    elif args.action == 'status':
        status = daemon.status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        sys.exit(0 if status['running'] else 1)

if __name__ == '__main__':
    main()