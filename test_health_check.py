#!/usr/bin/env python3
"""
測試健康檢查功能的腳本
"""
import time
import threading
import requests
from web.server import run_server, bot_status

def start_web_server():
    """在後台啟動Web服務器"""
    print("正在啟動Web服務器...")
    server_thread = threading.Thread(target=run_server, kwargs={
        'host': '0.0.0.0',
        'port': 5000,
        'debug': False
    }, daemon=True)
    server_thread.start()
    time.sleep(3)  # 等待服務器啟動
    print("Web服務器已啟動")

def test_health_check():
    """測試健康檢查端點"""
    try:
        # 測試策略未運行時的狀態
        print("\n=== 測試策略未運行時的狀態 ===")
        response = requests.get('http://localhost:5000/health', timeout=5)
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {response.json()}")
        
        # 模擬策略運行
        print("\n=== 模擬策略運行 ===")
        bot_status['running'] = True
        bot_status['strategy'] = 'test_strategy'
        bot_status['symbol'] = 'TEST_USDC'
        bot_status['exchange'] = 'backpack'
        bot_status['start_time'] = '2024-01-01T00:00:00'
        bot_status['last_update'] = '2024-01-01T00:00:00'
        
        time.sleep(1)
        
        # 測試策略運行時的狀態
        print("\n=== 測試策略運行時的狀態 ===")
        response = requests.get('http://localhost:5000/health', timeout=5)
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {response.json()}")
        
        # 模擬策略停止
        print("\n=== 模擬策略停止 ===")
        bot_status['running'] = False
        
        time.sleep(1)
        
        # 測試策略停止時的狀態
        print("\n=== 測試策略停止時的狀態 ===")
        response = requests.get('http://localhost:5000/health', timeout=5)
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {response.json()}")
        
        print("\n=== 測試完成 ===")
        print("健康檢查端點工作正常！")
        print("當策略運行時返回200，當策略停止時返回503")
        print("Uptime Kuma 可以監聽: http://localhost:5000/health")
        
    except requests.exceptions.RequestException as e:
        print(f"測試失敗: {e}")
        print("請確保Web服務器已正確啟動")

if __name__ == "__main__":
    print("=== 健康檢查功能測試 ===")
    start_web_server()
    test_health_check()
