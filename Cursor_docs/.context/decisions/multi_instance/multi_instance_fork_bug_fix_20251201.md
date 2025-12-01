# 多實例啟動 Bug 修復記錄

## 📋 文檔信息

- **日期**：2025-12-01
- **版本**：1.0
- **問題類型**：Bug 修復
- **影響範圍**：多實例同時運行功能
- **修復狀態**：✅ 已完成

---

## 🐛 問題描述

### 症狀
當嘗試同時啟動多個交易機器人實例（例如 `bp_eth_01` 和 `bp_sol_01`）時：
1. 第一個實例（bp_eth_01）能正常啟動並掛單
2. 第二個實例（bp_sol_01）守護進程啟動成功，但 **bot 進程從未啟動**
3. 日誌顯示 "守護進程已啟動"，但沒有 "交易機器人進程已啟動" 的後續日誌
4. `bot_stdout.log` 文件不存在

### 重現步驟
```bash
# 啟動第一個實例
.venv/bin/python3 core/daemon_manager.py start --config config/active/backpack_eth_usdc_perp_grid.json --daemon

# 等待幾秒後啟動第二個實例
.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_sol_01.json --daemon

# 第二個實例守護進程啟動，但 bot 不會啟動
```

---

## 🔍 問題分析

### 根本原因

經過深入分析，發現了 **三個關鍵問題**：

#### 問題 1：`start()` 方法中 `get_logger` 沒有傳遞 `log_dir`

**位置**：`core/daemon_manager.py` 第 334 行

**問題代碼**：
```python
# 清除日誌記錄器緩存，確保使用新的配置
_loggers.clear()

# 重新創建日誌記錄器
self.logger = get_logger("trading_bot_daemon")  # ❌ 沒有傳 log_dir
```

**影響**：
- `get_logger("trading_bot_daemon")` 使用默認的 "logs" 目錄
- 應該使用實例專用的 `logs/{instance_id}` 目錄

#### 問題 2：fork 後子進程沒有重新初始化日誌器

**位置**：`core/daemon_manager.py` `start()` 方法中的 fork 邏輯

**問題代碼**：
```python
if daemonize:
    daemon_pid = os.fork()
    if daemon_pid > 0:
        # 父進程退出
        return True
    
    # 子進程繼續執行
    os.setsid()
    os.umask(0)
    # ❌ 沒有重新初始化日誌器！
```

**影響**：
- fork 後子進程繼承了父進程的文件描述符和日誌處理器
- 當多個實例同時運行時，這些共享的資源會導致衝突
- 子進程的日誌無法正確寫入，主循環可能無法正常工作

#### 問題 3：`log_manager.py` 中 `shutil` 局部導入問題

**位置**：`core/log_manager.py` 第 590 行

**問題代碼**：
```python
if dir_datetime < cutoff_date:
    import shutil  # ❌ 局部導入會遮蔽全局導入
    shutil.rmtree(date_dir)
```

**影響**：
- 文件頂部已經 `import shutil`（第 11 行）
- 函數內部的局部導入會遮蔽全局導入
- 如果 if 塊沒有執行，else 塊中使用 `shutil` 會報錯：
  `"cannot access local variable 'shutil' where it is not associated with a value"`

---

## ✅ 修復方案

### 修復 1：傳遞正確的 `log_dir` 參數

**文件**：`core/daemon_manager.py`

```python
# 修改前
self.logger = get_logger("trading_bot_daemon")

# 修改後
self.logger = get_logger("trading_bot_daemon", log_dir=str(self.log_dir))
```

### 修復 2：fork 後重新初始化日誌器和進程管理器

**文件**：`core/daemon_manager.py`

```python
if daemonize:
    daemon_pid = os.fork()
    if daemon_pid > 0:
        self.logger.info("守護進程已啟動在後台", child_pid=daemon_pid)
        return True
    
    # 子進程繼續執行
    os.setsid()
    os.umask(0)
    
    # 重要：fork 後子進程必須重新初始化日誌器和進程管理器
    # 因為父進程的文件描述符和日誌處理器可能已關閉或有衝突
    # 這是多實例能夠同時運行的關鍵
    _loggers.clear()
    self.logger = get_logger("trading_bot_daemon", log_dir=str(self.log_dir))
    self.process_manager = ProcessManager(str(self.log_dir))
```

