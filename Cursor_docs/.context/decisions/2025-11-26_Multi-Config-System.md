# 多配置管理系統實現

## 背景
用戶需要根據不同交易所和交易對有獨立的配置文件，希望能夠動態選擇運行哪個配置，並需要模板方便修改。

## 決策摘要
1. **配置文件結構設計**
   - 採用混合命名規範：`exchange_trading_pair_market_type_strategy.json`
   - 四部分配置結構：metadata, daemon_config, exchange_config, strategy_config
   - 支持環境變量展開：`${VARIABLE_NAME}` 格式

2. **目錄結構組織**
   - `config/templates/` - 配置模板文件
   - `config/active/` - 活躍配置文件
   - `config/archived/` - 歸檔配置文件

3. **核心組件實現**
   - `ConfigManager` 類：完整的配置生命周期管理
   - 修改 `TradingBotDaemon` 類：支持多配置格式檢測和加載
   - CLI 配置管理命令：創建、驗證、列表、運行配置

## 操作流程
1. **創建配置**：從模板創建 → 參數替換 → 驗證 → 保存到 active 目錄
2. **運行配置**：檢測格式 → 驗證配置 → 構建 bot_args → 啟動守護進程
3. **管理配置**：列出所有配置 → 驗證配置 → 備份/恢復 → 歸檔舊配置

## 風險與建議
- **環境變量安全**：API 密鑰必須使用環境變量格式，不允許硬編碼
- **配置驗證**：啟動前必須通過完整驗證，包含類型檢查和範圍驗證
- **向後兼容**：保持對原有 `daemon_config.json` 格式的支持

## 常見操作問答
- **如何創建新配置？**
  使用 CLI 選項 11 → 配置管理 → 從模板創建新配置
- **如何運行特定配置？**
  `.venv/bin/python3 core/daemon_manager.py start --config config/active/your_config.json`
- **配置驗證失敗怎麼辦？**
  檢查 API 密鑰是否使用環境變量格式，確認參數類型和範圍正確

## 本次代碼更新概括
1. **core/config_manager.py**：完整的配置管理系統實現（550行）
   - ConfigManager 類：配置文件的完整生命周期管理
   - ConfigInfo 和 ValidationResult 類：數據結構定義
   - 環境變量展開、配置驗證、模板處理功能

2. **core/daemon_manager.py**：守護進程管理器修改（200行新增）
   - _is_multi_config_format()：檢測新配置格式
   - _load_multi_config()：加載和驗證多配置
   - _build_bot_args()：將策略配置轉換為 CLI 參數

3. **cli/commands.py**：CLI 配置管理命令（200行新增）
   - config_list_command()：列出所有配置文件
   - config_create_command()：從模板創建配置
   - config_validate_command()：驗證配置文件
   - config_run_command()：使用配置運行機器人

4. **config/templates/**：5個交易所模板文件
   - backpack_spot_grid.json, backpack_perp_grid.json
   - aster_perp_grid.json, paradex_perp_grid.json, lighter_perp_grid.json

5. **docs/**：完整文檔體系
   - multi_config_design.md：系統設計文檔
   - multi_config_implementation_plan.md：實現計劃
   - multi_config_user_guide.md：用戶使用指南
   - multi_config_architecture.md：系統架構文檔

### 涉及檔案
- `core/config_manager.py`
- `core/daemon_manager.py`
- `cli/commands.py`
- `config/templates/*.json`
- `docs/multi_config_*.md`