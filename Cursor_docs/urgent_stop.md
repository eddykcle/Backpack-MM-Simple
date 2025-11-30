## 強制終止方法

### 方法 1: 使用 CLI 命令（推薦）

```bash
# 1. 先查看所有運行中的實例
.venv/bin/python3 core/daemon_manager.py list

# 2. 停止特定實例（根據 list 結果）
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_sol_01.json
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_eth_02.json
.venv/bin/python3 core/daemon_manager.py stop --config config/active/backpack_eth_usdc_perp_grid.json
```

### 方法 2: 系統級強制終止（緊急情況）

如果 CLI 方法失效，使用系統命令：

```bash
# 查找所有相關進程
ps aux | grep -E "(daemon_manager|run.py)" | grep -v grep

# 強制終止所有守護進程
pkill -f daemon_manager

# 強制終止所有交易機器人
pkill -f run.py

# 終極手段：終止所有 Python3 進程
killall -9 python3
```

### 方法 3: 清理殘留文件

終止後務必清理殘留文件，否則可能導致下次啟動問題：

```bash
# 刪除 PID 文件
rm -f logs/*/daemon.pid
rm -f logs/*/bot.pid

# 清理實例註冊表
rm -f logs/instances.json

# 清理可能的鎖文件
find logs/ -name "*.lock" -delete
```

### 方法 4: 一鍵強制終止腳本

創建快速終止腳本：

```bash
#!/bin/bash
# force_stop_all.sh

echo "強制終止所有交易機器人進程..."
pkill -f daemon_manager
pkill -f run.py
sleep 2

echo "清理殘留文件..."
rm -f logs/*/daemon.pid
rm -f logs/*/bot.pid
rm -f logs/instances.json

echo "驗證進程狀態..."
ps aux | grep -E "(daemon_manager|run.py)" | grep -v grep

echo "完成！"
```

使用方法：
```bash
chmod +x force_stop_all.sh
./force_stop_all.sh
```

## 建議操作流程

1. **先嘗試優雅停止**：
   ```bash
   .venv/bin/python3 core/daemon_manager.py list
   # 然後逐個 stop
   ```

2. **如果失敗，使用強制終止**：
   ```bash
   pkill -f daemon_manager
   pkill -f run.py
   ```

3. **清理並驗證**：
   ```bash
   rm -f logs/*/daemon.pid logs/*/bot.pid logs/instances.json
   ps aux | grep -E "(daemon_manager|run.py)" | grep -v grep
   ```

這應該能解決你遇到的 bug。如果還有特定錯誤訊息，請提供詳細資訊以便進一步診斷。