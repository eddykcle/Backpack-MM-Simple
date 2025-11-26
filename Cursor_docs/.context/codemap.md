# Backpack-MM-Simple 程式碼地圖

本文件詳細介紹了 `Backpack-MM-Simple` 專案，旨在幫助 AI 助理和開發人員理解其架構、組件和執行流程。

## 1. 專案概覽

一個支援多交易所、多策略的加密貨幣交易機器人框架。它支援在 Backpack、Aster、Paradex 和 Lighter 等交易所上執行做市、對沖和網格交易策略。此系統設計成可擴充以支援新的交易所和策略。

## 2. 核心組件與目錄結構

以下是主要目錄及其職責的詳解：

- **`/` (根目錄)**
    - `run.py`: 應用程式的主要進入點。處理命令列參數解析，並啟動所選模式（Web UI、CLI 或直接執行策略）。
    - `config.py`: 中央設定檔。從環境變數（`.env` 檔案）載入 API 金鑰、端點和其他設定。
    - `requirements.txt`: 列出所有 Python 依賴項。
    - `README.md`: 提供總體概覽、設定說明和使用範例。

- **`api/`**: 交易所 API 客戶端
    - `base_client.py`: 一個抽象基礎類別，定義了所有交易所客戶端的通用介面。這確保了與不同交易所互動時的一致性。
    - `bp_client.py`: Backpack 交易所的客戶端。
    - `aster_client.py`: Aster 交易所的客戶端。
    - `paradex_client.py`: Paradex 交易所的客戶端。
    - `lighter_client.py`: Lighter 交易所的客戶端。
    - `auth.py`: 處理 API 認證和請求簽名邏輯。

- **`strategies/`**: 交易邏輯
    - `market_maker.py`: 實現核心的現貨做市策略。
    - `perp_market_maker.py`: 實現永續合約做市策略。
    - `maker_taker_hedge.py`: 一種對沖策略，下一個 maker 單，成交後立即下一個反向的 taker 單。
    - `grid_strategy.py`: 實現現貨網格交易策略。
    - `perp_grid_strategy.py`: 實現永續合約網格交易策略。

- **`core/`**: 核心系統服務
    - `daemon_manager.py`: 一個程序管理器，用於將交易機器人作為背景守護程序運行。它處理啟動、停止、重啟和監控機器人程序。
    - `log_manager.py`: 管理日誌檔案，包括清理舊日誌。
    - `logger.py`: 設定應用程式的日誌系統（使用 `loguru`）。

- **`web/`**: Web 儀表板 (Flask & SocketIO)
    - `server.py`: 提供即時儀表板以監控和控制機器人的 Flask 網頁伺服器。
    - `templates/index.html`: Web UI 的單頁 HTML 模板。
    - `static/`: 包含用於前端的 CSS 和 JavaScript。`app.js` 處理客戶端邏輯和 WebSocket 通訊。

- **`cli/`**: 命令列介面
    - `commands.py`: 實現用於管理機器人的互動式命令列介面。

- **`ws_client/`**: WebSocket 客戶端
    - `client.py`: 一個通用的 WebSocket 客戶端，用於從交易所接收即時數據。

- **`database/`**: 資料庫操作
    - `db.py`: 處理 SQLite 資料庫操作，用於儲存交易歷史和其他數據（可選）。

## 3. 執行流程

應用程式有三種主要執行模式，由 `run.py` 中的命令列參數決定。

### 模式一：Web UI (`python run.py --web`)

1.  `run.py` 解析 `--web` 參數。
2.  它呼叫 `web.server.run_server()`。
3.  Flask/SocketIO 伺服器啟動，提供 `index.html` 頁面。
4.  使用者透過 UI 互動以設定和啟動策略。
5.  呼叫 `server.py` 中的 `/api/start` 端點。
6.  根據使用者輸入建立策略實例（例如 `MarketMaker`）。
7.  策略的 `run()` 方法在一個新的背景執行緒 (`strategy_thread`) 中執行。
8.  另一個執行緒 (`stats_update_thread`) 定期呼叫 `collect_strategy_stats()` 以從運行的策略實例中獲取數據，並透過 WebSocket 發送到前端。
9.  當使用者點擊「停止」時，`/api/stop` 端點會呼叫 `current_strategy` 實例上的 `stop()` 方法。

### 模式二：CLI (`python run.py --cli`)

1.  `run.py` 解析 `--cli` 參數。
2.  它呼叫 `cli.commands.main_cli()`。
3.  顯示一個互動式選單，允許使用者執行諸如檢查餘額、下單或啟動策略等操作。

### 模式三：直接執行 (例如 `python run.py --symbol SOL_USDC ...`)

1.  `run.py` 解析策略參數（例如 `--symbol`, `--spread`, `--strategy`）。
2.  它直接建立相應的策略實例。
3.  它呼叫 `run_strategy_with_signals()`，該函式將策略的 `run()` 方法包裝起來，並帶有訊號處理器以實現優雅關閉（SIGINT, SIGTERM）。
4.  一個輕量級版本的網頁伺服器在背景啟動，以提供健康檢查端點。

## 4. 設定 (`config.py`)

