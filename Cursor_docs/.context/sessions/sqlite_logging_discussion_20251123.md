# SQLite 與日誌功能討論記錄
**日期：** 2025-11-23  
**討論主題：** 項目中 SQLite 數據庫和日誌功能的使用與查閱方法  
**狀態：** Completed  

---

## 討論概述

本次討論重點確認了 Backpack-MM-Simple 項目中 SQLite 數據庫和日誌系統的功能實現，以及如何有效查閱和管理這些數據。

---

## 1. 項目功能確認

### ✅ SQLite 數據庫功能
項目確實包含完整的 SQLite 數據庫功能，位於 `database/db.py`：

#### 數據庫表結構：
1. **completed_orders** - 存儲完成的訂單記錄
   - order_id, symbol, side, quantity, price, maker, fee, fee_asset, trade_type, timestamp
   
2. **trading_stats** - 交易統計數據
   - date, symbol, maker_buy_volume, maker_sell_volume, taker_buy_volume, taker_sell_volume
   - realized_profit, total_fees, net_profit, avg_spread, trade_count, volatility
   
3. **rebalance_orders** - 重平衡訂單記錄
   - order_id, symbol, timestamp
   
4. **market_data** - 市場數據存儲
   - symbol, price, volume, bid_ask_spread, liquidity_score, timestamp

#### 主要功能：
- 訂單記錄插入和查詢
- 交易統計數據管理
- 市場數據存儲
- 重平衡訂單追蹤
- 完整的錯誤處理和事務管理

### ✅ 日誌系統功能
項目實現了兩層日誌系統：

#### 基礎日誌系統 (`core/logger.py`)
- 簡單的日誌配置
- 支持文件和控制台輸出
- 行緩衝模式確保即時寫入

#### 高級日誌管理系統 (`core/log_manager.py`)
功能豐富的日誌系統，包含：

**核心特性：**
- **結構化日誌** - 支持JSON格式輸出
- **日誌輪轉** - 自動輪轉和壓縮舊日誌
- **異步處理** - 避免阻塞主線程
- **多級別日誌** - 分別記錄不同級別的日誌到不同文件
- **進程管理** - 替代nohup的守護進程功能

**日誌文件類型：**
- `{name}.log` - 主要日誌文件
- `{name}_errors.log` - 錯誤專用日誌
- `{name}_structured.log` - JSON格式結構化日誌
- `stdout.log` / `stderr.log` - 標準輸出重定向

---

## 2. 同時使用兩個功能

### 配置啟用
在 `.env` 文件中設置：
```bash
# 啟用數據庫功能
ENABLE_DATABASE=1
DB_PATH=orders.db

# 配置日誌文件
LOG_FILE=market_maker.log
```

### 使用示例

#### 數據庫操作：
```python
from database.db import Database
from core.logger import setup_logger

# 初始化數據庫
db = Database()
logger = setup_logger("trading_bot")

# 記錄訂單到數據庫
order_data = {
    'order_id': '12345',
    'symbol': 'SOL_USDC',
    'side': 'buy',
    'quantity': 10.0,
    'price': 100.5,
    'maker': True,
    'fee': 0.01,
    'fee_asset': 'USDC',
    'trade_type': 'market'
}

db.insert_order(order_data)
logger.info(f"訂單已記錄到數據庫: {order_data['order_id']}")
```

#### 高級日誌系統：
```python
from core.log_manager import get_logger

# 獲取結構化日誌記錄器
logger = get_logger("trading_bot")

# 同時記錄到日誌和數據庫
logger.info("交易執行開始", 
           order_id=order_data['order_id'],
           symbol=order_data['symbol'],
           side=order_data['side'])

# 記錄錯誤
logger.error("訂單執行失敗", 
            error_code="ORDER_FAILED",
            order_id=order_data['order_id'],
            details={"reason": "insufficient_balance"})
```

---

## 3. 查閱 SQLite 數據庫的方法

### 3.1 使用項目內建的查詢功能

```python
from database.db import Database

db = Database()

# 查詢最近的交易記錄
recent_trades = db.get_recent_trades("SOL_USDC", limit=10)
print("最近交易:", recent_trades)

# 查詢交易統計
stats = db.get_trading_stats("SOL_USDC")
print("交易統計:", stats)

# 查詢所有時間的總計統計
all_time_stats = db.get_all_time_stats("SOL_USDC")
print("總計統計:", all_time_stats)
```

### 3.2 使用 SQLite 命令行工具

