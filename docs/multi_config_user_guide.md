# 多配置管理系統用戶指南

## 快速開始

### 什麼是多配置管理系統？

多配置管理系統允許您為不同的交易所、交易對和策略創建獨立的配置文件，讓您可以輕鬆切換和管理多個交易配置。

### 為什麼需要多配置？

- **多交易所**: 同時在 Backpack、Aster、Paradex、Lighter 交易
- **多交易對**: 為 ETH/USDC、SOL/USDC、BTC/USDT 等不同交易對設置不同參數
- **多策略**: 網格交易、做市、對沖等不同策略的參數差異很大
- **風險管理**: 為不同風險級別的交易設置不同參數

## 基礎使用

### 1. 查看可用配置

```bash
# 列出所有配置
python cli/commands.py --config list

# 按交易所篩選
python cli/commands.py --config list --exchange backpack

# 按策略篩選  
python cli/commands.py --config list --strategy grid
```

輸出示例：
```
可用配置列表:
├── backpack_ETH_USDC_perp_grid.json (活躍)
├── backpack_SOL_USDC_spot_grid.json (活躍)
└── aster_BTC_USDT_perp_standard.json (活躍)

模板列表:
├── backpack_perp_grid.json
├── backpack_spot_grid.json
├── aster_perp_standard.json
└── paradex_perp_grid.json
```

### 2. 創建新配置

#### 基於模板創建（推薦）

```bash
# 創建 Backpack ETH/USDC 永續網格配置
python cli/commands.py --config create \
  --template backpack_perp_grid \
  --name "我的 ETH 網格" \
  --symbol ETH_USDC_PERP
```

#### 交互式創建

```bash
# 啟動交互式配置向導
python cli/commands.py --config create --interactive
```

向導會詢問：
1. 選擇交易所
2. 選擇交易對
3. 選擇策略類型
4. 配置策略參數
5. 設置風險管理參數

### 3. 編輯配置

```bash
# 編輯指定配置
python cli/commands.py --config edit backpack_ETH_USDC_perp_grid.json
```

### 4. 使用配置運行

```bash
# 使用指定配置啟動守護進程
.venv/bin/python3 core/daemon_manager.py start \
  --config config/active/backpack_ETH_USDC_perp_grid.json \
  --daemon
```

### 5. 配置驗證

```bash
# 驗證配置文件是否有效
python cli/commands.py --config validate backpack_ETH_USDC_perp_grid.json
```

## 進階使用

### 配置文件結構

每個配置文件包含四個部分：

```json
{
  "metadata": {
    "name": "配置名稱",
    "description": "配置描述", 
    "exchange": "backpack",
    "symbol": "ETH_USDC_PERP",
    "market_type": "perp",
    "strategy": "perp_grid"
  },
  "daemon_config": {
    "python_path": ".venv/bin/python3",
    "log_dir": "logs",
    "auto_restart": true
  },
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}"
  },
  "strategy_config": {
    "grid_upper_price": 3300,
    "grid_lower_price": 2750,
    "grid_num": 50
  }
}
```

### 環境變量使用

配置文件支持環境變量替換，格式為 `${VARIABLE_NAME}`：

```json
{
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}"
  }
}
```

設置環境變量：
```bash
export BACKPACK_KEY="your_api_key_here"
export BACKPACK_SECRET="your_secret_key_here"
```

### 配置管理命令

#### 備份配置
```bash
# 備份當前配置
python cli/commands.py --config backup backpack_ETH_USDC_perp_grid.json

# 查看備份列表
python cli/commands.py --config list-backups
```

#### 恢復配置
```bash
# 從備份恢復
python cli/commands.py --config restore backup_20251126_163000.json
```

#### 複製配置
```bash
# 複製現有配置並修改參數
python cli/commands.py --config copy \
  --source backpack_ETH_USDC_perp_grid.json \
  --target backpack_ETH_USDC_perp_grid_v2.json \
  --modify "grid_num=100" "max_position=5.0"
```

#### 刪除配置
```bash
# 刪除配置（會確認）
python cli/commands.py --config delete backpack_ETH_USDC_perp_grid.json
```

## 實用場景

### 場景 1: 多交易對網格交易

為不同交易對創建專用配置：

```bash
# ETH 網格 - 保守參數
python cli/commands.py --config create \
  --template backpack_perp_grid \
  --name "ETH 保守網格" \
  --symbol ETH_USDC_PERP \
  --params "grid_num=30" "max_position=1.0"

# SOL 網格 - 激進參數  
python cli/commands.py --config create \
  --template backpack_perp_grid \
  --name "SOL 激進網格" \
  --symbol SOL_USDC_PERP \
  --params "grid_num=100" "max_position=5.0"
```

### 場景 2: 風險級別管理

為同一交易對創建不同風險級別的配置：

```bash
# 低風險配置
python cli/commands.py --config create \
  --template backpack_perp_grid \
  --name "ETH 低風險" \
  --symbol ETH_USDC_PERP \
  --params "max_position=0.5" "grid_num=20"

# 高風險配置
python cli/commands.py --config create \
  --template backpack_perp_grid \
  --name "ETH 高風險" \
  --symbol ETH_USDC_PERP \
  --params "max_position=3.0" "grid_num=80"
```

### 場景 3: 多交易所套利

在不同交易所創建相似策略：

