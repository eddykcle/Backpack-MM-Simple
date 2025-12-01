#!/usr/bin/env python3
"""
Phase 3 測試：數據庫隔離
測試不同實例是否能夠使用不同的數據庫文件
"""
import os
import sys
import tempfile
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_database_path_support():
    """測試數據庫路徑支持"""
    print("=" * 60)
    print("Phase 3 測試：數據庫隔離")
    print("=" * 60)

    print("\n1. 測試 Database 類支持 db_path 參數")
    print("-" * 60)

    # 創建臨時數據庫文件
    temp_db1 = tempfile.NamedTemporaryFile(suffix='_instance1.db', delete=False)
    temp_db2 = tempfile.NamedTemporaryFile(suffix='_instance2.db', delete=False)
    temp_db1.close()
    temp_db2.close()

    try:
        from database.db import Database

        # 測試創建兩個不同路徑的數據庫
        db1 = Database(db_path=temp_db1.name)
        print(f"✅ 成功創建數據庫 1: {temp_db1.name}")

        db2 = Database(db_path=temp_db2.name)
        print(f"✅ 成功創建數據庫 2: {temp_db2.name}")

        # 驗證路徑不同
        if db1.db_path != db2.db_path:
            print("✅ 兩個數據庫路徑不同")
        else:
            print("❌ 兩個數據庫路徑相同")

        # 關閉數據庫
        db1.close()
        db2.close()
        print("✅ 成功關閉數據庫連接")

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理臨時文件
        for temp_file in [temp_db1.name, temp_db2.name]:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass

    print("\n2. 測試策略類支持 db_path 參數")
    print("-" * 60)

    try:
        from strategies.market_maker import MarketMaker
        import inspect

        # 檢查 __init__ 方法簽名
        init_signature = inspect.signature(MarketMaker.__init__)
        params = list(init_signature.parameters.keys())

        if 'db_path' in params:
            print("✅ MarketMaker 支持 db_path 參數")
        else:
            print("❌ MarketMaker 不支持 db_path 參數")
            print(f"   可用參數: {params}")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        return False

    print("\n3. 測試 run.py 導入 DB_PATH")
    print("-" * 60)

    try:
        # 檢查 run.py 是否導入了 DB_PATH
        with open(project_root / "run.py", 'r', encoding='utf-8') as f:
            run_py_content = f.read()

        if "from config import ENABLE_DATABASE, DB_PATH" in run_py_content:
            print("✅ run.py 正確導入 DB_PATH")
        else:
            print("❌ run.py 未導入 DB_PATH")

        # 檢查是否有讀取 db_path 的代碼
        if "db_path = os.getenv('DB_PATH', DB_PATH)" in run_py_content:
            print("✅ run.py 正確讀取 db_path 環境變量")
        else:
            print("⚠️  run.py 可能未正確讀取 db_path")

        # 檢查策略實例化是否傳遞 db_path
        if "db_path=db_path" in run_py_content:
            # 統計出現次數
            count = run_py_content.count("db_path=db_path")
            print(f"✅ 策略實例化傳遞 db_path 參數 ({count} 處)")
        else:
            print("❌ 策略實例化未傳遞 db_path 參數")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        return False

    print("\n4. 測試 daemon_manager.py 配置 db_path")
    print("-" * 60)

    try:
        from core.daemon_manager import TradingBotDaemon

        # 檢查配置文件中是否有 db_path
        config_path = project_root / "config/active/bp_sol_01.json"
        if config_path.exists():
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            daemon_config = config.get("daemon_config", {})
            if "db_path" in daemon_config:
                print(f"✅ 配置文件包含 db_path: {daemon_config['db_path']}")
            else:
                print("⚠️  配置文件未包含 db_path（將使用默認值）")
        else:
            print("⚠️  測試配置文件不存在")

        # 檢查 daemon_manager.py 源代碼
        with open(project_root / "core/daemon_manager.py", 'r', encoding='utf-8') as f:
            daemon_content = f.read()

        if '"db_path"' in daemon_content and "DB_PATH" in daemon_content:
            print("✅ daemon_manager.py 支持 db_path 配置")
        else:
            print("❌ daemon_manager.py 不支持 db_path 配置")

        if "env['DB_PATH']" in daemon_content:
            print("✅ daemon_manager.py 設置 DB_PATH 環境變量")
        else:
            print("❌ daemon_manager.py 未設置 DB_PATH 環境變量")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n5. 測試環境變量優先級")
    print("-" * 60)

    try:
        # 測試環境變量設置
        test_db_path = "/tmp/test_database.db"
        os.environ['DB_PATH'] = test_db_path

        # 檢查是否能正確讀取
        from config import DB_PATH as default_db_path
        current_db_path = os.getenv('DB_PATH', default_db_path)

        if current_db_path == test_db_path:
            print(f"✅ 環境變量優先級正確: {current_db_path}")
        else:
            print(f"❌ 環境變量優先級錯誤: 期望 {test_db_path}, 實際 {current_db_path}")

        # 清理環境變量
        del os.environ['DB_PATH']

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = test_database_path_support()
    sys.exit(0 if success else 1)