```bash
# 進入SQLite命令行
sqlite3 orders.db

# 查看所有表
.tables

# 查看表結構
.schema completed_orders

# 查詢最近的訂單
SELECT * FROM completed_orders ORDER BY timestamp DESC LIMIT 10;

# 查詢特定交易對的統計
SELECT * FROM trading_stats WHERE symbol = 'SOL_USDC';

# 查詢今日交易量
SELECT 
    symbol,
    SUM(CASE WHEN side = 'buy' THEN quantity ELSE 0 END) as buy_volume,
    SUM(CASE WHEN side = 'sell' THEN quantity ELSE 0 END) as sell_volume,
    COUNT(*) as trade_count
FROM completed_orders 
WHERE DATE(timestamp) = DATE('now')
GROUP BY symbol;
```

### 3.3 使用圖形化工具

推薦的 SQLite 客戶端：
- **DB Browser for SQLite** (免費，跨平台)
- **DBeaver** (免費，功能強大)
- **SQLiteStudio** (免費，輕量級)

### 3.4 創建查詢腳本

```python
# query_database.py
from database.db import Database
import json
from datetime import datetime, timedelta

def query_trading_data():
    db = Database()
    
    print("=== 交易數據查詢報告 ===")
    print(f"查詢時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 最近24小時的交易
    print("1. 最近24小時交易記錄:")
    recent_trades = db.get_recent_trades("SOL_USDC", limit=5)
    for trade in recent_trades:
        print(f"  {trade['timestamp']}: {trade['side']} {trade['quantity']} @ {trade['price']}")
    print()
    
    # 2. 交易統計
    print("2. 交易統計:")
    stats = db.get_trading_stats("SOL_USDC")
    if stats:
        for stat in stats[:3]:  # 顯示最近3天
            print(f"  {stat['date']}: 利潤 {stat['net_profit']}, 手續費 {stat['total_fees']}")
    print()
    
    # 3. 總計統計
    print("3. 所有時間總計:")
    all_time = db.get_all_time_stats("SOL_USDC")
    if all_time:
        print(f"  總買量: {all_time['total_maker_buy'] + all_time['total_taker_buy']}")
        print(f"  總賣量: {all_time['total_maker_sell'] + all_time['total_taker_sell']}")
        print(f"  總利潤: {all_time['total_profit']}")
        print(f"  總手續費: {all_time['total_fees']}")

if __name__ == "__main__":
    query_trading_data()
```

---

## 4. 查閱日誌文件的方法

### 4.1 直接查看日誌文件

```bash
# 查看主日誌
tail -f market_maker.log

# 查看錯誤日誌
tail -f logs/trading_bot_errors.log

# 查看結構化日誌
tail -f logs/trading_bot_structured.log
```

### 4.2 使用 grep 搜索

```bash
# 搜索特定訂單ID
grep "order_id:12345" market_maker.log

# 搜索錯誤信息
grep "ERROR" market_maker.log

# 搜索特定時間範圍
grep "2025-11-23" market_maker.log
```

### 4.3 解析結構化日誌

```python
# parse_logs.py
import json
from pathlib import Path

def parse_structured_logs():
    log_file = Path("logs/trading_bot_structured.log")
    
    trades = []
    errors = []
    
    for line in log_file.read_text().split('\n'):
        if not line.strip():
            continue
            
        try:
            log_entry = json.loads(line)
            
            if 'order_id' in log_entry.get('data', {}):
                trades.append(log_entry)
            elif log_entry['level'] == 'ERROR':
                errors.append(log_entry)
                
        except json.JSONDecodeError:
            continue
    
    print(f"找到 {len(trades)} 個交易記錄")
    print(f"找到 {len(errors)} 個錯誤記錄")
    
    return trades, errors
```

---

## 5. 結合查詢的最佳實踐

### 5.1 創建綜合報告

```python
# generate_report.py
from database.db import Database
from core.log_manager import get_logger
import json
from datetime import datetime

def generate_daily_report():
    db = Database()
    
    report = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'database_stats': {},
        'log_summary': {}
    }
    
    # 從數據庫獲取統計
    stats = db.get_trading_stats("SOL_USDC", date=report['date'])
    if stats:
        report['database_stats'] = stats[0]
    
    # 從日誌獲取信息
    log_file = Path("logs/trading_bot_structured.log")
    if log_file.exists():
        # 解析今日日誌
        today_logs = []
        for line in log_file.read_text().split('\n'):
            if report['date'] in line and line.strip():
                try:
                    today_logs.append(json.loads(line))
                except:
                    continue
        
        report['log_summary'] = {
            'total_entries': len(today_logs),
            'errors': len([log for log in today_logs if log['level'] == 'ERROR']),
            'trades': len([log for log in today_logs if 'order_id' in str(log)])
        }
    
    return report
```

