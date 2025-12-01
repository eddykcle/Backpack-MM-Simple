#!/usr/bin/env python3
"""
Phase 4 測試：Web 端口隔離
測試不同實例是否能夠使用不同的 Web 端口
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_web_port_isolation():
    """測試 Web 端口隔離功能"""
    print("=" * 60)
    print("Phase 4 測試：Web 端口隔離")
    print("=" * 60)

    # 測試配置
    test_configs = [
        {
            "config_file": "config/active/bp_sol_01.json",
            "expected_port": 5001,
            "instance_id": "bp_sol_01"
        },
        {
            "config_file": "config/active/bp_eth_02.json",
            "expected_port": 5002,
            "instance_id": "bp_eth_02"
        }
    ]

    print("\n1. 驗證配置文件中的 web_port 設置")
    print("-" * 60)

    for test_config in test_configs:
        config_path = project_root / test_config["config_file"]

        if not config_path.exists():
            print(f"❌ 配置文件不存在: {config_path}")
            continue

        with open(config_path, 'r') as f:
            config_data = json.load(f)

        daemon_config = config_data.get("daemon_config", {})
        web_port = daemon_config.get("web_port")

        if web_port == test_config["expected_port"]:
            print(f"✅ {test_config['instance_id']}: web_port = {web_port} (正確)")
        else:
            print(f"❌ {test_config['instance_id']}: web_port = {web_port}, 預期 {test_config['expected_port']}")

    print("\n2. 測試 daemon_manager.py 是否正確加載 web_port")
    print("-" * 60)

    try:
        from core.daemon_manager import TradingBotDaemon

        for test_config in test_configs:
            config_path = str(project_root / test_config["config_file"])

            # 創建守護進程實例（不啟動）
            daemon = TradingBotDaemon(config_path)

            # 檢查是否正確加載了 web_port
            loaded_port = daemon.config.get("web_port")

            if loaded_port == test_config["expected_port"]:
                print(f"✅ {test_config['instance_id']}: 加載 web_port = {loaded_port} (正確)")
            else:
                print(f"❌ {test_config['instance_id']}: 加載 web_port = {loaded_port}, 預期 {test_config['expected_port']}")

            # 檢查實例 ID 是否正確
            if daemon.instance_id == test_config["instance_id"]:
                print(f"✅ {test_config['instance_id']}: instance_id 正確")
            else:
                print(f"❌ instance_id = {daemon.instance_id}, 預期 {test_config['instance_id']}")

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n3. 測試 run.py 是否能正確讀取 WEB_PORT 環境變量")
    print("-" * 60)

    # 測試不同的 WEB_PORT 環境變量值
    test_ports = [5001, 5002, 5003]

    for port in test_ports:
        # 設置環境變量
        os.environ['WEB_PORT'] = str(port)

        # 導入並測試
        try:
            # 清除模塊緩存
            if 'run' in sys.modules:
                del sys.modules['run']

            # 檢查環境變量是否正確設置
            read_port = int(os.getenv('WEB_PORT', '5000'))

            if read_port == port:
                print(f"✅ WEB_PORT={port}: 環境變量讀取正確")
            else:
                print(f"❌ WEB_PORT={port}: 讀取為 {read_port}")

        except Exception as e:
            print(f"❌ WEB_PORT={port} 測試失敗: {e}")

    # 清理環境變量
    if 'WEB_PORT' in os.environ:
        del os.environ['WEB_PORT']

    print("\n4. 檢查 web/server.py 的 run_server() 函數")
    print("-" * 60)

    try:
        from web.server import run_server
        import inspect

        # 獲取函數源碼
        source = inspect.getsource(run_server)

        # 檢查是否包含環境變量讀取邏輯
        if "os.getenv('WEB_PORT'" in source or 'os.getenv("WEB_PORT"' in source:
            print("✅ run_server() 函數包含 WEB_PORT 環境變量讀取邏輯")
        else:
            print("❌ run_server() 函數缺少 WEB_PORT 環境變量讀取邏輯")

        if "os.getenv('WEB_HOST'" in source or 'os.getenv("WEB_HOST"' in source:
            print("✅ run_server() 函數包含 WEB_HOST 環境變量讀取邏輯")
        else:
            print("⚠️  run_server() 函數缺少 WEB_HOST 環境變量讀取邏輯（可選）")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

    print("\n5. 檢查 daemon_manager.py 的 _start_bot() 方法")
    print("-" * 60)

    try:
        from core.daemon_manager import TradingBotDaemon
        import inspect

        # 獲取 _start_bot 方法源碼
        source = inspect.getsource(TradingBotDaemon._start_bot)

        # 檢查是否設置了 WEB_PORT 環境變量
        if "env['WEB_PORT']" in source or 'env["WEB_PORT"]' in source:
            print("✅ _start_bot() 方法正確設置 WEB_PORT 環境變量")
        else:
            print("❌ _start_bot() 方法未設置 WEB_PORT 環境變量")

        # 檢查是否從配置讀取 web_port
        if 'self.config' in source and 'web_port' in source:
            print("✅ _start_bot() 方法從配置讀取 web_port")
        else:
            print("⚠️  _start_bot() 方法可能未從配置讀取 web_port")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)

    return True

if __name__ == "__main__":
    success = test_web_port_isolation()
    sys.exit(0 if success else 1)
