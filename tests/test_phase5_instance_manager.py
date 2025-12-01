#!/usr/bin/env python3
"""
Phase 5 測試：實例管理工具
測試實例註冊、查詢、清理等功能
"""
import os
import sys
import json
import tempfile
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.instance_manager import InstanceRegistry, InstanceManager
from datetime import datetime


def test_instance_registry():
    """測試實例註冊表功能"""
    print("=" * 60)
    print("Phase 5 測試：實例管理工具")
    print("=" * 60)

    # 創建臨時註冊表文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_registry = f.name

    try:
        registry = InstanceRegistry(temp_registry)

        print("\n1. 測試實例註冊")
        print("-" * 60)

        # 註冊第一個實例
        instance1_info = {
            "config_file": "config/active/bp_sol_01.json",
            "pid": os.getpid(),
            "log_dir": "logs/bp_sol_01",
            "web_port": 5001,
            "started_at": datetime.now().isoformat(),
            "status": "running"
        }

        registry.register("bp_sol_01", instance1_info)
        print("✅ 成功註冊實例 bp_sol_01")

        # 註冊第二個實例
        instance2_info = {
            "config_file": "config/active/bp_eth_02.json",
            "pid": os.getpid() + 1,  # 模擬不同的 PID
            "log_dir": "logs/bp_eth_02",
            "web_port": 5002,
            "started_at": datetime.now().isoformat(),
            "status": "running"
        }

        registry.register("bp_eth_02", instance2_info)
        print("✅ 成功註冊實例 bp_eth_02")

        print("\n2. 測試獲取實例信息")
        print("-" * 60)

        # 獲取實例信息
        info1 = registry.get("bp_sol_01")
        if info1 and info1.get("web_port") == 5001:
            print("✅ 成功獲取 bp_sol_01 信息")
        else:
            print("❌ 獲取 bp_sol_01 信息失敗")

        info2 = registry.get("bp_eth_02")
        if info2 and info2.get("web_port") == 5002:
            print("✅ 成功獲取 bp_eth_02 信息")
        else:
            print("❌ 獲取 bp_eth_02 信息失敗")

        # 獲取不存在的實例
        info_none = registry.get("non_existent")
        if info_none is None:
            print("✅ 正確處理不存在的實例")
        else:
            print("❌ 應該返回 None")

        print("\n3. 測試列出實例")
        print("-" * 60)

        instances = registry.list_instances(include_dead=True)
        if len(instances) == 2:
            print(f"✅ 成功列出 {len(instances)} 個實例")
        else:
            print(f"❌ 預期 2 個實例，實際 {len(instances)} 個")

        for inst in instances:
            print(f"   - {inst['instance_id']}: Port {inst.get('web_port')}")

        print("\n4. 測試更新實例")
        print("-" * 60)

        # 更新實例狀態
        update_success = registry.update("bp_sol_01", {"status": "stopped"})
        if update_success:
            print("✅ 成功更新實例狀態")

            # 驗證更新
            updated_info = registry.get("bp_sol_01")
            if updated_info and updated_info.get("status") == "stopped":
                print("✅ 狀態更新正確")
            else:
                print("❌ 狀態更新失敗")
        else:
            print("❌ 更新實例失敗")

        print("\n5. 測試按端口查找實例")
        print("-" * 60)

        instance_by_port = registry.get_instance_by_port(5001)
        if instance_by_port and instance_by_port['instance_id'] == 'bp_sol_01':
            print("✅ 成功按端口查找實例")
        else:
            print("❌ 按端口查找失敗")

        print("\n6. 測試實例計數")
        print("-" * 60)

        total_count = registry.count_instances(alive_only=False)
        if total_count == 2:
            print(f"✅ 總實例數正確: {total_count}")
        else:
            print(f"❌ 總實例數錯誤: 預期 2，實際 {total_count}")

        print("\n7. 測試註銷實例")
        print("-" * 60)

        # 註銷一個實例
        unregister_success = registry.unregister("bp_eth_02")
        if unregister_success:
            print("✅ 成功註銷實例 bp_eth_02")

            # 驗證註銷
            remaining = registry.list_instances(include_dead=True)
            if len(remaining) == 1 and remaining[0]['instance_id'] == 'bp_sol_01':
                print("✅ 註銷後實例列表正確")
            else:
                print("❌ 註銷後實例列表錯誤")
        else:
            print("❌ 註銷實例失敗")

        print("\n8. 測試實例管理器")
        print("-" * 60)

        manager = InstanceManager()
        manager.registry = registry  # 使用測試註冊表

        # 獲取實例統計
        stats = manager.get_instance_stats("bp_sol_01")
        if stats:
            print("✅ 成功獲取實例統計信息")
            print(f"   - 實例ID: {stats.get('instance_id')}")
            print(f"   - 存活狀態: {stats.get('is_alive')}")
        else:
            print("❌ 獲取實例統計失敗")

        # 驗證配置
        validation = manager.validate_instance_config("bp_sol_01")
        if validation:
            print("✅ 成功驗證實例配置")
            print(f"   - 有效: {validation.get('valid')}")
            if validation.get('errors'):
                print(f"   - 錯誤: {validation.get('errors')}")
            if validation.get('warnings'):
                print(f"   - 警告: {validation.get('warnings')}")
        else:
            print("❌ 驗證實例配置失敗")

        print("\n9. 測試持久化")
        print("-" * 60)

        # 創建新的註冊表實例，測試是否能加載之前保存的數據
        registry2 = InstanceRegistry(temp_registry)
        loaded_instances = registry2.list_instances(include_dead=True)

        if len(loaded_instances) == 1 and loaded_instances[0]['instance_id'] == 'bp_sol_01':
            print("✅ 成功從文件加載註冊表")
        else:
            print("❌ 從文件加載註冊表失敗")

        print("\n" + "=" * 60)
        print("測試完成")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理臨時文件
        try:
            if os.path.exists(temp_registry):
                os.unlink(temp_registry)
        except:
            pass


if __name__ == "__main__":
    success1 = test_instance_registry()
    sys.exit(0 if success1 else 1)
