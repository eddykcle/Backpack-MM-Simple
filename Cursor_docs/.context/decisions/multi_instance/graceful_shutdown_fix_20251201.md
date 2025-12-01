# 優雅停止機制修復記錄

## 📋 文檔信息

- **日期**：2025-12-01
- **版本**：1.0
- **問題類型**：Bug 修復
- **影響範圍**：所有策略的停止機制
- **修復狀態**：✅ 已完成

---

## 🐛 問題描述

### 症狀
當使用 `daemon_manager.py stop` 停止交易機器人時：
1. 進程無法在 25 秒內優雅終止
2. 出現警告：`進程未在 25 秒內終止，強制殺掉`
3. 即使強制 kill 後，仍需等待 5 秒才能確認退出
4. 總停止時間超過 30 秒

### 重現步驟
```bash
# 啟動實例
.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_sol_01.json --daemon

# 停止實例（會出現超時警告）
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_sol_01.json --daemon
```

### 日誌記錄
```
21:30:58 - 正在停止本實例的交易機器人進程...
21:30:58 - 等待 bot 進程完成清理（取消訂單等），超時時間: 25 秒
21:31:23 - 進程未在 25 秒內終止，強制殺掉  ⚠️ 25秒後
21:31:28 - 強制殺掉後 5 秒內仍未退出        ⚠️ 又過了5秒
21:31:29 - Bot 進程已停止
```

---

## 🔍 問題分析

### 根本原因

經過代碼分析，發現 **兩個關鍵阻塞點**：

#### 問題 1：主循環的長時間 `sleep` 阻塞

**位置**：`strategies/market_maker.py` 第 2422-2424 行

**問題代碼**：
```python
wait_time = interval_seconds  # 默認 60 秒
logger.info(f"等待 {wait_time} 秒後進行下一次迭代...")
time.sleep(wait_time)  # ❌ 阻塞最多 60 秒！
```

**影響**：
- `time.sleep(60)` 是阻塞調用
- 當 SIGTERM 到達時，進程需要等待 sleep 結束才能響應
- 這導致進程無法在 25 秒超時內退出

#### 問題 2：`stop()` 方法在信號處理器中執行阻塞操作

**位置**：`strategies/market_maker.py` 第 2308-2326 行

**問題代碼**：
```python
def stop(self):
    logger.info("收到停止信號，正在停止做市策略...")
    self._stop_flag = True
    self._stop_trading = True
    
    # ❌ 在信號處理器中執行網絡請求，可能長時間阻塞
    try:
        logger.info("正在取消所有未成交訂單...")
        self.cancel_existing_orders()  # 包含多個網絡請求
        logger.info("所有訂單取消完成")
    except Exception as e:
        logger.error(f"取消訂單時發生錯誤: {e}")
```

**影響**：
- `cancel_existing_orders()` 包含多個網絡請求（`get_open_orders`、`cancel_all_orders`）
- 這些請求沒有超時控制，可能需要很長時間
- 信號處理器應該快速返回，不應執行阻塞操作

### 問題流程圖

```
SIGTERM 到達
     │
     ▼
┌─────────────────────────────────────────┐
│ 主線程可能正在執行：                      │
│ 1. time.sleep(60) - 等待下一次迭代       │
│ 2. API 請求 - 下單/查詢訂單              │
└─────────────────────────────────────────┘
     │
     ▼ (等待阻塞操作完成)
     │
┌─────────────────────────────────────────┐
│ 信號處理器執行 strategy.stop()           │
│   └─> cancel_existing_orders()          │
│       ├─> get_open_orders()    (阻塞)   │
│       ├─> cancel_all_orders()  (阻塞)   │
│       ├─> time.sleep(1)        (阻塞)   │
│       └─> get_open_orders()    (阻塞)   │
└─────────────────────────────────────────┘
     │
     ▼
  已經超過 25 秒...
```

---

## 🔧 修復方案

### 修復 1：簡化 `stop()` 方法

**文件**：`strategies/market_maker.py`

**修改前**：
```python
def stop(self):
    """停止做市策略
    
    執行優雅停止流程：
    1. 設置停止標誌位
    2. 主動取消所有未成交訂單
    3. 關閉 WebSocket 連接
    """
    logger.info("收到停止信號，正在停止做市策略...")
    self._stop_flag = True
    self._stop_trading = True
    
    # 主動取消所有未成交訂單（確保訂單被取消）
    try:
        logger.info("正在取消所有未成交訂單...")
        self.cancel_existing_orders()
        logger.info("所有訂單取消完成")
    except Exception as e:
        logger.error(f"取消訂單時發生錯誤: {e}")
```

