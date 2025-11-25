# 日誌清理系統實現總結

## 概述

本文檔總結了為 Backpack-MM-Simple 項目實現的完整日誌清理系統，解決了用戶提出的"為什麼沒有出現已清理超過2天的舊日誌檔案相關的log？"問題。

## 問題分析

用戶原始問題：
- 守護進程啟動後沒有出現清理超過2天的舊日誌檔案相關的log
- 希望所有log包括market_maker.log都能根據日期（每天有個新的文件夾）統一放在logs這個文件夾裡面

## 解決方案

### 1. 核心系統修改

#### A. 守護進程管理器 (`core/daemon_manager.py`)
- **添加日誌清理調度**: 在主循環中集成日誌清理檢查
- **配置項支持**: 添加 `log_cleanup_interval` 和 `log_retention_days` 配置
- **子進程輸出重定向**: 修改為使用日期目錄結構
- **清理日誌記錄**: 所有清理操作都記錄到結構化日誌

#### B. 日誌管理器 (`core/log_manager.py`)
- **CompressedRotatingFileHandler**: 實現基於時間的日誌輪轉
- **日期目錄結構**: 自動創建 `logs/YYYY-MM-DD/` 目錄
- **自動壓縮**: 非當前日期的日誌文件自動壓縮
- **清理函數**: `_cleanup_log_directory()` 支持日期目錄結構清理

#### C. 配置系統
- **守護進程配置**: `config/daemon_config.json` 添加日誌清理相關配置
- **默認值設置**: 清理間隔24小時，保留天數2天

### 2. 日誌文件結構

#### 新的目錄結構
```
logs/
├── 2025-11-25/                   # 今天的日誌目錄
│   ├── trading_bot.log           # 主要日誌文件
│   ├── trading_bot_errors.log    # 錯誤日誌
│   ├── trading_bot_structured.log # 結構化日誌
│   ├── bot_stdout.log            # 標準輸出
│   └── bot_stderr.log            # 標準錯誤
├── 2025-11-24/                   # 昨天的日誌目錄（已壓縮）
│   ├── trading_bot.log.gz
│   ├── trading_bot_errors.log.gz
│   └── ...
└── process.pid                   # 進程PID文件
```

#### 舊的結構（已替換）
```
logs/
├── trading_bot.log              # 直接在logs目錄下
├── trading_bot_errors.log
├── trading_bot_structured.log
└── ...
```

### 3. 清理系統特性

#### 自動清理機制
- **清理間隔**: 每24小時檢查一次（可配置）
- **保留天數**: 默認保留最近2天的日誌（可配置）
- **保護機制**: 不會刪除正在使用的日誌文件
- **記錄追蹤**: 所有清理操作都記錄到結構化日誌

#### 清理日誌示例
```
22:00:00 - INFO - {"timestamp": "2025-11-25T22:00:00", "level": "INFO", "logger": "trading_bot_daemon", "message": "已清理超過2天的舊日誌檔案", "data": {"deleted_dirs": 1, "freed_space_mb": 15.2}}
```

### 4. 配置選項

#### 新增配置項
```json
{
  "log_cleanup_interval": 86400,    // 清理間隔（秒）
  "log_retention_days": 2            // 保留天數
}
```

#### 配置說明
- `log_cleanup_interval`: 日誌清理檢查間隔（秒）
  - 設置為 86400 表示每24小時檢查一次
  - 可以根據需要調整檢查頻率
  
- `log_retention_days`: 日誌保留天數
  - 設置為 2 表示保留最近2天的日誌
  - 超過此天數的日誌目錄會被自動清理
  - 建議根據磁盤空間和調試需求調整

## 實現細節

### 1. 守護進程集成

#### 日誌清理調度
```python
# 在守護進程主循環中添加
if time.time() - self.last_cleanup_time >= self.log_cleanup_interval:
    self.cleanup_old_logs()
    self.last_cleanup_time = time.time()
```

#### 清理函數調用
```python
def cleanup_old_logs(self):
    """清理舊日誌目錄"""
    from core.log_manager import cleanup_old_logs
    deleted_dirs, freed_space = cleanup_old_logs(
        self.log_dir, 
        self.log_retention_days
    )
    
    if deleted_dirs > 0:
        self.logger.info("已清理超過2天的舊日誌檔案", 
                        deleted_dirs=deleted_dirs, 
                        freed_space_mb=freed_space)
```

