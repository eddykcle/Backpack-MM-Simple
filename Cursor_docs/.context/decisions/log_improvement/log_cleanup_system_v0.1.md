# Log清理系統實施決策

## 背景
- 日誌檔案隨時間累積，佔用磁碟空間且影響系統性能
- 需要自動化清理機制，只保留最近2天的日誌
- 需要同時處理根目錄和logs目錄的日誌檔案

## 決策摘要
1. **修改現有清理函數**
   - 將 `cleanup_old_logs()` 預設保留天數從30天改為2天
   - 添加 `cleanup_root_logs` 參數控制是否清理根目錄log
   - 增強安全性檢查，確保只刪除真正的log檔案

2. **根目錄log清理邏輯**
   - 自動識別根目錄下的 `.log` 檔案
   - 安全檢查：檔案內容必須包含日誌特徵關鍵字
   - 排除系統重要檔案，避免誤刪

3. **程式啟動時自動清理**
   - 在 `run.py` 的 `main()` 函數開頭添加自動清理調用
   - 每次程式啟動時都會自動清理舊log
   - 添加錯誤處理，不影響程式正常運行

## 實施詳情

### 修改的檔案
1. **`core/log_manager.py`**
   - 修改 `cleanup_old_logs()` 函數簽名
   - 添加 `_cleanup_log_directory()` 和 `_cleanup_root_logs()` 輔助函數
   - 添加 `_is_safe_to_delete_log()` 安全檢查函數

2. **`run.py`**
   - 在 `main()` 函數開頭添加自動清理邏輯
   - 包含適當的錯誤處理和日誌記錄

### 安全特性
1. **智能識別**：只刪除包含日誌特徵的檔案
   - 檢查檔案副檔名必須是 `.log`
   - 檢查檔案內容包含日誌關鍵字（如 `INFO`, `ERROR`, `WARNING` 等）
   - 已知根目錄log檔案名稱白名單

2. **保護機制**：排除系統重要檔案
   - 排除 `setup.py`, `requirements.txt`, `README.md` 等重要檔案
   - 跳過目錄和非log檔案

3. **錯誤處理**：確保系統穩定性
   - 清理失敗不影響程式正常啟動
   - 詳細的錯誤日誌記錄

## 使用方式

### 自動清理（預設行為）
程式每次啟動時會自動清理超過2天的舊log：
```bash
python run.py --help  # 會看到 "已清理超過2天的舊日誌檔案"
```

### 手動清理
```python
from core.log_manager import cleanup_old_logs
cleanup_old_logs()  # 清理logs目錄和根目錄的舊log
cleanup_old_logs(cleanup_root_logs=False)  # 只清理logs目錄
cleanup_old_logs(days_to_keep=5)  # 自定義保留天數
```

## 測試驗證
1. **手動清理測試**：成功清理了12個logs目錄下的舊檔案
2. **根目錄清理測試**：成功創建並清理了測試用的舊log檔案
3. **程式啟動測試**：驗證 `python run.py --help` 時自動執行清理

## 效果
- **自動化**：無需手動干預，程式啟動時自動清理
- **安全性**：多重檢查確保不誤刪重要檔案
- **靈活性**：支援自定義保留天數和清理範圍
- **透明性**：詳細的清理日誌記錄

## 後續建議
1. 可考慮添加配置參數讓用戶自定義保留天數
2. 可添加定時清理機制（如每天固定時間清理）
3. 可考慮添加日誌壓縮功能以進一步節省空間

## 涉及檔案
- `core/log_manager.py`
- `run.py`
- `Cursor_docs/.context/decisions/log_cleanup_system.md`
