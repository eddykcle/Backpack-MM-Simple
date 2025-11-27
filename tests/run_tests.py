#!/usr/bin/env python3
"""
測試運行腳本
提供便捷的測試執行和報告功能
"""
import sys
import os
import unittest
import time
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_config_manager_tests():
    """運行配置管理器測試"""
    print("=" * 60)
    print("運行配置管理器測試")
    print("=" * 60)
    
    # 導入測試模塊
    from tests.test_config_manager import TestConfigManager
    
    # 創建測試套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestConfigManager)
    
    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_all_tests():
    """運行所有測試"""
    print("=" * 60)
    print("運行所有測試")
    print("=" * 60)
    
    # 發現並運行所有測試
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def generate_test_report():
    """生成測試報告"""
    print("=" * 60)
    print("生成測試報告")
    print("=" * 60)
    
    # 創建報告目錄
    report_dir = Path(__file__).parent.parent / "test_reports"
    report_dir.mkdir(exist_ok=True)
    
    # 生成報告文件名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = report_dir / f"test_report_{timestamp}.txt"
    
    # 運行測試並捕獲輸出
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            success = run_all_tests()
        
        # 寫入報告文件
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"測試報告 - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            f.write("標準輸出:\n")
            f.write("-" * 40 + "\n")
            f.write(stdout_capture.getvalue())
            f.write("\n")
            
            if stderr_capture.getvalue():
                f.write("錯誤輸出:\n")
                f.write("-" * 40 + "\n")
                f.write(stderr_capture.getvalue())
                f.write("\n")
            
            f.write(f"\n測試結果: {'通過' if success else '失敗'}\n")
        
        print(f"測試報告已生成: {report_file}")
        return success
        
    except Exception as e:
        print(f"生成測試報告失敗: {e}")
        return False


def main():
    """主函數"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python run_tests.py config     - 運行配置管理器測試")
        print("  python run_tests.py all         - 運行所有測試")
        print("  python run_tests.py report      - 生成測試報告")
        return 1
    
    command = sys.argv[1].lower()
    
    start_time = time.time()
    
    try:
        if command == "config":
            success = run_config_manager_tests()
        elif command == "all":
            success = run_all_tests()
        elif command == "report":
            success = generate_test_report()
        else:
            print(f"未知命令: {command}")
            return 1
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "=" * 60)
        print(f"測試完成，耗時: {duration:.2f} 秒")
        print(f"結果: {'通過' if success else '失敗'}")
        print("=" * 60)
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"運行測試時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())