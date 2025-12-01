# 配置管理指南

## 📋 文檔信息

- **日期**：2025-12-01
- **版本**：1.0
- **目標**：說明 Backpack-MM-Simple 系統中的配置文件結構和管理方法
- **最後審查**：2025-12-01

---

## 🔧 配置管理系統概述

### `core/config_manager.py` - 配置管理器

**用途：提供配置文件的完整生命周期管理**

- **功能**：配置文件的創建、讀取、驗證、備份和恢復
- **特點**：
  - 支持多層級配置目錄結構（templates/、active/、archived/）
  - 環境變量展開與驗證機制
  - 配置文件驗證和錯誤檢查
  - 配置備份和恢復功能
  - 基於模板的配置創建

---

## 📁 配置目錄結構

```
config/
├── templates/          # 配置模板
│   ├── backpack_perp_grid.json
│   ├── backpack_spot_grid.json
│   ├── aster_perp_grid.json
│   ├── lighter_perp_grid.json
│   └── paradex_perp_grid.json
├── active/             # 當前使用的配置
│   ├── bp_sol_01.json
│   ├── bp_eth_02.json
│   └── backpack_eth_usdc_perp_grid.json
└── archived/           # 已歸檔的配置
    └── ...
```

---

## 🔧 配置文件結構

### 基本配置結構

```json
{
  "metadata": {
    "name": "配置名稱",
    "instance_id": "實例唯一標識",
    "exchange": "backpack",
    "symbol": "SOL_USDC_PERP",
    "market_type": "perp",
    "strategy": "perp_grid",
    "version": "1.0.0",
    "created_at": "2025-12-01T00:00:00",
    "updated_at": "2025-12-01T00:00:00"
  },
  "daemon_config": {
    "python_path": ".venv/bin/python3",
    "script_path": "run.py",
    "working_dir": ".",
    "log_dir": "logs/bp_sol_01",
    "db_path": "database/bp_sol_01.db",
    "web_port": 5001,
    "max_restart_attempts": 3,
    "restart_delay": 60,
    "health_check_interval": 30,
    "memory_limit_mb": 2048,
    "cpu_limit_percent": 80,
    "auto_restart": true,
    "log_cleanup_interval": 86400,
    "log_retention_days": 2,
    "bot_args": [...]
  },
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}",
    "base_url": "https://api.backpack.work"
  },
  "strategy_config": {
    "grid_upper_price": 160,
    "grid_lower_price": 140,
    "grid_num": 20,
    "grid_mode": "arithmetic",
    "grid_type": "neutral"
  }
}
```

---

## 🔧 環境變量處理

### 支持的格式

1. **基本環境變量**：`${VARIABLE_NAME}`
2. **帶默認值**：`${VARIABLE:-default_value}`

### 敏感環境變量

系統會特別處理以下敏感環境變量：
- `API_KEY`
- `SECRET_KEY`
- `PRIVATE_KEY`
- `PASSWORD`
- `TOKEN`

如果這些變量未設置且沒有默認值，系統會拋出錯誤。

---

## 🔧 配置驗證

### 驗證規則

配置管理器提供以下驗證規則：

#### 元數據驗證
- **必需字段**：name, exchange, symbol, market_type, strategy
- **有效值**：
  - exchange: ["backpack", "aster", "paradex", "lighter"]
  - market_type: ["spot", "perp"]
  - strategy: ["standard", "grid", "perp_grid", "maker_hedge"]

#### 守護進程配置驗證
- **必需字段**：python_path, script_path
- **數值範圍**：
  - max_restart_attempts: 1-10
  - restart_delay: 10-300
  - health_check_interval: 10-300
  - memory_limit_mb: 512-8192
  - cpu_limit_percent: 10-100

#### 策略配置驗證
- **網格策略**：
  - grid_upper_price/grid_lower_price: 必須 > 0
  - grid_num: 2-200
  - grid_mode: ["arithmetic", "geometric"]
  - grid_type: ["neutral", "long", "short"]
- **永續策略**：
  - max_position: 必須 > 0
  - stop_loss: 建議為負值
  - take_profit: 建議為正值

---

## 🔧 配置管理 API

### 基本操作

```python
from core.config_manager import ConfigManager

# 初始化配置管理器
config_manager = ConfigManager()

# 列出所有配置
configs = config_manager.list_configs()

# 加載配置
config_data = config_manager.load_config("config/active/bp_sol_01.json")

# 保存配置
config_manager.save_config("config/active/new_config.json", config_data)

# 驗證配置
result = config_manager.validate_config(config_data)
```

### 模板操作

```python
# 從模板創建配置
config_data = config_manager.create_from_template(
    "backpack_perp_grid",
    "My SOL Grid",
    params={
        "symbol": "SOL_USDC_PERP",
        "grid_upper_price": 160,
        "grid_lower_price": 140,
        "grid_num": 20
    }
)

# 直接創建配置文件
config_path = config_manager.create_config_from_template(
    "backpack_perp_grid",
    "my_sol_grid.json",
    symbol="SOL_USDC_PERP",
    grid_upper_price=160,
    grid_lower_price=140,
    grid_num=20
)
```

### 備份和恢復

```python
# 備份配置
backup_path = config_manager.backup_config("config/active/bp_sol_01.json")

# 恢復配置
config_manager.restore_config(backup_path, "config/active/restored_config.json")
```

---

## 🔧 多實例配置

### 實例隔離配置

每個實例需要獨立的配置：

```json
{
  "metadata": {
    "instance_id": "bp_sol_01"
  },
  "daemon_config": {
    "log_dir": "logs/bp_sol_01",
    "db_path": "database/bp_sol_01.db",
    "web_port": 5001
  }
}
```

### 配置文件命名規範

建議使用以下命名規範：
- `<exchange>_<symbol>_<number>.json`
- 例如：`bp_sol_01.json`, `bp_eth_02.json`

---

## 🔧 配置最佳實踐

### 1. 安全性
- 使用環境變量存儲敏感信息（API 密鑰等）
- 不要將 `.env` 文件提交到版本控制
- 使用 `chmod 600 .env` 限制文件權限

### 2. 可維護性
- 使用描述性的配置名稱
- 定期備份重要配置
- 使用版本控制管理配置文件變更

### 3. 多實例管理
- 確保每個實例有唯一的 `instance_id`
- 使用不同的端口和數據庫路徑
- 為不同實例使用不同的日誌目錄

---

## 🔧 故障排查

### 常見問題

**Q1: 配置文件驗證失敗**
```
A: 檢查配置文件是否符合驗證規則，特別是必需字段和數值範圍
```

**Q2: 環境變量未展開**
```
A: 確認環境變量已正確設置，檢查 .env 文件或系統環境變量
```

**Q3: 配置文件備份失敗**
```
A: 檢查歸檔目錄權限，確保有足夠的磁盤空間
```

---

## 🔧 相關文檔

- [多實例實施指南](../Cursor_docs/.context/sessions/multi_instance_implementation_guide.md) - 詳細的多實例技術實施文檔
- [系統管理文檔](system/Fork_README.md) - 系統概述和使用指南

---

**文檔版本**：1.0  
**作者**：Kilo Code  
**最後更新**：2025-12-01  
**審閱狀態**：已審查並修正