# 資金檢查與自動終止功能實現

## 日期
2025-12-02 (星期二)

## 背景
用戶詢問：當啟動 `daemon_manager.py` 時，如果賬戶資金不足以進行交易，程序是否會繼續運行？用戶希望在資金不足時立即終止實例。

### 問題分析
- `daemon_manager.py` 只檢查進程是否存活，不檢查資金是否充足
- `PerpGridStrategy` 在初始化時沒有進行保證金檢查
- 資金不足時，策略會繼續運行並嘗試下單，導致無效操作

## 解決方案

採用兩層檢查機制：

### 第一層：策略初始化時檢查
在 `PerpGridStrategy.initialize_grid()` 中添加資金驗證：
1. 獲取當前價格和保證金餘額
2. 計算所需保證金 = (max_position * current_price) / leverage * 1.1
3. 如果可用保證金 < 所需保證金，拋出 `InsufficientFundsError` 異常

### 第二層：run.py 入口捕獲
在策略執行時捕獲異常並終止進程：
```python
except InsufficientFundsError as e:
    logger.error(f"資金不足，策略終止: {e}")
    sys.exit(1)
```

## 修改文件

### 1. `core/exceptions.py`
新增交易相關異常類：
```python
class TradingError(Exception):
    """交易相關錯誤基類"""
    pass

class InsufficientFundsError(TradingError):
    """資金不足錯誤"""
    def __init__(self, message: str, available: float = None, required: float = None, **kwargs):
        super().__init__(message)
        self.available = available
        self.required = required
        self.details = kwargs
```

### 2. `strategies/perp_grid_strategy.py`
新增兩個方法：

#### `_get_available_margin()`
根據不同交易所的 API 返回格式，統一獲取可用保證金：
- Backpack: `collateral.assets[].availableQuantity`
- Aster: `balances[asset].available`
- APEX: `balances[asset].available`
- Paradex: `collateral.free_collateral`
- Lighter: `balances[asset].available`

#### `_validate_sufficient_margin(current_price)`
驗證保證金是否足夠啟動網格策略：
```python
notional_value = self.max_position * current_price
required_margin = notional_value / self.leverage
required_margin *= 1.1  # 預留 10% 緩衝

if available_margin < required_margin:
    raise InsufficientFundsError(...)
```

並在 `initialize_grid()` 中調用：
```python
# 資金檢查：驗證保證金是否足夠
self._validate_sufficient_margin(current_price)
```

### 3. `run.py`
添加異常導入和捕獲：
```python
from core.exceptions import InsufficientFundsError

# ... 在策略執行的 try-except 中 ...
except InsufficientFundsError as e:
    logger.error(f"資金不足，策略終止: {e}")
    logger.error("請確保賬戶有足夠的保證金後再重新啟動策略")
    sys.exit(1)
```

## 保證金計算邏輯

```
所需保證金 = (最大持倉量 × 當前價格) / 槓桿倍數 × 1.1

例如：
- max_position = 2.682 ETH
- current_price = 2800 USDC
- leverage = 5x
- 所需保證金 = (2.682 × 2800) / 5 × 1.1 = 1651.15 USDC
```

## 預期行為

| 情況 | 行為 |
|------|------|
| 資金充足 | 正常啟動網格策略 |
| 資金不足 | 日誌記錄詳細信息，進程以 exit code 1 退出 |
| Daemon 檢測 | 記錄啟動失敗，不會無限重試（因 `auto_restart: false`） |

## 日誌輸出示例

資金充足時：
```
INFO - 保證金檢查: 可用=2000.0000 USDC, 需要=1651.1500 USDC (max_position=2.6820, price=2800.0000, leverage=5.0x)
INFO - 保證金檢查通過: 可用 2000.0000 >= 需要 1651.1500
```

資金不足時：
```
INFO - 保證金檢查: 可用=500.0000 USDC, 需要=1651.1500 USDC (max_position=2.6820, price=2800.0000, leverage=5.0x)
ERROR - 保證金不足，無法啟動網格策略: 可用 500.0000 USDC, 需要 1651.1500 USDC
ERROR - 資金不足，策略終止: 保證金不足...
ERROR - 請確保賬戶有足夠的保證金後再重新啟動策略
```

## 結論

本次實現確保了在資金不足時，策略會立即終止而不是繼續無效運行。這避免了：
1. 無效的 API 請求
2. 日誌中充斥失敗的下單記錄
3. Daemon 誤以為策略正常運行
