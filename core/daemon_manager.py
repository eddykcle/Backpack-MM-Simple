"""
進程守護管理器
提供啟動、停止、重啟、狀態檢查等功能，替代 nohup
"""
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
except ImportError:
    # 直接運行時使用絕對導入
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.log_manager import StructuredLogger, ProcessManager, get_logger, cleanup_old_logs, _loggers

class TradingBotDaemon:
    """交易機器人守護進程管理器"""
    
    def __init__(self, config_file: str = "config/daemon_config.json"):
        self.config_file = Path(config_file)
        # 檢查是否為新的多配置格式
        self.is_multi_config = self._is_multi_config_format(config_file)
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 使用高級日誌系統
        self.logger = get_logger("trading_bot_daemon")
        self.process_manager = ProcessManager(str(self.log_dir))
        
        # 配置
        self.config = self.load_config()
        
        # 信號處理
        self.running = True
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 子進程管理（防止資源泄漏）
        self._bot_process: Optional[subprocess.Popen] = None
        self._bot_pid_file = self.log_dir / "bot.pid"
        
        # 註冊退出時的清理函數
        atexit.register(self._cleanup_bot_process)
    
    def _is_multi_config_format(self, config_file: str) -> bool:
        """檢查是否為新的多配置格式"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
                # 新格式包含 metadata, daemon_config, exchange_config, strategy_config
                return all(key in config_data for key in ["metadata", "daemon_config", "exchange_config", "strategy_config"])
        except:
            return False
    
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
            
            # 加載配置文件
            config_data = config_manager.load_config(self.config_file, expand_vars=True)
            
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
            
            # 提取守護進程配置
            daemon_config = config_data.get("daemon_config", {})
            exchange_config = config_data.get("exchange_config", {})
            strategy_config = config_data.get("strategy_config", {})
            metadata = config_data.get("metadata", {})
            
            # 構建 bot_args
            bot_args = self._build_bot_args(metadata, strategy_config)
            
            # 合併配置
            final_config = {
                "python_path": daemon_config.get("python_path", sys.executable),
                "script_path": daemon_config.get("script_path", "run.py"),
                "working_dir": daemon_config.get("working_dir", str(Path.cwd())),
                "log_dir": daemon_config.get("log_dir", str(self.log_dir)),
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
        """根據配置構建 bot_args"""
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
            # 網格策略參數
            grid_params = [
                "grid-upper", "grid-lower", "grid-num", "grid-mode", "grid-type",
                "max-position", "stop-loss", "take-profit",
                "boundary-action", "boundary-tolerance", "duration", "interval"
            ]
            
            for param in grid_params:
                key = param.replace("-", "_")
                if key in strategy_config:
                    value = strategy_config[key]
                    if isinstance(value, bool):
                        if value:
                            args.extend([f"--{param}"])
                    elif param.startswith("enable") and not value:
                        args.extend([f"--no-{param}"])
                    elif value is not None:
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
    
    def _signal_handler(self, signum, frame):
        """信號處理函數"""
        self.logger.info("收到停止信號", signal=signum)
        self.running = False
    
    def start(self, daemonize: bool = True) -> bool:
        """啟動守護進程"""
        try:
            # 清除日誌記錄器緩存，確保使用新的配置
            _loggers.clear()
            
            # 重新創建日誌記錄器
            self.logger = get_logger("trading_bot_daemon")
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
        """停止守護進程"""
        try:
            # 先清理子進程引用
            self._cleanup_bot_process()
            
            # 停止所有由守護進程啟動的 run.py 子進程
            self.logger.info("正在停止所有交易機器人進程...")
            self._stop_old_bot_processes()
            
            # 檢查守護進程是否在運行
            if not self.process_manager.is_running():
                self.logger.warning("守護進程未在運行")
                return False
            
            pid = self.process_manager.get_pid()
            self.logger.info("正在停止守護進程", pid=pid)
            
            # 停止守護進程本身
            success = self.process_manager.stop_process()
            
            if success:
                self.logger.info("守護進程已停止")
                # 再次確認沒有遺留的 run.py 進程
                time.sleep(1)
                remaining = self._stop_old_bot_processes()
                if remaining > 0:
                    self.logger.warning("仍有 %d 個 run.py 進程在運行", remaining)
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
        """主循環，監控和重啟交易機器人"""
        restart_count = 0
        last_restart_time = 0
        last_log_cleanup_time = time.time()  # 記錄上次日誌清理時間
        
        while self.running:
            try:
                # 檢查交易機器人進程
                bot_running = self._is_bot_running()
                
                if bot_running:
                    # 如果機器人在運行，重置重啟計數器
                    if restart_count > 0:
                        self.logger.info("交易機器人已恢復運行，重置重啟計數器", 
                                       previous_restart_count=restart_count)
                        restart_count = 0
                elif self.config.get("auto_restart", True):
                    # 機器人未運行，嘗試重啟
                    current_time = time.time()
                    
                    # 檢查重啟次數限制
                    if restart_count >= self.config.get("max_restart_attempts", 3):
                        self.logger.error("達到最大重啟次數，停止自動重啟", 
                                        max_attempts=self.config["max_restart_attempts"])
                        break
                    
                    # 檢查重啟間隔
                    if current_time - last_restart_time < self.config.get("restart_delay", 60):
                        time.sleep(10)
                        continue
                    
                    self.logger.warning("交易機器人未運行，正在重啟", 
                                      restart_count=restart_count + 1)
                    
                    # 重啟交易機器人
                    if self._start_bot():
                        restart_count += 1
                        last_restart_time = current_time
                        self.logger.info("交易機器人重啟成功")
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
        """檢查交易機器人是否在運行"""
        # 優先檢查進程是否存在（更可靠）
        if self._check_bot_process():
            return True
        
        # 如果進程不存在，再檢查健康檢查端點（可能Web服務器還沒啟動）
        try:
            import requests
            health_url = "http://localhost:5000/health"
            response = requests.get(health_url, timeout=5)
            # 即使返回503，只要進程存在就認為在運行
            return response.status_code in [200, 503]
        except Exception:
            # 如果健康檢查也失敗，返回False（進程已經檢查過不存在）
            return False
    
    def _check_bot_process(self) -> bool:
        """通過進程檢查交易機器人是否在運行"""
        try:
            # 查找運行run.py的進程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('run.py' in arg for arg in cmdline):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error("檢查進程失敗", error=str(e))
            return False
    
    def _stop_old_bot_processes(self) -> int:
        """停止所有舊的run.py進程
        
        Returns:
            int: 停止的進程數量
        """
        try:
            stopped_count = 0
            current_pid = os.getpid()
            
            stop_timeout = max(1, int(self.config.get("bot_stop_timeout", 20)))
            kill_timeout = max(1, int(self.config.get("bot_kill_timeout", 5)))
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('run.py' in arg for arg in cmdline):
                        # 跳過當前進程（如果是從daemon內部調用）
                        if proc.pid == current_pid:
                            continue
                        
                        self.logger.info("發現 run.py 進程，正在停止", pid=proc.pid)
                        
                        # 優雅停止：先發送 SIGTERM
                        try:
                            proc.terminate()
                            if self._wait_process_exit(proc, stop_timeout):
                                self.logger.info("進程已優雅停止", pid=proc.pid)
                            else:
                                self.logger.warning(
                                    f"進程未在 {stop_timeout} 秒內終止，強制殺掉",
                                    pid=proc.pid
                                )
                                proc.kill()
                                if not self._wait_process_exit(proc, kill_timeout):
                                    self.logger.error(
                                        f"強制殺掉後 {kill_timeout} 秒內仍未退出",
                                        pid=proc.pid
                                    )
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            # 進程可能已經停止
                            self.logger.debug("進程已不存在或無權限", pid=proc.pid, error=str(e))
                        
                        stopped_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # 進程在檢查時已經消失，繼續檢查下一個
                    continue
            
            if stopped_count > 0:
                self.logger.info(f"已停止 {stopped_count} 個 run.py 進程")
                # 等待一下讓進程完全停止
                time.sleep(1)
            else:
                self.logger.debug("沒有發現需要停止的 run.py 進程")
            
            return stopped_count
            
        except Exception as e:
            self.logger.error("停止舊進程時出錯", error=str(e))
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
        """啟動交易機器人"""
        try:
            # 先停止所有舊的run.py進程（防止多個進程同時運行）
            self._stop_old_bot_processes()
            
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

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='交易機器人守護進程管理器')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'], 
                       help='操作: start(啟動), stop(停止), restart(重啟), status(狀態)')
    parser.add_argument('--daemon', '-d', action='store_true', 
                       help='以守護進程方式運行')
    parser.add_argument('--config', '-c', default='config/daemon_config.json',
                       help='配置文件路徑')
    parser.add_argument('--log-dir', default='logs',
                       help='日誌目錄')
    
    args = parser.parse_args()
    
    # 創建守護進程管理器
    daemon = TradingBotDaemon(args.config)
    
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