### 修復 3：移除 `shutil` 的局部導入

**文件**：`core/log_manager.py`

```python
# 修改前
if dir_datetime < cutoff_date:
    import shutil
    shutil.rmtree(date_dir)

# 修改後（使用頂部已導入的 shutil）
if dir_datetime < cutoff_date:
    shutil.rmtree(date_dir)
```

---

## 📊 修復前後對比

### 修復前的日誌（bp_sol_01）
```
00:37:58 - INFO - 多配置格式已載入
00:37:58 - INFO - 實例已註冊
00:37:58 - INFO - 開始啟動守護進程
00:37:58 - INFO - 守護進程已啟動在後台
00:37:58 - INFO - 守護進程已啟動
# ❌ 沒有 "交易機器人未運行，正在重啟" 的日誌
# ❌ 沒有 "交易機器人進程已啟動" 的日誌
# ❌ bot_stdout.log 不存在
```

### 修復後的日誌（預期）
```
00:XX:XX - INFO - 多配置格式已載入
00:XX:XX - INFO - 實例已註冊
00:XX:XX - INFO - 開始啟動守護進程
00:XX:XX - INFO - 守護進程已啟動在後台
00:XX:XX - INFO - 守護進程已啟動
00:XX:XX - WARNING - 交易機器人未運行，正在重啟  # ✅
00:XX:XX - INFO - 正在啟動交易機器人           # ✅
00:XX:XX - INFO - 交易機器人進程已啟動          # ✅
00:XX:XX - INFO - 交易機器人重啟成功            # ✅
```

---

## 🧪 測試步驟

```bash
# 1. 確保沒有舊進程
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_sol_01.json
.venv/bin/python3 core/daemon_manager.py stop --config config/active/backpack_eth_usdc_perp_grid.json

# 2. 確認清空
.venv/bin/python3 core/daemon_manager.py list

# 3. 啟動第一個實例
.venv/bin/python3 core/daemon_manager.py start --config config/active/backpack_eth_usdc_perp_grid.json --daemon

# 4. 等待確認啟動成功
sleep 10

# 5. 啟動第二個實例
.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_sol_01.json --daemon

# 6. 查看狀態
sleep 10
.venv/bin/python3 core/daemon_manager.py list

# 預期輸出：兩個實例都應該顯示為運行中（🟢）
```

---

## 📝 修改的文件清單

| 文件 | 修改類型 | 說明 |
|-----|---------|------|
| `core/daemon_manager.py` | Bug 修復 | 傳遞正確的 log_dir 參數 |
| `core/daemon_manager.py` | Bug 修復 | fork 後重新初始化日誌器和進程管理器 |
| `core/log_manager.py` | Bug 修復 | 移除 shutil 局部導入 |

---

## 🔑 關鍵教訓

1. **fork 後的資源管理**：Unix fork 會複製父進程的所有資源（包括文件描述符），子進程需要重新初始化需要獨立的資源。

2. **日誌器的單例模式**：`get_logger()` 使用單例模式，如果不清除緩存並傳遞正確參數，可能會返回錯誤配置的日誌器。

3. **Python 變量作用域**：在函數內部使用 `import` 語句會創建局部變量，這會遮蔽全局同名變量。

4. **多實例隔離**：每個實例需要完全獨立的：
   - 日誌目錄 (`logs/{instance_id}/`)
   - PID 文件 (`daemon.pid`, `bot.pid`)
   - 數據庫文件
   - Web 端口

---

## 📚 相關文檔

- [多實例啟動方法指南](./multi_instance_startup_methods_20251130.md)
- [合併實例 CLI 計劃](./merge-instance-cli.plan.md)
- [系統管理文檔](../../../docs/system/Fork_README.md)

---

**文檔版本**：1.0  
**作者**：Kilo Code  
**最後更新**：2025-12-01
