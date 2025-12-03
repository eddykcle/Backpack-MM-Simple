# 永續網格策略邊界處理實現決策

## 日期
2025-11-25

## 背景
用戶詢問 `strategies/perp_grid_strategy.py` 是否有觸碰上下限自動平倉和取消所有訂單的機制。經分析發現現有網格策略缺乏邊界保護機制，需要實現此功能以增強風險控制。

## 決策
實現方案二：可配置的邊界處理策略，提供三種不同的邊界觸發處理方式。

## 實現詳情

### 1. 新增配置參數
在 `PerpGridStrategy.__init__()` 方法中添加：
- `boundary_action`: 邊界觸發時的處理方式
  - `"emergency_close"`: 緊急平倉並停止策略（默認）
  - `"adjust_range"`: 自動調整網格範圍
  - `"stop_only"`: 只停止新訂單但保留持倉
- `boundary_tolerance`: 邊界觸發的容差（默認 0.001 = 0.1%）
- `enable_boundary_check`: 是否啟用邊界檢查（默認 True）

### 2. 實現核心方法

#### `_check_price_boundaries()` 方法
- 檢查當前價格是否超出網格範圍（考慮容差）
- 返回布爾值表示是否超出邊界
- 包含適當的日誌記錄

#### `_handle_boundary_breach()` 方法
- 根據 `boundary_action` 配置執行不同處理策略：
  - **緊急平倉**：取消所有訂單，平掉所有持倉，停止策略
  - **調整範圍**：自動調整網格範圍以適應當前價格
  - **僅停止**：取消所有訂單但保留持倉，停止策略

### 3. 集成到主要邏輯
在 `place_limit_orders()` 方法開頭添加邊界檢查：
```python
if self._check_price_boundaries():
    self._handle_boundary_breach()
    return
```

### 4. 命令行參數支持
在 `run.py` 中添加三個新的命令行參數：
- `--boundary-action`: 設置邊界處理方式
- `--boundary-tolerance`: 設置邊界容差
- `--enable-boundary-check` / `--disable-boundary-check`: 啟用/禁用邊界檢查

### 5. 配置文件更新
在 `config/daemon_config.json` 中添加默認配置：
```json
"--boundary-action",
"emergency_close",
"--boundary-tolerance",
"0.001",
"--enable-boundary-check"
```

## 使用方法

### 通過配置文件調整
編輯 `config/daemon_config.json`：
```json
"--boundary-action",
"adjust_range"  // 改為所需的處理方式
```

### 通過命令行調整
```bash
python run.py --exchange backpack --symbol ETH_USDC_PERP --strategy perp_grid --boundary-action adjust_range
```

## 技術特點

1. **向後兼容**：所有新參數都有默認值，不影響現有配置
2. **靈活配置**：提供三種不同的處理策略，適應不同風險偏好
3. **容差機制**：避免因小幅價格波動頻繁觸發邊界檢查
4. **可選禁用**：允許用戶完全禁用邊界檢查功能
5. **完整日誌**：提供詳細的日誌記錄，便於調試和監控

## 風險控制效果

1. **防止極端損失**：當價格大幅偏離網格範圍時，自動執行保護措施
2. **靈活應對**：根據市場情況選擇不同的應對策略
3. **及時響應**：在每次訂單更新前檢查邊界，確保及時處理

## 文件變更

1. `strategies/perp_grid_strategy.py`：添加邊界處理邏輯
2. `run.py`：添加命令行參數支持
3. `config/daemon_config.json`：添加默認配置

## 測試建議

1. 測試三種邊界處理策略的正確性
2. 驗證容差機制是否有效防止頻繁觸發
3. 確認配置參數的正確傳遞和應用
4. 檢查日誌記錄的完整性和準確性