# 多配置管理系統設計文檔

## 概述

本文檔描述了為 Backpack-MM-Simple 項目設計的多配置管理系統，允許用戶根據不同交易所和交易對創建和管理獨立的配置文件。

## 設計目標

1. **靈活性**: 支持不同交易所、交易對和策略的獨立配置
2. **易用性**: 提供模板和簡化的配置管理界面
3. **可維護性**: 清晰的配置結構和版本管理
4. **安全性**: 配置驗證和備份機制

## 目錄結構設計

```
config/
├── daemon_config.json                    # 默認守護進程配置
├── templates/                           # 配置模板目錄
│   ├── backpack_spot_standard.json
│   ├── backpack_spot_grid.json
│   ├── backpack_perp_standard.json
│   ├── backpack_perp_grid.json
│   ├── aster_perp_standard.json
│   ├── aster_perp_grid.json
│   ├── paradex_perp_standard.json
│   ├── paradex_perp_grid.json
│   └── lighter_perp_standard.json
├── active/                             # 活躍配置目錄
│   ├── backpack_ETH_USDC_perp_grid.json
│   ├── backpack_SOL_USDC_spot_grid.json
│   └── aster_BTC_USDT_perp_grid.json
└── archived/                           # 歸檔配置目錄
    └── (用戶自定義的歷史配置)
```

## 配置文件命名規範

### 模板文件命名
格式: `{exchange}_{market_type}_{strategy}.json`

示例:
- `backpack_spot_standard.json` - Backpack 現貨標準策略
- `backpack_perp_grid.json` - Backpack 永續合約網格策略
- `aster_perp_grid.json` - Aster 永續合約網格策略

### 活躍配置文件命名
格式: `{exchange}_{symbol}_{market_type}_{strategy}.json`

示例:
- `backpack_ETH_USDC_perp_grid.json` - Backpack ETH/USDC 永續網格
- `aster_BTC_USDT_perp_standard.json` - Aster BTC/USDT 永續標準

## 配置文件結構

每個配置文件包含四個主要部分：

```json
{
  "metadata": {
    "name": "Backpack ETH/USDC 永續網格",
    "description": "ETH/USDC 永續合約網格交易策略",
    "exchange": "backpack",
    "symbol": "ETH_USDC_PERP",
    "market_type": "perp",
    "strategy": "perp_grid",
    "created_at": "2025-11-26T16:00:00Z",
    "updated_at": "2025-11-26T16:00:00Z",
    "version": "1.0.0"
  },
  "daemon_config": {
    "python_path": ".venv/bin/python3",
    "script_path": "run.py",
    "working_dir": ".",
    "log_dir": "logs",
    "max_restart_attempts": 3,
    "restart_delay": 60,
    "health_check_interval": 30,
    "memory_limit_mb": 2048,
    "cpu_limit_percent": 80,
    "auto_restart": true,
    "log_cleanup_interval": 86400,
    "log_retention_days": 2
  },
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}",
    "base_url": "https://api.backpack.exchange",
    "api_version": "v1",
    "default_window": "5000"
  },
  "strategy_config": {
    "grid_upper_price": 3300,
    "grid_lower_price": 2750,
    "grid_num": 50,
    "grid_mode": "geometric",
    "grid_type": "long",
    "max_position": 2.4,
    "stop_loss": 600,
    "take_profit": 1200,
    "boundary_action": "emergency_close",
    "boundary_tolerance": 0.001,
    "enable_boundary_check": true,
    "duration": 1209600,
    "interval": 90
  }
}
```

## 配置管理功能

### 1. 配置列表和選擇
- 列出所有可用配置
- 按交易所、策略、交易對篩選
- 顯示配置狀態（活躍/歸檔）

### 2. 配置創建
- 基於模板創建新配置
- 交互式配置向導
- 配置參數驗證

### 3. 配置管理
- 編輯現有配置
- 複製配置
- 刪除配置
- 備份和恢復

### 4. 配置驗證
- 參數類型驗證
- 參數範圍驗證
- 依賴關係檢查
- 交易所兼容性檢查

## 實現計劃

### 階段 1: 基礎結構
1. 創建目錄結構
2. 設計配置模板
3. 實現配置文件讀寫功能

### 階段 2: 配置管理
1. 實現配置管理器類
2. 添加配置驗證功能
3. 創建 CLI 命令接口

### 階段 3: 集成和測試
1. 修改 daemon_manager.py 支持動態配置
2. 集成到現有 CLI 系統
3. 全面測試

## CLI 命令設計

### 配置管理命令
```bash
# 列出所有配置
python cli/commands.py --config list

# 創建新配置（基於模板）
python cli/commands.py --config create --template backpack_perp_grid --symbol ETH_USDC_PERP

# 編輯配置
python cli/commands.py --config edit backpack_ETH_USDC_perp_grid.json

# 刪除配置
python cli/commands.py --config delete backpack_ETH_USDC_perp_grid.json

# 選擇配置運行
python cli/commands.py --config use backpack_ETH_USDC_perp_grid.json

# 驗證配置
python cli/commands.py --config validate backpack_ETH_USDC_perp_grid.json
```

### 守護進程命令
```bash
# 使用指定配置啟動守護進程
.venv/bin/python3 core/daemon_manager.py start --config config/active/backpack_ETH_USDC_perp_grid.json --daemon

# 查看當前使用的配置
.venv/bin/python3 core/daemon_manager.py status --config
```

## 配置模板詳細設計

### 1. Backpack 永續網格模板 (backpack_perp_grid.json)
- 交易所: Backpack
- 市場類型: 永續合約
- 策略: 網格交易
- 默認參數: 適合 ETH/USDC 等主流交易對

### 2. Backpack 現貨網格模板 (backpack_spot_grid.json)
- 交易所: Backpack
- 市場類型: 現貨
- 策略: 網格交易
- 默認參數: 適合 SOL_USDC 等高波動性交易對

### 3. Aster 永續標準模板 (aster_perp_standard.json)
- 交易所: Aster
- 市場類型: 永續合約
- 策略: 標準做市
- 默認參數: 適合 BTC/USDT 等穩定交易對

## 環境變量支持

配置文件支持環境變量替換，格式為 `${VARIABLE_NAME}`：

```json
{
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}"
  }
}
```

## 配置版本管理

每個配置文件包含版本信息：
- `version`: 配置格式版本
- `created_at`: 創建時間
- `updated_at`: 最後更新時間

## 安全考慮

1. **API 密鑰安全**: 使用環境變量，不直接存儲在配置中
2. **配置備份**: 自動備份重要配置到 archived 目錄
3. **配置驗證**: 防止無效配置導致系統錯誤
4. **權限控制**: 配置文件適當的文件權限設置

## 向後兼容性

1. 保持現有 `daemon_config.json` 作為默認配置
2. 支持舊版配置格式的自動升級
3. 提供配置遷移工具

## 擴展性設計

1. **插件化策略**: 支持自定義策略配置模板
2. **多交易所擴展**: 易於添加新交易所支持
3. **配置繼承**: 支持配置繼承和覆蓋機制
4. **配置分享**: 支持配置導出和導入功能

## 測試策略

1. **單元測試**: 配置讀寫、驗證功能
2. **集成測試**: 與現有系統的集成
3. **端到端測試**: 完整的配置管理工作流
4. **性能測試**: 大量配置文件的管理性能

## 文檔和用戶指南

1. **快速開始指南**: 如何創建和使用第一個配置
2. **配置參考**: 所有配置參數的詳細說明
3. **最佳實踐**: 配置管理的建議和技巧
4. **故障排除**: 常見問題和解決方案