```bash
# Backpack 配置
python cli/commands.py --config create \
  --template backpack_perp_standard \
  --name "Backpack ETH 做市" \
  --symbol ETH_USDC_PERP

# Aster 配置
python cli/commands.py --config create \
  --template aster_perp_standard \
  --name "Aster ETH 做市" \
  --symbol ETHUSDT
```

## 配置參數詳解

### 網格策略參數

| 參數 | 說明 | 默認值 | 建議範圍 |
|------|------|--------|----------|
| `grid_upper_price` | 網格上限價格 | 自動計算 | 當前價格 + 5-10% |
| `grid_lower_price` | 網格下限價格 | 自動計算 | 當前價格 - 5-10% |
| `grid_num` | 網格數量 | 10 | 10-100 |
| `grid_mode` | 網格模式 | "arithmetic" | "arithmetic", "geometric" |
| `grid_type` | 網格類型 | "neutral" | "neutral", "long", "short" |
| `max_position` | 最大持倉 | 1.0 | 根據資金量決定 |

### 永續做市參數

| 參數 | 說明 | 默認值 | 建議範圍 |
|------|------|--------|----------|
| `base_spread_percentage` | 基礎價差百分比 | 0.5 | 0.1-2.0 |
| `target_position` | 目標持倉 | 0.0 | -1.0 到 1.0 |
| `max_position` | 最大持倉 | 1.0 | 根據資金量決定 |
| `stop_loss` | 止損閾值 | null | 負值，如 -100 |
| `take_profit` | 止盈閾值 | null | 正值，如 200 |

### 守護進程參數

| 參數 | 說明 | 默認值 |
|------|------|--------|
| `health_check_interval` | 健康檢查間隔（秒） | 30 |
| `max_restart_attempts` | 最大重啟次數 | 3 |
| `restart_delay` | 重啟延遲（秒） | 60 |
| `memory_limit_mb` | 內存限制（MB） | 2048 |

## 故障排除

### 常見問題

#### 1. 配置驗證失敗
```
錯誤: 配置驗證失敗: grid_upper_price 必須大於 grid_lower_price
```

**解決方案**: 檢查網格上下限設定，確保上限 > 下限

#### 2. 環境變量未設置
```
錯誤: 環境變量 BACKPACK_KEY 未設置
```

**解決方案**: 設置環境變量或在配置文件中直接指定值

#### 3. 守護進程啟動失敗
```
錯誤: 找不到配置文件
```

**解決方案**: 檢查配置文件路徑是否正確，使用絕對路徑

#### 4. 策略參數無效
```
錯誤: max_position 必須大於 0
```

**解決方案**: 檢查策略參數是否符合要求

### 調試技巧

#### 1. 查看詳細錯誤信息
```bash
# 使用 --verbose 參數查看詳細信息
python cli/commands.py --config validate config.json --verbose
```

#### 2. 檢查配置文件語法
```bash
# 使用 JSON 驗證工具
python -m json.tool config.json
```

#### 3. 查看守護進程日誌
```bash
# 查看最新日誌
tail -f logs/$(date +%Y-%m-%d)/daemon.log
```

## 最佳實踐

### 1. 配置命名規範

使用描述性的名稱：
- ✅ `backpack_ETH_USDC_perp_grid_conservative.json`
- ✅ `aster_BTC_USDT_perp_standard_aggressive.json`
- ❌ `config1.json`
- ❌ `test.json`

### 2. 參數調整建議

#### 新手建議
- 從小持倉開始（max_position: 0.1-0.5）
- 使用較少的網格數量（grid_num: 10-20）
- 設置合理的止損（stop_loss: -50 到 -100）

#### 進階用戶
- 根據波動率調整網格數量
- 使用不同的網格類型（long/short）
- 動態調整參數

### 3. 風險管理

#### 資金管理
- 不要在單個配置中投入過多資金
- 分散到不同交易對和策略
- 定期檢查持倉情況

#### 監控建議
- 設置合理的健康檢查間隔
- 監控內存和 CPU 使用
- 定期備份重要配置

### 4. 配置維護

#### 定期任務
- 每月檢查配置是否需要更新
- 備份重要的配置文件
- 清理不再使用的配置

#### 版本控制
- 將配置文件納入版本控制（排除敏感信息）
- 記錄配置變更原因
- 標記成功的配置版本

## 進階功能

### 1. 配置繼承

創建基礎配置，其他配置繼承並覆蓋特定參數：

```json
// base_config.json
{
  "daemon_config": {
    "python_path": ".venv/bin/python3",
    "auto_restart": true
  },
  "strategy_config": {
    "max_position": 1.0
  }
}

// derived_config.json  
{
  "extends": "base_config.json",
  "strategy_config": {
    "max_position": 2.0  // 覆蓋基礎配置
  }
}
```

### 2. 配置模板變量

在模板中使用變量：

```json
{
  "strategy_config": {
    "grid_upper_price": "${CURRENT_PRICE * 1.1}",
    "grid_lower_price": "${CURRENT_PRICE * 0.9}"
  }
}
```

### 3. 條件配置

根據市場條件自動選擇配置：

```bash
# 根據波動率選擇配置
python cli/commands.py --config auto-select \
  --symbol ETH_USDC_PERP \
  --condition "volatility > 2%:high_volatility_config.json,default_config.json"
```

## 支持和反饋

如果遇到問題或有建議：

1. 查看本文檔的故障排除部分
2. 檢查系統日誌文件
3. 在項目 GitHub 倉庫提交 Issue
4. 聯繫技術支持團隊

---

**注意**: 本指南會隨系統更新而持續完善，建議定期查看最新版本。