### 5.2 實時監控腳本

```python
# monitor.py
import time
from database.db import Database
from core.log_manager import get_logger

def real_time_monitor():
    db = Database()
    logger = get_logger("monitor")
    
    last_count = 0
    
    while True:
        # 檢查新交易
        current_trades = len(db.get_order_history("SOL_USDC", limit=10000))
        new_trades = current_trades - last_count
        
        if new_trades > 0:
            logger.info(f"檢測到 {new_trades} 筆新交易")
            last_count = current_trades
        
        time.sleep(60)  # 每分鐘檢查一次
```

---

## 6. 協同工作流程

### 6.1 典型使用場景

1. **交易執行** → 記錄到日誌（實時監控）
2. **訂單完成** → 存儲到SQLite（持久化）
3. **統計分析** → 從數據庫查詢，結果記錄到日誌
4. **錯誤處理** → 日誌記錄詳細錯誤，數據庫記錄失敗訂單

### 6.2 實際項目中的集成

查看項目的主要文件，發現：
- **策略文件**（如 `strategies/market_maker.py`）同時使用數據庫和日誌
- **API客戶端**（如 `api/bp_client.py`）記錄API調用到日誌
- **核心模塊**（如 `core/daemon_manager.py`）使用高級日誌管理

### 6.3 優勢

**同時使用的優點：**
- **數據完整性** - SQLite確保數據不丟失
- **實時監控** - 日誌提供即時反饋
- **性能優化** - 異步日誌不影響交易性能
- **故障排查** - 結合日誌和數據庫快速定位問題
- **歷史分析** - 數據庫存儲長期數據，日誌記錄詳細事件

---

## 7. 配置建議

### 7.1 環境配置

```python
# 在您的代碼中
from database.db import Database
from core.log_manager import get_logger

class TradingBot:
    def __init__(self):
        self.db = Database()
        self.logger = get_logger("trading_bot")
        
    def execute_trade(self, order_data):
        try:
            # 記錄到日誌
            self.logger.info("開始執行交易", order_data=order_data)
            
            # 執行交易邏輯...
            
            # 存儲到數據庫
            order_id = self.db.insert_order(order_data)
            
            # 記錄成功
            self.logger.info("交易執行成功", 
                           order_id=order_id, 
                           database_record=True)
                           
        except Exception as e:
            # 記錄錯誤到日誌
            self.logger.error("交易執行失敗", 
                            error=str(e), 
                            order_data=order_data)
            raise
```

### 7.2 生產環境建議

```bash
# .env 配置
ENABLE_DATABASE=1
DB_PATH=/var/lib/trading_bot/orders.db
LOG_FILE=/var/log/trading_bot/market_maker.log

# 確保目錄權限
mkdir -p /var/lib/trading_bot
mkdir -p /var/log/trading_bot
chown -R trading_bot:trading_bot /var/lib/trading_bot
chown -R trading_bot:trading_bot /var/log/trading_bot
```

---

## 8. 總結

### 核心結論
- **SQLite數據庫** → 用於查詢結構化的交易數據和統計
- **日誌文件** → 用於查看系統運行狀態和調試信息
- **結合使用** → 數據庫提供"什麼發生了"，日誌提供"為什麼發生"

### 最佳實踐
1. **配置管理** - 使用環境變數統一管理配置
2. **錯誤處理** - 日誌記錄詳細錯誤，數據庫記錄失敗操作
3. **性能考慮** - 使用異步日誌避免阻塞交易
4. **監控告警** - 結合日誌監控和數據庫統計實現全面監控
5. **數據備份** - 定期備份SQLite數據庫和重要日誌文件

### 工具推薦
- **數據庫查詢** - DB Browser for SQLite, DBeaver
- **日誌分析** - grep, jq, 自定義Python腳本
- **監控工具** - Prometheus + Grafana, ELK Stack
- **自動化** - cron jobs, systemd timers

---

**記錄完成時間：** 2025-11-23 01:04  
**相關文件：** `database/db.py`, `core/logger.py`, `core/log_manager.py`, `config.py`  
**適用版本：** Backpack-MM-Simple v1.x+

---

*此文檔將作為項目數據存儲和日誌管理的參考指南，建議定期更新以反映最新的功能變更。*
