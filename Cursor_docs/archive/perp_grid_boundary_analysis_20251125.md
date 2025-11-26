# 永續合約網格策略邊界觸碰機制分析

日期: 2025-11-25
分析文件: strategies/perp_grid_strategy.py

## 結論：目前沒有觸碰上下限自動平倉和取消所有訂單的機制

### 現有風控機制：

#### 1. 止損止盈機制（繼承自 PerpetualMarketMaker）
- 參數：`stop_loss` 和 `take_profit`
- 實現位置：`check_stop_conditions()` 方法
- 觸發行為：調用 `cancel_existing_orders()` 和 `close_position()`
- 觸發條件：基於盈虧，不是基於價格邊界

#### 2. 最大持倉風控
- 實現位置：`manage_positions()` 方法
- 觸發條件：持倉量超過 `max_position`
- 觸發行為：執行緊急平倉

#### 3. 網格邊界處理（僅警告，不執行操作）
在 `_place_close_long_order()` 和 `_place_close_short_order()` 方法中：
- 當開多價格已是最高網格時，記錄警告但不平倉（第1300-1302行）
- 當開空價格已是最低網格時，記錄警告但不平倉（第1380-1382行）

### 問題分析：

網格策略有 `grid_upper_price` 和 `grid_lower_price` 參數：
- 這些參數在 `_initialize_grid_prices()` 方法中用於生成網格點位
- 但僅用於確定網格範圍，沒有觸發自動平倉的邏輯
- 當價格超出網格範圍時，策略會繼續運行但無法正常工作

### 實現觸碰上下限自動平倉功能的必要性：

1. **風險控制**：當價格遠離網格範圍時，策略無法正常運作，可能導致：
   - 單邊持倉累積過大
   - 無法實現網格套利邏輯
   - 市場逆轉時造成重大損失

2. **資金效率**：價格脫離網格範圍後，掛單長期無法成交，資金被閒置

3. **策略完整性**：網格策略應該有明確的運行邊界，超出邊界應有相應處理機制

### 推薦實現方案：

#### 方案一：在現有架構中添加邊界檢查

```python
def _check_price_boundaries(self) -> bool:
    """檢查當前價格是否超出網格範圍"""
    current_price = self.get_current_price()
    if not current_price:
        return False
        
    # 檢查是否超出網格範圍（允許一定容差）
    tolerance = 0.001  # 0.1% 容差
    upper_threshold = self.grid_upper_price * (1 + tolerance)
    lower_threshold = self.grid_lower_price * (1 - tolerance)
    
    if current_price > upper_threshold:
        logger.warning(f"價格 {current_price} 超出網格上限 {self.grid_upper_price}")
        return True
    elif current_price < lower_threshold:
        logger.warning(f"價格 {current_price} 低於網格下限 {self.grid_lower_price}")
        return True
    
    return False

def _handle_boundary_breach(self) -> None:
    """處理價格觸碰網格邊界"""
    logger.warning("價格觸碰網格邊界，執行緊急平倉和取消訂單")
    
    # 1. 取消所有未成交訂單
    self.cancel_existing_orders()
    
    # 2. 平掉所有持倉
    net_position = self.get_net_position()
    if abs(net_position) > self.min_order_size:
        self.close_position(order_type="Market")
    
    # 3. 停止策略運行或重新調整網格範圍
    self._stop_trading = True
    self.stop_reason = "價格觸碰網格邊界，已執行緊急平倉"
```

#### 方案二：可配置的邊界處理策略

添加配置參數，讓用戶選擇邊界觸發時的行為：

```python
def __init__(
    self,
    # ... 現有參數
    boundary_action: str = "emergency_close",  # "emergency_close", "adjust_range", "stop_only"
    boundary_tolerance: float = 0.001,  # 0.1% 容差
    # ...
):
    self.boundary_action = boundary_action
    self.boundary_tolerance = boundary_tolerance

def _handle_boundary_breach(self) -> None:
    """根據配置處理價格觸碰網格邊界"""
    if self.boundary_action == "emergency_close":
        # 緊急平倉並停止策略
        self.cancel_existing_orders()
        net_position = self.get_net_position()
        if abs(net_position) > self.min_order_size:
            self.close_position(order_type="Market")
        self._stop_trading = True
        
    elif self.boundary_action == "adjust_range":
        # 自動調整網格範圍
        current_price = self.get_current_price()
        price_range = current_price * (self.price_range_percent / 100)
        self.adjust_grid_range(
            new_lower_price=current_price - price_range,
            new_upper_price=current_price + price_range
        )
        
    elif self.boundary_action == "stop_only":
        # 只停止新訂單，保留持倉
        self._stop_trading = True
```

### 實現位置建議：

1. 在 `PerpGridStrategy` 類中添加新方法
2. 在 `place_limit_orders()` 方法開頭添加邊界檢查
3. 在 `__init__()` 方法中添加配置參數

這樣的實現既保持了代碼的整潔性，又提供了必要的安全保障。

### 推薦採用方案二：

**靈活性高**：用戶可根據市場情況和個人偏好選擇不同的處理方式
**向下兼容**：默認使用緊急平倉，不影響現有用戶
**適應性強**：在高波動市場可選擇調整範圍，在風險可控情況下保持策略運行