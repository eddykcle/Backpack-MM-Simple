Codemap概覽
===========

分層架構  
- `run.py` 為統一入口，向下分為介面層（Web/CLI/Daemon）、策略層（`strategies/`）、交易所接入層（`api/`、`ws_client/`）與資料/觀測層（`database/`、`core/`、`monitoring/`）。  
- 核心資料流：使用者透過 Web/CLI/Daemon 觸發 `run.py` → 建立策略實例（MarketMaker / Perp / Grid 等）→ 透過 REST API 客戶端與 WebSocket 交互 → 選用資料庫/監控/日誌 → Web/SocketIO 與 CLI 回饋狀態。

啟動與執行  
- `run.py` 處理命令列參數、重平衡校驗、API 憑證，並啟動 Web (`--web`)、CLI (`--cli`) 或直接執行策略；`StrategySignalHandler` 確保 SIGTERM/SIGINT 優雅退出。  
- 守護與自動重啟：`core/daemon_manager.TradingBotDaemon` 讀取 `config/daemon_config.json`，提供啟停、重啟、健康檢查、CPU/MEM 限制與 bot 參數管理。

策略層  
- `strategies/market_maker.py`：現貨做市，整合多交易所客戶端、重平衡與可選 SQLite 紀錄；Backpack 結合 WebSocket 實時行情。  
- `strategies/perp_market_maker.py` 與 `maker_taker_hedge.py`：永續倉位控制、止損/止盈、inventory skew；`grid_strategy.py` / `perp_grid_strategy.py` 提供算術／幾何、auto price、long/short 模式。  
- 所有策略透過 `exchange_config` 注入客戶端、可選 Database，並以 `core.logger` 記錄運行情況。

交易所與數據  
- `api/base_client.py` 定義統一資料結構與方法；`api/bp_client.py`、`aster_client.py`、`paradex_client.py`、`lighter_client.py` 具體實作簽名、重試與代理；`api/example_exchange_client.py` 提供擴充模板。  
- `ws_client/client.py` 的 `BackpackWebSocket` 處理連線、心跳、REST 備援、訂單更新與波動率計算。

共用基礎
- `config.py` 載入 `.env`，集中代理、資料庫與交易所設定；`database/db.py` 封裝 SQLite（訂單、統計、重平衡、行情）；`utils/helpers.py` 提供精度/波動計算。
- `core/log_manager.py` 與 `core/logger.py` 提供結構化日誌、基於時間的輪轉、日期目錄結構（logs/YYYY-MM-DD/）、自動清理超過保留天數的舊日誌目錄、壓縮舊日誌、PID 管理。

介面與監控  
- `web/server.py` 提供 Flask+SocketIO 控制枱、健康檢查與背景執行策略；`cli/commands.py` 提供互動菜單與工具指令。  
- `monitoring/monitoring.py` 監控系統資源與 `run.py` 進程，透過 Email/Telegram/Webhook 告警；健康資訊與日誌輸出位於 `logs/`。

