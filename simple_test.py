#!/usr/bin/env python3
import subprocess
import time
import os
import signal

print("=== 測試健康檢查端點 ===")

# 在後台啟動Web服務器
print("啟動Web服務器...")
server_process = subprocess.Popen([
    'python3', '-c', 
    """
from web.server import run_server
import sys
sys.stdout = sys.stderr  # 重定向輸出
run_server(host='0.0.0.0', port=5000, debug=False)
    """
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

time.sleep(5)  # 等待服務器啟動

try:
    # 測試健康檢查端點
    print("測試健康檢查端點...")
    result = subprocess.run(['curl', '-s', 'http://localhost:5000/health'], 
                          capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0:
        print("✅ 健康檢查端點正常工作！")
        print(f"響應: {result.stdout}")
    else:
        print("❌ 無法連接到健康檢查端點")
        print(f"錯誤: {result.stderr}")
        
    # 測試詳細端點
    print("\n測試詳細狀態端點...")
    result = subprocess.run(['curl', '-s', 'http://localhost:5000/health/detailed'], 
                          capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0:
        print("✅ 詳細狀態端點正常工作！")
        print(f"響應: {result.stdout[:200]}...")  # 只顯示前200字符
    else:
        print("❌ 無法連接到詳細狀態端點")
        
finally:
    # 清理：終止服務器進程
    print("\n清理中...")
    server_process.terminate()
    server_process.wait()
    print("測試完成！")