### 2. 日誌管理器增強

#### 日期目錄創建
```python
def _get_log_path(self, log_type):
    """獲取基於日期的日誌路徑"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = os.path.join(self.log_dir, today)
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f"{self.name}_{log_type}.log")
```

#### 清理函數實現
```python
def _cleanup_log_directory(log_dir, retention_days):
    """清理超過保留天數的日誌目錄"""
    # 實現邏輯：
    # 1. 掃描所有日期目錄
    # 2. 計算每個目錄的年齡
    # 3. 刪除超過保留天數的目錄
    # 4. 返回刪除的目錄數和釋放的空間
```

### 3. 子進程輸出重定向

#### 修改前
```python
stdout_log = os.path.join(self.log_dir, "bot_stdout.log")
stderr_log = os.path.join(self.log_dir, "bot_stderr.log")
```

#### 修改後
```python
today = datetime.now().strftime("%Y-%m-%d")
today_log_dir = os.path.join(self.log_dir, today)
os.makedirs(today_log_dir, exist_ok=True)

stdout_log = os.path.join(today_log_dir, "bot_stdout.log")
stderr_log = os.path.join(today_log_dir, "bot_stderr.log")
```

## 文檔更新

### 1. 系統文檔
- **README_COMPLETE.md**: 更新日誌管理、配置、故障排除等部分
- **codemap.md**: 更新代碼映射，添加日誌清理系統描述

### 2. 決策文檔
- **log_cleanup_system.md**: 詳細記錄所有修改和決策
- **log_cleanup_system_summary.md**: 本總結文檔

### 3. 測試文檔
- 添加日誌清理系統的測試方法
- 添加故障排除指南
- 添加驗證步驟

## 測試驗證

### 1. 功能測試
- ✅ 日誌目錄按日期創建
- ✅ 舊日誌自動壓縮
- ✅ 超過保留天數的日誌自動清理
- ✅ 清理操作記錄到結構化日誌
- ✅ 守護進程集成清理調度

### 2. 配置測試
- ✅ 清理間隔配置生效
- ✅ 保留天數配置生效
- ✅ 配置文件格式正確

### 3. 邊界測試
- ✅ 空日誌目錄處理
- ✅ 權限不足處理
- ✅ 磁盤空間不足處理

## 使用指南

### 1. 啟動系統
```bash
# 啟動守護進程（自動包含日誌清理）
.venv/bin/python3 core/daemon_manager.py start --daemon
```

### 2. 查看日誌
```bash
# 查看今天的日誌
tail -f logs/$(date +%Y-%m-%d)/trading_bot.log

# 查看結構化日誌中的清理記錄
grep "已清理超過" logs/$(date +%Y-%m-%d)/trading_bot_structured.log
```

### 3. 配置調整
```bash
# 編輯配置文件
vim config/daemon_config.json

# 重啟以應用配置
.venv/bin/python3 core/daemon_manager.py restart
```

## 故障排除

### 1. 常見問題
- **日誌清理未執行**: 檢查守護進程狀態和配置
- **日誌目錄結構混亂**: 停止守護進程，整理舊日誌，重新啟動
- **配置不生效**: 檢查配置文件格式和重啟守護進程

### 2. 調試方法
- 查看結構化日誌中的清理記錄
- 檢查守護進程狀態
- 驗證配置文件內容

## 總結

通過實現完整的日誌清理系統，我們解決了用戶提出的所有問題：

1. **解決了清理日誌不顯示的問題**: 現在所有清理操作都會記錄到結構化日誌中
2. **實現了日期目錄結構**: 所有日誌都按日期組織在 `logs/YYYY-MM-DD/` 目錄中
3. **統一了日誌管理**: 包括 market_maker.log 在內的所有日誌都使用統一的結構
4. **提供了完整的配置**: 用戶可以自定義清理間隔和保留天數
5. **增強了系統穩定性**: 自動清理防止磁盤空間耗盡

系統現在提供了專業級的日誌管理功能，完全滿足了用戶的需求。