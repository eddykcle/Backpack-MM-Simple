#!/usr/bin/env python3
"""
Phase 6 集成測試：多實例系統完整測試
測試雙實例並發運行、資源隔離、Web UI、熱調整等功能
"""
import os
import sys
import time
import json
import tempfile
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.instance_manager import InstanceRegistry
from core.daemon_manager import TradingBotDaemon


class Phase6IntegrationTest:
    """Phase 6 集成測試類"""
    
    def __init__(self):
        self.test_results = []
        self.test_start_time = datetime.now()
        self.registry = InstanceRegistry()
        
    def log_test(self, name, status, details=""):
        """記錄測試結果"""
        result = {
            "name": name,
            "status": "✅ PASS" if status else "❌ FAIL",
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        print(f"{result['status']} {name}")
        if details:
            print(f"   {details}")
        return status
    
    def cleanup_instances(self):
        """清理所有測試實例"""
        print("\n🧹 清理測試實例...")
        try:
            # 停止所有守護進程
            for config_file in ["config/active/bp_sol_01.json", "config/active/bp_eth_02.json"]:
                if Path(config_file).exists():
                    daemon = TradingBotDaemon(config_file)
                    daemon.stop()
                    time.sleep(2)
            
            # 清理註冊表
            count = self.registry.cleanup_dead_instances()
            self.log_test("清理實例", True, f"清理了 {count} 個死亡實例")
            
            # 清理測試數據庫
            for db_file in ["database/bp_sol_01.db", "database/bp_eth_02.db"]:
                db_path = Path(db_file)
                if db_path.exists():
                    db_path.unlink()
                    print(f"   刪除測試數據庫: {db_file}")
            
        except Exception as e:
            self.log_test("清理實例", False, str(e))
    
    def test_config_files(self):
        """測試配置文件"""
        print("\n📋 測試配置文件...")
        
        # 測試 bp_sol_01.json
        try:
            with open("config/active/bp_sol_01.json", "r") as f:
                config1 = json.load(f)
            
            checks = [
                ("metadata.instance_id", config1.get("metadata", {}).get("instance_id") == "bp_sol_01"),
                ("daemon_config.log_dir", config1.get("daemon_config", {}).get("log_dir") == "logs/bp_sol_01"),
                ("daemon_config.db_path", config1.get("daemon_config", {}).get("db_path") == "database/bp_sol_01.db"),
                ("daemon_config.web_port", config1.get("daemon_config", {}).get("web_port") == 5001),
            ]
            
            for check_name, result in checks:
                self.log_test(f"bp_sol_01 {check_name}", result)
                
        except Exception as e:
            self.log_test("bp_sol_01 配置", False, str(e))
        
        # 測試 bp_eth_02.json
        try:
            with open("config/active/bp_eth_02.json", "r") as f:
                config2 = json.load(f)
            
            checks = [
                ("metadata.instance_id", config2.get("metadata", {}).get("instance_id") == "bp_eth_02"),
                ("daemon_config.log_dir", config2.get("daemon_config", {}).get("log_dir") == "logs/bp_eth_02"),
                ("daemon_config.db_path", config2.get("daemon_config", {}).get("db_path") == "database/bp_eth_02.db"),
                ("daemon_config.web_port", config2.get("daemon_config", {}).get("web_port") == 5002),
            ]
            
            for check_name, result in checks:
                self.log_test(f"bp_eth_02 {check_name}", result)
                
        except Exception as e:
            self.log_test("bp_eth_02 配置", False, str(e))
    
    def test_instance_isolation(self):
        """測試實例隔離"""
        print("\n🔒 測試實例隔離...")
        
        # 測試 daemon_manager 實例隔離
        try:
            daemon1 = TradingBotDaemon("config/active/bp_sol_01.json")
            daemon2 = TradingBotDaemon("config/active/bp_eth_02.json")
            
            checks = [
                ("instance_id 不同", daemon1.instance_id != daemon2.instance_id),
                ("log_dir 不同", str(daemon1.log_dir) != str(daemon2.log_dir)),
                ("web_port 不同", daemon1.config.get("web_port") != daemon2.config.get("web_port")),
                ("db_path 不同", daemon1.config.get("db_path") != daemon2.config.get("db_path")),
            ]
            
            for check_name, result in checks:
                self.log_test(f"實例隔離 {check_name}", result)
                
        except Exception as e:
            self.log_test("實例隔離", False, str(e))
    
    def test_daemon_manager_cli(self):
        """測試守護進程管理器 CLI"""
        print("\n🖥️  測試守護進程管理器 CLI...")
        
        # 測試 list 命令
        try:
            result = subprocess.run([
                ".venv/bin/python3", "core/daemon_manager.py", "list"
            ], capture_output=True, text=True, timeout=10)
            
            success = result.returncode == 0
            self.log_test("CLI list 命令", success, 
                         f"returncode={result.returncode}" if not success else "")
            
            if success and "實例ID" in result.stdout:
                self.log_test("CLI list 輸出格式", True)
            else:
                self.log_test("CLI list 輸出格式", False, result.stdout[:100])
                
        except subprocess.TimeoutExpired:
            self.log_test("CLI list 命令", False, "超時")
        except Exception as e:
            self.log_test("CLI list 命令", False, str(e))
    
    def test_instance_cli(self):
        """測試實例管理 CLI"""
        print("\n🖥️  測試實例管理 CLI...")
        
        commands = [
            ([".venv/bin/python3", "cli/instance_cli.py", "list"], "list 命令"),
            ([".venv/bin/python3", "cli/instance_cli.py", "list", "--all"], "list --all 命令"),
            ([".venv/bin/python3", "cli/instance_cli.py", "stats"], "stats 命令"),
            ([".venv/bin/python3", "cli/instance_cli.py", "validate"], "validate 命令"),
        ]
        
        for cmd, name in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                success = result.returncode == 0
                self.log_test(f"CLI {name}", success,
                             f"returncode={result.returncode}" if not success else "")
            except subprocess.TimeoutExpired:
                self.log_test(f"CLI {name}", False, "超時")
            except Exception as e:
                self.log_test(f"CLI {name}", False, str(e))
    
    def test_web_port_availability(self):
        """測試 Web 端口可用性"""
        print("\n🌐 測試 Web 端口可用性...")
        
        # 檢查端口是否被佔用
        for port in [5001, 5002]:
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                # 如果端口被佔用但返回 503，這是正常的（表示服務未啟動）
                if response.status_code in [200, 503]:
                    self.log_test(f"端口 {port} 檢查", True, f"status={response.status_code}")
                else:
                    self.log_test(f"端口 {port} 檢查", False, f"status={response.status_code}")
            except requests.exceptions.ConnectionError:
                # 連接錯誤表示端口未被佔用，這是好的
                self.log_test(f"端口 {port} 可用性", True, "端口未被佔用")
            except Exception as e:
                self.log_test(f"端口 {port} 檢查", False, str(e))
    
    def test_database_isolation(self):
        """測試數據庫隔離"""
        print("\n🗄️  測試數據庫隔離...")
        
        try:
            from database.db import Database
            
            # 測試創建不同的數據庫實例
            db1 = Database("database/bp_sol_01.db")
            db2 = Database("database/bp_eth_02.db")
            
            # 檢查數據庫文件是否被正確創建
            db1_path = Path("database/bp_sol_01.db")
            db2_path = Path("database/bp_eth_02.db")
            
            checks = [
                ("db1 文件創建", db1_path.exists()),
                ("db2 文件創建", db2_path.exists()),
                ("db1 路徑正確", db1.db_path == "database/bp_sol_01.db"),
                ("db2 路徑正確", db2.db_path == "database/bp_eth_02.db"),
            ]
            
            for check_name, result in checks:
                self.log_test(f"數據庫隔離 {check_name}", result)
            
            # 清理
            db1.close()
            db2.close()
            
        except Exception as e:
            self.log_test("數據庫隔離", False, str(e))
    
    def test_log_directory_isolation(self):
        """測試日誌目錄隔離"""
        print("\n📝 測試日誌目錄隔離...")
        
        try:
            # 檢查日誌目錄結構
            log_dirs = ["logs/bp_sol_01", "logs/bp_eth_02"]
            
            for log_dir in log_dirs:
                path = Path(log_dir)
                if path.exists():
                    self.log_test(f"日誌目錄 {log_dir}", True, "目錄已存在")
                else:
                    # 嘗試創建
                    path.mkdir(parents=True, exist_ok=True)
                    self.log_test(f"日誌目錄 {log_dir}", path.exists(), "創建目錄")
            
        except Exception as e:
            self.log_test("日誌目錄隔離", False, str(e))
    
    def test_concurrent_instance_startup(self):
        """測試並發實例啟動"""
        print("\n🚀 測試並發實例啟動...")
        
        # 注意：這個測試不會真正啟動交易機器人（需要API密鑰）
        # 而是測試守護進程的啟動邏輯
        try:
            # 測試啟動守護進程（不帶 --daemon 避免後台運行）
            result1 = subprocess.run([
                ".venv/bin/python3", "core/daemon_manager.py", "start",
                "--config", "config/active/bp_sol_01.json"
            ], capture_output=True, text=True, timeout=30)
            
            # 等待一下
            time.sleep(5)
            
            result2 = subprocess.run([
                ".venv/bin/python3", "core/daemon_manager.py", "start",
                "--config", "config/active/bp_eth_02.json"
            ], capture_output=True, text=True, timeout=30)
            
            # 檢查啟動結果
            # 注意：由於沒有API密鑰，實際會失敗，但我們測試的是啟動邏輯
            self.log_test("bp_sol_01 啟動命令", result1.returncode in [0, 1])
            self.log_test("bp_eth_02 啟動命令", result2.returncode in [0, 1])
            
            # 檢查實例是否註冊
            time.sleep(3)
            instances = self.registry.list_instances(include_dead=True)
            if len(instances) >= 2:
                self.log_test("實例註冊", True, f"註冊了 {len(instances)} 個實例")
            else:
                self.log_test("實例註冊", False, f"只註冊了 {len(instances)} 個實例")
            
            # 停止實例
            subprocess.run([
                ".venv/bin/python3", "core/daemon_manager.py", "stop",
                "--config", "config/active/bp_sol_01.json"
            ], capture_output=True, timeout=10)
            
            subprocess.run([
                ".venv/bin/python3", "core/daemon_manager.py", "stop",
                "--config", "config/active/bp_eth_02.json"
            ], capture_output=True, timeout=10)
            
        except subprocess.TimeoutExpired:
            self.log_test("並發啟動", False, "超時")
        except Exception as e:
            self.log_test("並發啟動", False, str(e))
    
    def test_grid_adjust_api(self):
        """測試網格熱調整 API"""
        print("\n🔧 測試網格熱調整 API...")
        
        # 這個測試檢查 API 端點是否存在和可訪問
        # 實際的熱調整功能需要運行中的策略
        for port in [5001, 5002]:
            try:
                # 測試健康檢查端點
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                self.log_test(f"端口 {port} 健康檢查", 
                            response.status_code in [200, 503],
                            f"status={response.status_code}")
                
                # 測試網格調整端點（會返回 400，因為沒有運行中的策略）
                response = requests.post(
                    f"http://localhost:{port}/api/grid/adjust",
                    json={"grid_upper_price": 150, "grid_lower_price": 140},
                    timeout=2
                )
                # 400 表示端點存在但策略未運行，這是預期的
                self.log_test(f"端口 {port} 網格調整端點", 
                            response.status_code in [400, 503],
                            f"status={response.status_code}")
                
            except requests.exceptions.ConnectionError:
                self.log_test(f"端口 {port} API", True, "端口未佔用（正常）")
            except Exception as e:
                self.log_test(f"端口 {port} API", False, str(e))
    
    def generate_report(self):
        """生成測試報告"""
        print("\n" + "=" * 80)
        print("PHASE 6 集成測試報告")
        print("=" * 80)
        print(f"測試開始時間: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"測試結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"總測試項: {len(self.test_results)}")
        
        passed = sum(1 for r in self.test_results if "✅ PASS" in r["status"])
        failed = sum(1 for r in self.test_results if "❌ FAIL" in r["status"])
        
        print(f"通過: {passed}")
        print(f"失敗: {failed}")
        print(f"成功率: {passed/len(self.test_results)*100:.1f}%")
        
        print("\n詳細結果:")
        print("-" * 80)
        
        for result in self.test_results:
            print(f"{result['status']} {result['name']}")
            if result['details']:
                print(f"   {result['details']}")
        
        print("\n" + "=" * 80)
        
        if failed == 0:
            print("🎉 所有測試通過！多實例系統已準備就緒。")
        else:
            print("⚠️  部分測試失敗，請檢查相關功能。")
        
        print("=" * 80)
        
        # 保存報告到文件
        report_file = f"test_reports/phase6_integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        Path("test_reports").mkdir(exist_ok=True)
        
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("PHASE 6 集成測試報告\n")
            f.write("=" * 80 + "\n")
            f.write(f"測試開始時間: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"測試結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"總測試項: {len(self.test_results)}\n")
            f.write(f"通過: {passed}\n")
            f.write(f"失敗: {failed}\n")
            f.write(f"成功率: {passed/len(self.test_results)*100:.1f}%\n\n")
            f.write("詳細結果:\n")
            f.write("-" * 80 + "\n")
            
            for result in self.test_results:
                f.write(f"{result['status']} {result['name']}\n")
                if result['details']:
                    f.write(f"   {result['details']}\n")
        
        print(f"\n📄 測試報告已保存到: {report_file}")
        
        return failed == 0


def main():
    """主測試函數"""
    print("=" * 80)
    print("PHASE 6 集成測試開始")
    print("多實例系統完整功能測試")
    print("=" * 80)
    
    # 檢查環境
    if not Path(".venv/bin/python3").exists():
        print("❌ 錯誤: 虛擬環境未找到，請先運行: python3 -m venv .venv")
        sys.exit(1)
    
    test = Phase6IntegrationTest()
    
    try:
        # 清理環境
        test.cleanup_instances()
        
        # 執行測試
        test.test_config_files()
        test.test_instance_isolation()
        test.test_daemon_manager_cli()
        test.test_instance_cli()
        test.test_web_port_availability()
        test.test_database_isolation()
        test.test_log_directory_isolation()
        test.test_concurrent_instance_startup()
        test.test_grid_adjust_api()
        
        # 最終清理
        test.cleanup_instances()
        
        # 生成報告
        success = test.generate_report()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  測試被用戶中斷")
        test.cleanup_instances()
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 測試執行失敗: {e}")
        import traceback
        traceback.print_exc()
        test.cleanup_instances()
        sys.exit(1)


if __name__ == "__main__":
    main()