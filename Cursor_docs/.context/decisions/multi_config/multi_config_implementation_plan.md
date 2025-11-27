# 多配置管理系統實施計劃

## 實施概述

基於設計文檔，本實施計劃詳細描述了多配置管理系統的具體實施步驟和技術細節。

## 實施階段

### 階段 1: 基礎結構和模板創建

#### 1.1 目錄結構創建
```bash
mkdir -p config/templates
mkdir -p config/active  
mkdir -p config/archived
```

#### 1.2 配置模板文件
需要創建以下模板文件：

1. **backpack_perp_grid.json** - Backpack 永續網格模板
2. **backpack_spot_grid.json** - Backpack 現貨網格模板  
3. **backpack_perp_standard.json** - Backpack 永續標準模板
4. **aster_perp_grid.json** - Aster 永續網格模板
5. **aster_perp_standard.json** - Aster 永續標準模板
6. **paradex_perp_grid.json** - Paradex 永續網格模板
7. **paradex_perp_standard.json** - Paradex 永續標準模板
8. **lighter_perp_standard.json** - Lighter 永續標準模板

#### 1.3 配置管理器基礎類
創建 `core/config_manager.py` 文件，包含：
- `ConfigManager` 類
- 基礎的配置讀寫功能
- 路徑管理功能

### 階段 2: 配置管理核心功能

#### 2.1 ConfigManager 類完整實現
```python
class ConfigManager:
    def __init__(self, config_dir="config")
    def list_configs(self, filter_by=None)
    def load_config(self, config_name)
    def save_config(self, config_name, config_data)
    def create_from_template(self, template_name, target_name, params)
    def validate_config(self, config_data)
    def delete_config(self, config_name)
    def backup_config(self, config_name)
    def restore_config(self, backup_name)
```

#### 2.2 配置驗證器
創建 `utils/config_validator.py` 文件：
- 參數類型驗證
- 參數範圍驗證
- 交易所兼容性檢查
- 策略參數依賴檢查

#### 2.3 環境變量處理
實現 `${VARIABLE_NAME}` 格式的環境變量替換功能

### 階段 3: CLI 集成

#### 3.1 擴展 CLI 命令
修改 `cli/commands.py` 添加配置管理命令：
```python
def config_list_command()
def config_create_command()
def config_edit_command()
def config_delete_command()
def config_use_command()
def config_validate_command()
```

#### 3.2 交互式配置向導
創建配置創建的交互式界面：
- 交易所選擇
- 交易對選擇
- 策略選擇
- 參數配置

### 階段 4: 守護進程集成

#### 4.1 修改 daemon_manager.py
- 支持動態配置文件路徑
- 配置文件參數解析
- 配置驗證集成

#### 4.2 啟動命令修改
```bash
# 新的啟動方式
python core/daemon_manager.py start --config config/active/backpack_ETH_USDC_perp_grid.json --daemon

# 保持向後兼容
python core/daemon_manager.py start --daemon  # 使用默認 daemon_config.json
```

## 技術實施細節

### 配置文件結構實現

#### 元數據結構
```json
{
  "metadata": {
    "name": "配置顯示名稱",
    "description": "配置描述",
    "exchange": "backpack|aster|paradex|lighter",
    "symbol": "交易對符號",
    "market_type": "spot|perp", 
    "strategy": "standard|grid|perp_grid|maker_hedge",
    "created_at": "ISO 8601 時間戳",
    "updated_at": "ISO 8601 時間戳",
    "version": "配置格式版本",
    "author": "配置創建者",
    "tags": ["標籤1", "標籤2"]
  }
}
```

#### 守護進程配置
```json
{
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
  }
}
```

#### 交易所配置
```json
{
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}",
    "base_url": "https://api.backpack.exchange",
    "api_version": "v1",
    "default_window": "5000"
  }
}
```

#### 策略配置
```json
{
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

### 配置驗證規則

#### 通用驗證
- 必需字段檢查
- 數據類型驗證
- 數值範圍驗證

#### 策略特定驗證
- 網格策略：grid_upper > grid_lower, grid_num >= 2
- 永續策略：max_position > 0
- 止損止盈：stop_loss < 0, take_profit > 0

#### 交易所驗證
- API 密鑰格式檢查
- 交易所特定參數驗證

### 環境變量處理

實現 `expand_env_vars()` 函數：
```python
import re
import os

def expand_env_vars(text):
    """將 ${VAR_NAME} 格式替換為環境變量值"""
    pattern = r'\$\{([^}]+)\}'
    
    def replace_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    return re.sub(pattern, replace_var, text)
```

## 實施順序

### 第一步：基礎結構（預計 2 小時）
1. 創建目錄結構
2. 創建基礎配置模板
3. 實現基礎 ConfigManager 類

### 第二步：核心功能（預計 4 小時）
1. 完善配置讀寫功能
2. 實現配置驗證器
3. 添加環境變量支持
4. 實現配置備份功能

### 第三步：CLI 集成（預計 3 小時）
1. 擴展 CLI 命令
2. 實現交互式配置向導
3. 添加配置管理命令

### 第四步：守護進程集成（預計 2 小時）
1. 修改 daemon_manager.py
2. 實現動態配置加載
3. 測試向後兼容性

### 第五步：測試和文檔（預計 2 小時）
1. 編寫單元測試
2. 集成測試
3. 更新用戶文檔

## 風險評估和緩解

### 風險 1：配置文件格式不兼容
- **緩解**: 實現配置版本管理和自動升級
- **檢測**: 配置加載時的版本檢查

### 風險 2：API 密鑰洩露
- **緩解**: 強制使用環境變量，不在配置中存儲密鑰
- **檢測**: 配置驗證時的密鑰格式檢查

### 風險 3：無效配置導致系統崩潰
- **緩解**: 嚴格的配置驗證和默認值回退
- **檢測**: 啟動前的完整配置驗證

### 風險 4：向後兼容性問題
- **緩解**: 保持舊配置文件支持，提供遷移工具
- **檢測**: 現有用戶配置的兼容性測試

## 成功標準

1. **功能完整性**: 所有設計功能正常工作
2. **向後兼容**: 現有用戶無需修改即可繼續使用
3. **用戶友好**: 提供清晰的 CLI 界面和文檔
4. **穩定性**: 配置錯誤不會導致系統崩潰
5. **可擴展性**: 易於添加新的交易所和策略

## 後續擴展計劃

1. **Web 界面**: 提供基於 Web 的配置管理界面
2. **配置分享**: 支持配置文件的導出和導入
3. **配置繼承**: 支持配置模板繼承和覆蓋
4. **自動化配置**: 基於市場數據的自動配置生成
5. **配置分析**: 配置性能分析和優化建議