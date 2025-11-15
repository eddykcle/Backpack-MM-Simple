"""
監控和告警系統
提供系統監控、性能監控、告警通知等功能
"""
import os
import sys
import time
import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import threading
import psutil
from dataclasses import dataclass
from enum import Enum

from core.log_manager import get_logger

class AlertLevel(Enum):
    """告警級別"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertType(Enum):
    """告警類型"""
    SYSTEM_RESOURCE = "system_resource"
    PROCESS_STATUS = "process_status"
    TRADING_ERROR = "trading_error"
    NETWORK_ERROR = "network_error"
    PERFORMANCE = "performance"
    CUSTOM = "custom"

@dataclass
class Alert:
    """告警信息"""
    level: AlertLevel
    alert_type: AlertType
    title: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    acknowledged: bool = False

class NotificationManager:
    """通知管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger("notification_manager")
    
    def send_email(self, alert: Alert, recipients: List[str]) -> bool:
        """發送郵件通知"""
        try:
            if not self.config.get('email', {}).get('enabled', False):
                return False
            
            email_config = self.config['email']
            
            msg = MIMEMultipart()
            msg['From'] = email_config['sender']
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.title}"
            
            # 構建郵件內容
            body = f"""
交易機器人告警通知

級別: {alert.level.value.upper()}
類型: {alert.alert_type.value}
時間: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}

詳細信息:
{json.dumps(alert.details, indent=2, ensure_ascii=False)}

---
這是自動發送的告警郵件，請勿回覆。
"""
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 發送郵件
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
            
            self.logger.info("郵件通知已發送", 
                           recipients=recipients, 
                           alert_title=alert.title)
            return True
            
        except Exception as e:
            self.logger.error("發送郵件失敗", error=str(e))
            return False
    
    def send_telegram(self, alert: Alert, chat_ids: List[str]) -> bool:
        """發送Telegram通知"""
        try:
            if not self.config.get('telegram', {}).get('enabled', False):
                return False
            
            telegram_config = self.config['telegram']
            bot_token = telegram_config['bot_token']
            
            # 構建消息
            emoji_map = {
                AlertLevel.INFO: "ℹ️",
                AlertLevel.WARNING: "⚠️",
                AlertLevel.ERROR: "❌",
                AlertLevel.CRITICAL: "🚨"
            }
            
            message = f"""
{emoji_map.get(alert.level, "📊")} <b>{alert.title}</b>

<b>級別:</b> {alert.level.value.upper()}
<b>類型:</b> {alert.alert_type.value}
<b>時間:</b> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}

<pre>{json.dumps(alert.details, indent=2, ensure_ascii=False)}</pre>
"""
            
            # 發送到所有指定的chat_id
            for chat_id in chat_ids:
                try:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    data = {
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                    
                    response = requests.post(url, data=data, timeout=10)
                    if response.status_code != 200:
                        self.logger.warning("Telegram消息發送失敗", 
                                          chat_id=chat_id,
                                          status_code=response.status_code)
                    
                except Exception as e:
                    self.logger.error("發送Telegram消息失敗", 
                                    chat_id=chat_id, 
                                    error=str(e))
            
            self.logger.info("Telegram通知已發送", 
                           chat_ids_count=len(chat_ids),
                           alert_title=alert.title)
            return True
            
        except Exception as e:
            self.logger.error("發送Telegram通知失敗", error=str(e))
            return False
    
    def send_webhook(self, alert: Alert, webhook_urls: List[str]) -> bool:
        """發送Webhook通知"""
        try:
            if not webhook_urls:
                return False
            
            # 構建webhook數據
            webhook_data = {
                'alert': {
                    'level': alert.level.value,
                    'type': alert.alert_type.value,
                    'title': alert.title,
                    'message': alert.message,
                    'details': alert.details,
                    'timestamp': alert.timestamp.isoformat()
                },
                'metadata': {
                    'hostname': os.uname().nodename,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            # 發送到所有webhook URL
            for webhook_url in webhook_urls:
                try:
                    response = requests.post(
                        webhook_url,
                        json=webhook_data,
                        timeout=10,
                        headers={'Content-Type': 'application/json'}
                    )
                    
                    if response.status_code not in [200, 201, 202]:
                        self.logger.warning("Webhook發送失敗", 
                                          url=webhook_url,
                                          status_code=response.status_code)
                    
                except Exception as e:
                    self.logger.error("發送Webhook失敗", 
                                    url=webhook_url, 
                                    error=str(e))
            
            self.logger.info("Webhook通知已發送", 
                           webhook_count=len(webhook_urls),
                           alert_title=alert.title)
            return True
            
        except Exception as e:
            self.logger.error("發送Webhook通知失敗", error=str(e))
            return False
    
    def send_notification(self, alert: Alert) -> bool:
        """發送所有類型的通知"""
        success = False
        
        # 發送郵件
        email_recipients = self.config.get('email', {}).get('recipients', [])
        if email_recipients:
            if self.send_email(alert, email_recipients):
                success = True
        
        # 發送Telegram
        telegram_chat_ids = self.config.get('telegram', {}).get('chat_ids', [])
        if telegram_chat_ids:
            if self.send_telegram(alert, telegram_chat_ids):
                success = True
        
        # 發送Webhook
        webhook_urls = self.config.get('webhook', {}).get('urls', [])
        if webhook_urls:
            if self.send_webhook(alert, webhook_urls):
                success = True
        
        return success

class SystemMonitor:
    """系統監控器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger("system_monitor")
        self.notification_manager = NotificationManager(config.get('notifications', {}))
        
        # 監控配置
        self.cpu_threshold = config.get('cpu_threshold', 80)
        self.memory_threshold = config.get('memory_threshold', 80)
        self.disk_threshold = config.get('disk_threshold', 90)
        self.check_interval = config.get('check_interval', 60)
        
        # 告警歷史
        self.alert_history: List[Alert] = []
        self.max_history_size = 1000
        
        # 運行標誌
        self.running = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """開始監控"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("系統監控已啟動")
    
    def stop_monitoring(self):
        """停止監控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("系統監控已停止")
    
    def _monitor_loop(self):
        """監控循環"""
        while self.running:
            try:
                # 檢查系統資源
                self._check_system_resources()
                
                # 檢查進程狀態
                self._check_process_status()
                
                # 檢查網絡連接
                self._check_network_connectivity()
                
                # 等待下一個檢查週期
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error("監控循環錯誤", error=str(e))
                time.sleep(10)
    
    def _check_system_resources(self):
        """檢查系統資源使用情況"""
        try:
            # 檢查CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.cpu_threshold:
                self._create_alert(
                    AlertLevel.WARNING,
                    AlertType.SYSTEM_RESOURCE,
                    "CPU使用率過高",
                    f"CPU使用率達到 {cpu_percent:.1f}%，超過閾值 {self.cpu_threshold}%",
                    {"cpu_percent": cpu_percent, "threshold": self.cpu_threshold}
                )
            
            # 檢查內存使用率
            memory = psutil.virtual_memory()
            if memory.percent > self.memory_threshold:
                self._create_alert(
                    AlertLevel.WARNING,
                    AlertType.SYSTEM_RESOURCE,
                    "內存使用率過高",
                    f"內存使用率達到 {memory.percent:.1f}%，超過閾值 {self.memory_threshold}%",
                    {"memory_percent": memory.percent, "threshold": self.memory_threshold}
                )
            
            # 檢查磁盤使用率
            disk = psutil.disk_usage('/')
            if disk.percent > self.disk_threshold:
                self._create_alert(
                    AlertLevel.ERROR,
                    AlertType.SYSTEM_RESOURCE,
                    "磁盤空間不足",
                    f"磁盤使用率達到 {disk.percent:.1f}%，超過閾值 {self.disk_threshold}%",
                    {"disk_percent": disk.percent, "threshold": self.disk_threshold}
                )
            
            # 檢查系統負載
            load_avg = psutil.getloadavg()
            cpu_count = psutil.cpu_count()
            if load_avg[0] > cpu_count * 2:
                self._create_alert(
                    AlertLevel.WARNING,
                    AlertType.SYSTEM_RESOURCE,
                    "系統負載過高",
                    f"系統負載 {load_avg[0]:.2f} 超過CPU核心數 {cpu_count} 的兩倍",
                    {"load_avg": load_avg, "cpu_count": cpu_count}
                )
                
        except Exception as e:
            self.logger.error("檢查系統資源失敗", error=str(e))
    
    def _check_process_status(self):
        """檢查進程狀態"""
        try:
            # 查找交易機器人進程
            bot_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('run.py' in arg for arg in cmdline):
                        bot_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not bot_processes:
                self._create_alert(
                    AlertLevel.ERROR,
                    AlertType.PROCESS_STATUS,
                    "交易機器人進程未找到",
                    "系統中沒有找到運行中的交易機器人進程",
                    {}
                )
            else:
                # 檢查進程狀態
                for proc in bot_processes:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        self._create_alert(
                            AlertLevel.ERROR,
                            AlertType.PROCESS_STATUS,
                            f"進程變為殭屍進程: {proc.pid}",
                            f"交易機器人進程 {proc.pid} 變為殭屍進程",
                            {"pid": proc.pid, "status": proc.info['status']}
                        )
                    
                    # 檢查進程資源使用
                    try:
                        memory_mb = proc.memory_info().rss / 1024 / 1024
                        cpu_percent = proc.cpu_percent()
                        
                        if memory_mb > 2048:  # 2GB
                            self._create_alert(
                                AlertLevel.WARNING,
                                AlertType.PROCESS_STATUS,
                                f"進程內存使用過高: {proc.pid}",
                                f"進程 {proc.pid} 內存使用 {memory_mb:.1f}MB 超過限制",
                                {"pid": proc.pid, "memory_mb": memory_mb}
                            )
                        
                        if cpu_percent > 80:
                            self._create_alert(
                                AlertLevel.WARNING,
                                AlertType.PROCESS_STATUS,
                                f"進程CPU使用過高: {proc.pid}",
                                f"進程 {proc.pid} CPU使用 {cpu_percent:.1f}% 超過限制",
                                {"pid": proc.pid, "cpu_percent": cpu_percent}
                            )
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                        
        except Exception as e:
            self.logger.error("檢查進程狀態失敗", error=str(e))
    
    def _check_network_connectivity(self):
        """檢查網絡連接"""
        try:
            # 檢查是否能訪問外部網絡
            test_urls = [
                "https://api.backpack.exchange",
                "https://api.aster.exchange",
                "https://api.prod.paradex.trade",
                "https://www.google.com"
            ]
            
            failed_urls = []
            for url in test_urls:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code >= 500:
                        failed_urls.append(f"{url} (HTTP {response.status_code})")
                except Exception:
                    failed_urls.append(url)
            
            if failed_urls:
                self._create_alert(
                    AlertLevel.WARNING,
                    AlertType.NETWORK_ERROR,
                    "網絡連接問題",
                    f"無法連接到以下服務: {', '.join(failed_urls)}",
                    {"failed_urls": failed_urls}
                )
                
        except Exception as e:
            self.logger.error("檢查網絡連接失敗", error=str(e))
    
    def _create_alert(self, level: AlertLevel, alert_type: AlertType, 
                     title: str, message: str, details: Dict[str, Any]):
        """創建告警"""
        alert = Alert(
            level=level,
            alert_type=alert_type,
            title=title,
            message=message,
            details=details,
            timestamp=datetime.now()
        )
        
        # 添加到歷史記錄
        self.alert_history.append(alert)
        
        # 限制歷史記錄大小
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]
        
        # 發送通知
        self.notification_manager.send_notification(alert)
        
        # 記錄到日誌
        self.logger.warning(f"告警創建: {title}", 
                          level=level.value,
                          type=alert_type.value,
                          message=message,
                          details=details)
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """獲取告警歷史"""
        history = []
        for alert in self.alert_history[-limit:]:
            history.append({
                'level': alert.level.value,
                'type': alert.alert_type.value,
                'title': alert.title,
                'message': alert.message,
                'details': alert.details,
                'timestamp': alert.timestamp.isoformat(),
                'acknowledged': alert.acknowledged
            })
        return history
    
    def acknowledge_alert(self, timestamp: str) -> bool:
        """確認告警"""
        for alert in self.alert_history:
            if alert.timestamp.isoformat() == timestamp:
                alert.acknowledged = True
                return True
        return False

class PerformanceMonitor:
    """性能監控器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger("performance_monitor")
        
        # 性能數據存儲
        self.performance_data: List[Dict[str, Any]] = []
        self.max_data_points = 10000
        
        # 監控配置
        self.collect_interval = config.get('collect_interval', 60)
        
        # 運行標誌
        self.running = False
        self.collect_thread = None
    
    def start_monitoring(self):
        """開始性能監控"""
        if self.running:
            return
        
        self.running = True
        self.collect_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.collect_thread.start()
        self.logger.info("性能監控已啟動")
    
    def stop_monitoring(self):
        """停止性能監控"""
        self.running = False
        if self.collect_thread:
            self.collect_thread.join(timeout=5)
        self.logger.info("性能監控已停止")
    
    def _collect_loop(self):
        """收集循環"""
        while self.running:
            try:
                # 收集系統性能數據
                data = self._collect_system_metrics()
                
                # 收集應用性能數據
                app_data = self._collect_app_metrics()
                data.update(app_data)
                
                # 保存數據
                self.performance_data.append(data)
                
                # 限制數據點數量
                if len(self.performance_data) > self.max_data_points:
                    self.performance_data = self.performance_data[-self.max_data_points:]
                
                # 等待下一個收集週期
                time.sleep(self.collect_interval)
                
            except Exception as e:
                self.logger.error("收集性能數據失敗", error=str(e))
                time.sleep(10)
    
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """收集系統指標"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_avg': psutil.getloadavg(),
            'network_io': {
                'bytes_sent': psutil.net_io_counters().bytes_sent,
                'bytes_recv': psutil.net_io_counters().bytes_recv
            }
        }
    
    def _collect_app_metrics(self) -> Dict[str, Any]:
        """收集應用指標"""
        metrics = {}
        
        try:
            # 查找交易機器人進程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('run.py' in arg for arg in cmdline):
                        metrics['bot_process'] = {
                            'pid': proc.pid,
                            'cpu_percent': proc.cpu_percent(),
                            'memory_mb': proc.memory_info().rss / 1024 / 1024,
                            'num_threads': proc.num_threads(),
                            'status': proc.status()
                        }
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            self.logger.error("收集應用指標失敗", error=str(e))
        
        return metrics
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """獲取性能報告"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 篩選指定時間範圍內的數據
        recent_data = [
            data for data in self.performance_data
            if datetime.fromisoformat(data['timestamp']) > cutoff_time
        ]
        
        if not recent_data:
            return {"error": "沒有足夠的性能數據"}
        
        # 計算統計信息
        cpu_values = [data['cpu_percent'] for data in recent_data]
        memory_values = [data['memory_percent'] for data in recent_data]
        disk_values = [data['disk_percent'] for data in recent_data]
        
        report = {
            'period_hours': hours,
            'data_points': len(recent_data),
            'cpu_stats': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory_stats': {
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values)
            },
            'disk_stats': {
                'avg': sum(disk_values) / len(disk_values),
                'max': max(disk_values),
                'min': min(disk_values)
            },
            'latest_data': recent_data[-1] if recent_data else None
        }
        
        # 添加應用性能統計
        bot_cpu_values = []
        bot_memory_values = []
        
        for data in recent_data:
            if 'bot_process' in data:
                bot_cpu_values.append(data['bot_process']['cpu_percent'])
                bot_memory_values.append(data['bot_process']['memory_mb'])
        
        if bot_cpu_values:
            report['bot_performance'] = {
                'cpu_stats': {
                    'avg': sum(bot_cpu_values) / len(bot_cpu_values),
                    'max': max(bot_cpu_values),
                    'min': min(bot_cpu_values)
                },
                'memory_stats': {
                    'avg': sum(bot_memory_values) / len(bot_memory_values),
                    'max': max(bot_memory_values),
                    'min': min(bot_memory_values)
                }
            }
        
        return report

# 全局監控實例
_system_monitor = None
_performance_monitor = None

def get_system_monitor(config: Optional[Dict[str, Any]] = None) -> SystemMonitor:
    """獲取系統監控器實例"""
    global _system_monitor
    if _system_monitor is None and config:
        _system_monitor = SystemMonitor(config)
    return _system_monitor

def get_performance_monitor(config: Optional[Dict[str, Any]] = None) -> PerformanceMonitor:
    """獲取性能監控器實例"""
    global _performance_monitor
    if _performance_monitor is None and config:
        _performance_monitor = PerformanceMonitor(config)
    return _performance_monitor

if __name__ == "__main__":
    # 測試監控系統
    config = {
        'cpu_threshold': 80,
        'memory_threshold': 80,
        'disk_threshold': 90,
        'check_interval': 10,
        'notifications': {
            'email': {
                'enabled': False,
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': 'your-email@gmail.com',
                'password': 'your-password',
                'sender': 'your-email@gmail.com',
                'recipients': ['recipient@example.com']
            },
            'telegram': {
                'enabled': False,
                'bot_token': 'your-bot-token',
                'chat_ids': ['your-chat-id']
            },
            'webhook': {
                'urls': []
            }
        }
    }
    
    monitor = SystemMonitor(config)
    monitor.start_monitoring()
    
    print("監控系統已啟動，按 Ctrl+C 停止...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop_monitoring()
        print("監控系統已停止")
