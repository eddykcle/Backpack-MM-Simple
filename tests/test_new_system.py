"""
測試新的日誌和監控系統
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path

# 添加當前目錄到Python路徑
sys.path.insert(0, str(Path.cwd()))

from core.log_manager import get_logger, cleanup_old_logs
from core.daemon_manager import TradingBotDaemon
from monitoring import SystemMonitor, PerformanceMonitor

def test_log_manager():
    """測試日誌管理器"""
    print("=== 測試日誌管理器 ===")
    
    # 創建日誌記錄器
    logger = get_logger("test_logger")
    
    # 測試不同級別的日誌
    logger.info("這是一條信息日誌")
    logger.warning("這是一條警告日誌", user_id="test_user", component="test")
    logger.error("這是一條錯誤日誌", error_code="E001", details={"field": "value"})
    logger.debug("這是一條調試日誌", debug_info={"variable": "test"})
    
    # 測試結構化日誌
    logger.log_structured("INFO", "結構化日誌測試", {
        "event": "test_event",
        "data": {"key": "value", "number": 123},
        "user": {"id": "user123", "name": "測試用戶"}
    })
    
    print("日誌測試完成，請查看 logs/ 目錄")
    print(f"日誌文件: {list(Path('logs').glob('*.log'))}")
    return True

def test_daemon_manager():
    """測試守護進程管理器"""
    print("\n=== 測試守護進程管理器 ===")
    
    # 創建守護進程管理器
    daemon = TradingBotDaemon("tests/test_daemon_config.json")
    
    # 測試狀態檢查
    status = daemon.status()
    print(f"當前狀態: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    # 測試配置文件
    print(f"配置文件路徑: {daemon.config_file}")
    print(f"日誌目錄: {daemon.log_dir}")
    
    return True

def test_monitoring():
    """測試監控系統"""
    print("\n=== 測試監控系統 ===")
    
    # 創建監控配置
    config = {
        'cpu_threshold': 90,
        'memory_threshold': 90,
        'disk_threshold': 95,
        'check_interval': 30,
        'notifications': {
            'email': {'enabled': False},
            'telegram': {'enabled': False},
            'webhook': {'urls': []}
        }
    }
    
    # 創建系統監控器
    monitor = SystemMonitor(config)
    
    # 測試手動觸發告警
    monitor._create_alert(
        AlertLevel.WARNING,
        AlertType.CUSTOM,
        "測試告警",
        "這是一個測試告警",
        {"test": True, "component": "monitoring_system"}
    )
    
    # 獲取告警歷史
    history = monitor.get_alert_history(10)
    print(f"告警歷史: {json.dumps(history, indent=2, ensure_ascii=False)}")
    
    # 創建性能監控器
    perf_monitor = PerformanceMonitor(config)
    
    # 測試性能報告
    report = perf_monitor.get_performance_report(1)  # 最近1小時
    print(f"性能報告: {json.dumps(report, indent=2, ensure_ascii=False)}")
    
    return True

def test_integration():
    """測試系統集成"""
    print("\n=== 測試系統集成 ===")
    
    # 測試日誌和監控的集成
    logger = get_logger("integration_test")
    
    # 創建監控配置
    config = {
        'cpu_threshold': 80,
        'memory_threshold': 80,
        'disk_threshold': 90,
        'check_interval': 60,
        'notifications': {
            'email': {'enabled': False},
            'telegram': {'enabled': False},
            'webhook': {'urls': []}
        }
    }
    
    # 啟動監控
    monitor = SystemMonitor(config)
    monitor.start_monitoring()
    
    # 記錄集成測試開始
    logger.info("集成測試開始", test_type="integration")
    
    # 模擬一些系統活動
    print("模擬系統活動...")
    
    # 創建一些CPU負載
    start_time = time.time()
    while time.time() - start_time < 2:  # 2秒
        _ = [i**2 for i in range(1000)]
    
    # 記錄活動
    logger.info("CPU負載測試完成", duration=2)
    
    # 停止監控
    monitor.stop_monitoring()
    
    # 獲取最終的告警歷史
    final_history = monitor.get_alert_history(10)
    print(f"最終告警歷史記錄數: {len(final_history)}")
    
    logger.info("集成測試完成")
    return True

def test_file_cleanup():
    """測試日誌清理功能"""
    print("\n=== 測試日誌清理 ===")
    
    # 創建一些測試日誌文件
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # 創建舊的日誌文件
    old_log = logs_dir / "old_test.log"
    old_log.write_text("這是一個舊的測試日誌文件")
    
    # 修改文件時間為30天前
    old_time = time.time() - (30 * 24 * 60 * 60)  # 30天前
    os.utime(old_log, (old_time, old_time))
    
    print(f"清理前日誌文件: {list(logs_dir.glob('*.log'))}")
    
    # 執行清理
    cleanup_old_logs("logs", days_to_keep=7)
    
    print(f"清理後日誌文件: {list(logs_dir.glob('*.log'))}")
    
    return True

def create_test_config():
    """創建測試配置文件"""
    test_config = {
        "python_path": sys.executable,
        "script_path": "simple_test.py",
        "working_dir": str(Path.cwd()),
        "log_dir": "logs",
        "max_restart_attempts": 2,
        "restart_delay": 30,
        "health_check_interval": 10,
        "memory_limit_mb": 1024,
        "cpu_limit_percent": 90,
        "auto_restart": False,
        "environment": {},
        "bot_args": ["--test-mode"]
    }
    
    with open("tests/test_daemon_config.json", "w") as f:
        json.dump(test_config, f, indent=2, ensure_ascii=False)
    
    print("測試配置文件已創建: test_daemon_config.json")
    return True

def main():
    """主測試函數"""
    print("開始測試新的日誌和監控系統...")
    
    # 創建測試配置
    create_test_config()
    
    # 運行所有測試
    tests = [
        test_log_manager,
        test_daemon_manager,
        test_monitoring,
        test_integration,
        test_file_cleanup
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✓ {test.__name__} 通過")
            else:
                failed += 1
                print(f"✗ {test.__name__} 失敗")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} 錯誤: {e}")
    
    print(f"\n測試完成: {passed} 通過, {failed} 失敗")
    
    # 清理測試文件
    test_files = ["tests/test_daemon_config.json"]
    for file in test_files:
        Path(file).unlink(missing_ok=True)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