**修改後**：
```python
def stop(self):
    """停止做市策略
    
    執行優雅停止流程：
    1. 設置停止標誌位，讓主循環快速退出
    2. 訂單取消由 run() 方法的 finally 塊處理
    
    注意：此方法可能在信號處理器中被調用，因此必須快速返回，
    不能執行阻塞操作（如網絡請求）。
    """
    logger.info("收到停止信號，設置停止標誌...")
    self._stop_flag = True
    self._stop_trading = True
    logger.info("停止標誌已設置，主循環將在下次檢查時退出")
```

### 修復 2：分段 sleep，每秒檢查停止標誌

**文件**：`strategies/market_maker.py`

**修改前**：
```python
wait_time = interval_seconds
logger.info(f"等待 {wait_time} 秒後進行下一次迭代...")
time.sleep(wait_time)
```

**修改後**：
```python
wait_time = interval_seconds
logger.info(f"等待 {wait_time} 秒後進行下一次迭代...")
# 分段 sleep，每秒檢查停止標誌，確保能快速響應停止信號
for _ in range(wait_time):
    if self._stop_flag:
        logger.info("檢測到停止標誌，提前結束等待")
        break
    time.sleep(1)
```

---

## 🔒 安全性保證

訂單取消和資源清理仍然會執行，由 `run()` 方法的 `finally` 塊保證：

```python
finally:
    logger.info("取消所有未成交訂單...")
    self.cancel_existing_orders()  # ✅ 訂單仍會被取消
    
    # 關閉 WebSocket
    if self.ws:
        self.ws.close()  # ✅ WebSocket 仍會關閉
    
    # 關閉數據庫連接
    if self.db:
        self.db.close()  # ✅ 數據庫連接仍會關閉
        logger.info("數據庫連接已關閉")

    # 關閉背景執行緒池
    if hasattr(self, "executor") and self.executor:
        self.executor.shutdown(wait=False)  # ✅ 線程池仍會關閉
        logger.info("背景執行緒池已關閉")
```

---

## 📊 修復效果

### 時序對比

| 階段 | 修復前 | 修復後 |
|------|--------|--------|
| 主循環響應 | 最多 60 秒 | 最多 1 秒 |
| 信號處理器 | 包含網絡請求 | 僅設置標誌 |
| 總停止時間 | 25-60+ 秒 | 1-5 秒 |

### 預期日誌變化

**修復前**：
```
21:30:58 - 等待 bot 進程完成清理，超時時間: 25 秒
21:31:23 - 進程未在 25 秒內終止，強制殺掉  ⚠️
```

**修復後**：
```
21:30:58 - 等待 bot 進程完成清理，超時時間: 25 秒
21:30:59 - 檢測到停止標誌，提前結束等待
21:31:00 - 取消所有未成交訂單...
21:31:02 - Bot 進程已停止  ✅
```

---

## 📝 影響範圍

### 受影響的類

所有繼承自 `MarketMaker` 的策略類：

- `MarketMaker` (基類)
- `PerpetualMarketMaker`
- `PerpGridStrategy`
- `GridStrategy`
- `MakerTakerHedgeStrategy`

### 不受影響的功能

- 訂單下單邏輯
- 成交處理邏輯
- WebSocket 連接管理
- 數據庫操作

---

## ✅ 測試驗證

### 測試命令
```bash
# 啟動
.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_sol_01.json --daemon

# 等待幾秒後停止
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_sol_01.json --daemon
```

### 預期結果
- 進程在 1-5 秒內優雅退出
- 不再出現「進程未在 25 秒內終止」的警告
- 訂單被正確取消
- 所有資源被正確釋放

---

## 📚 相關文件

- `strategies/market_maker.py` - 主要修改文件
- `run.py` - 信號處理器定義
- `core/daemon_manager.py` - 進程管理器

---

## 🔮 後續優化建議

1. **API 超時控制**：為網絡請求添加超時參數（如 5-10 秒）
2. **finally 塊超時保護**：添加清理操作的超時限制
3. **異步取消訂單**：考慮使用異步方式取消訂單，減少阻塞時間