-   設定在 `config.py` 中管理。
-   它使用 `python-dotenv` 從專案根目錄的 `.env` 檔案載入環境變數。
-   它定義了所有支援交易所的 API 金鑰、密鑰和基礎 URL。
-   它還包括代理、資料庫和日誌的設定。

## 5. 策略實作

-   所有策略都繼承自一個基類（雖然不是一個正式的 `BaseStrategy` 類，但它們共享一個通用結構）。`GridStrategy` 繼承自 `MarketMaker`。
-   主要邏輯在 `run()` 方法內，該方法通常包含一個運行指定持續時間的循環。
-   在循環內部，策略會：
    1.  獲取市場數據（報價、訂單簿）。
    2.  獲取帳戶數據（餘額、開放訂單、倉位）。
    3.  根據其邏輯取消和下新訂單（例如 `MarketMaker` 中的 `place_limit_orders()`）。
    4.  處理 WebSocket 訊息以進行即時更新（例如 `on_ws_message()`）。
    5.  計算 PnL 和其他統計數據。
-   `stop()` 方法設定一個旗標 (`self.is_running = False`) 以優雅地退出主循環。

## 6. API 客戶端 (`api/`)

-   `base_client.py` 提供一個 `ABC`，標準化了 `get_balance`, `execute_order`, `get_ticker` 等方法。
-   每個特定於交易所的客戶端（例如 `bp_client.py`）都實現了這些方法。
-   請求在 `auth.py` 或客戶端內部進行簽名。
-   `BPClient` 包含一個重試機制，用於處理速率限制和連線錯誤。
-   透過 `proxy_utils.py` 整合了代理支援，該檔案從環境中讀取 `HTTP_PROXY`/`HTTPS_PROXY`。

## 7. Web 儀表板 (`web/`)

-   一個 Flask 應用程式提供後端。
-   Flask-SocketIO 用於伺服器和瀏覽器之間的即時雙向通訊。
-   **前端 (`static/js/app.js`)**:
    -   透過 WebSocket 連接到伺服器。
    -   處理 UI 事件（按鈕點擊、表單提交）。
    -   向伺服器發送命令（例如，啟動/停止機器人）。
    -   接收並顯示即時的 `stats_update` 事件。
-   **後端 (`server.py`)**:
    -   在一個單獨的執行緒中管理策略實例的生命週期。
    -   提供 HTTP 端點（`/api/start`, `/api/stop`, `/api/status`）。
    -   透過 WebSocket 向客戶端廣播統計數據。
    -   包括一個健康檢查端點 (`/health`)，供像 Uptime Kuma 這樣的監控服務使用。

這種結構實現了交易邏輯、交易所通訊和使用者介面之間的明確關注點分離。

## 8. 守護進程管理器 (`core/daemon_manager.py`)

專案包含一個強大的守護進程管理器，允許交易機器人作為背景程序可靠地運行，獨立於使用者的終端會話。這是比使用 `nohup` 或 `screen` 更安全、更穩定的替代方案。

### 主要功能

- **啟動、停止、重啟**: 提供清晰的命令來管理機器人的生命週期 (`python core/daemon_manager.py start/stop/restart`)。
- **守護進程化**: `start --daemon` 命令會分叉 (fork) 程序，使其在背景運行並在終端關閉後繼續存在。
- **程序監控**: 主守護進程循環持續監控交易機器人的子程序。
- **自動重啟**: 如果機器人程序崩潰，守護進程將自動嘗試重啟它，最多可達設定的次數 (`max_restart_attempts`)。
- **健康檢查**: 定期檢查系統資源，如磁碟空間、記憶體使用和系統負載，以防止問題發生。
- **日誌記錄**: 將機器人程序的 `stdout` 和 `stderr` 捕獲到每日日誌檔案中 (例如 `logs/2025-11-26/bot_stdout.log`)。
- **PID 管理**: 使用 PID 檔案 (`logs/bot.pid`, `logs/daemon.pid`) 來追蹤運行中的程序，防止多個實例運行。

### 運作方式

1.  **設定**: 守護進程的行為在 `config/daemon_config.json` 中設定。此檔案指定了 Python 可執行檔、腳本路徑 (`run.py`)、機器人參數和資源限制。
2.  **啟動守護進程**:
    -   `python core/daemon_manager.py start --daemon` 啟動管理器。
    -   管理器程序與終端分離並在背景運行。
    -   然後，它使用其設定中指定的命令（例如 `python run.py --symbol ...`）作為子程序啟動實際的交易機器人。
3.  **監控循環**:
    -   守護進程進入一個 `_main_loop`，在此循環中定期檢查機器人子程序是否仍在運行。
    -   如果程序已終止，它會啟動重啟邏輯。
    -   它還執行定期的健康檢查。
4.  **停止守護進程**:
    -   `python core/daemon_manager.py stop` 向守護進程發送 SIGTERM 訊號。
    -   守護進程首先會優雅地終止它所管理的機器人子程序，然後關閉自己。它包含超時機制，以在程序無響應時強制終止。

此守護進程提供了一種生產級的方式來管理交易機器人，確保高可用性和適當的日誌記錄。