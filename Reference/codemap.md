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
    - `example_exchange_client.py`: 交易所客戶端實現範例。
    - `proxy_utils.py`: 代理工具，用於處理 HTTP/HTTPS 代理設置。

- **`strategies/`**: 交易邏輯
    - `market_maker.py`: 實現核心的現貨做市策略。
    - `perp_market_maker.py`: 實現永續合約做市策略。
    - `maker_taker_hedge.py`: 一種對沖策略，下一個 maker 單，成交後立即下一個反向的 taker 單。
    - `grid_strategy.py`: 實現現貨網格交易策略。
    - `perp_grid_strategy.py`: 實現永續合約網格交易策略。

- **`core/`**: 核心系統服務
    - `daemon_manager.py`: 一個程序管理器，用於將交易機器人作為背景守護程序運行。它處理啟動、停止、重啟和監控機器人程序。
    - `config_manager.py`: 多配置管理系統，提供配置文件的創建、讀取、驗證、備份等功能。
    - `log_manager.py`: 高級日誌管理系統，替代 nohup，提供結構化日誌、輪轉和壓縮功能。
    - `logger.py`: 設定應用程式的日誌系統（使用 `loguru`）。
    - `exceptions.py`: 自定義異常類，統一錯誤處理策略。

- **`config/`**: 配置文件管理
    - `daemon_config.json`: 守護進程配置文件（傳統格式）。
    - `templates/`: 配置模板目錄，包含各種策略和交易所的配置模板。
    - `active/`: 當前使用的配置文件目錄。
    - `archived/`: 已歸檔的配置文件目錄。

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

- **`monitoring/`**: 監控系統
    - `monitoring.py`: 系統監控和告警系統，提供系統資源監控、性能監控、告警通知等功能。

- **`utils/`**: 工具模塊
    - `helpers.py`: 輔助函數。
    - `input_validation.py`: 統一輸入驗證框架，用於解決 code review 中識別的輸入驗證不足問題。

- **`test_reports/`**: 測試報告
    - 存放各種測試報告文件。

- **`tests/`**: 測試文件
    - 包含各種測試腳本和測試用例。

## 3. 執行流程

應用程式有多種主要執行模式，由 `run.py` 中的命令列參數決定。

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

### 模式四：守護進程模式 (`python core/daemon_manager.py start --daemon`)

1.  啟動守護進程管理器。
2.  守護進程讀取配置文件（支持傳統格式和新的多配置格式）。
3.  守護進程在背景運行，並啟動交易機器人作為子進程。
4.  守護進程持續監控交易機器人進程，如果崩潰則自動重啟。
5.  定期執行健康檢查和日誌清理。
6.  支持通過 `stop`、`restart` 和 `status` 命令管理守護進程。

## 4. 配置管理系統

專案採用了多層次的配置管理系統：

### 傳統配置格式

- 使用單一配置文件（如 `config/daemon_config.json`）
- 包含守護進程配置和機器人參數
- 適合簡單的部署場景

### 新的多配置格式

- **結構化配置**：分為四個主要部分
  - `metadata`: 配置元數據（名稱、描述、交易所、策略等）
  - `daemon_config`: 守護進程配置
  - `exchange_config`: 交易所特定配置
  - `strategy_config`: 策略特定參數

- **配置目錄結構**：
  - `config/templates/`: 配置模板，用於快速創建新配置
  - `config/active/`: 當前使用的配置文件
  - `config/archived/`: 已歸檔的配置文件

- **環境變量支持**：
  - 支持 `${VARIABLE_NAME}` 格式
  - 支持默認值 `${VARIABLE:-default}`
  - 敏感信息（如 API 密鑰）強制使用環境變量

### 配置管理器 (`core/config_manager.py`)

提供完整的配置生命周期管理：
- 配置文件的讀寫操作
- 配置列表和篩選
- 配置驗證
- 配置備份和恢復
- 環境變量處理

## 5. 策略實作

### 基礎策略類

所有策略都繼承自一個基類（雖然不是一個正式的 `BaseStrategy` 類，但它們共享一個通用結構）。`GridStrategy` 繼承自 `MarketMaker`。

主要邏輯在 `run()` 方法內，該方法通常包含一個運行指定持續時間的循環。

### 現貨網格策略 (`strategies/grid_strategy.py`)

特點：
- 在價格區間內設置多個網格價格點位
- 在每個點位掛限價單
- 買單成交後，在上一個網格點位掛賣單
- 賣單成交後，在下一個網格點位掛買單
- 支持自動借貸功能
- 支持等差和等比網格模式

### 永續合約網格策略 (`strategies/perp_grid_strategy.py`)

特點：
- 支持做多網格、做空網格和中性網格
- 在價格區間內設置多個網格價格點位
- 買入開多後，在上一個網格點位賣出平多
- 賣出開空後，在下一個網格點位買入平空
- 支持邊界檢查和自動處理
- 支持倉位變化檢測和訂單狀態同步

### 策略通用邏輯

在循環內部，策略會：
1. 獲取市場數據（報價、訂單簿）。
2. 獲取帳戶數據（餘額、開放訂單、倉位）。
3. 根據其邏輯取消和下新訂單（例如 `MarketMaker` 中的 `place_limit_orders()`）。
4. 處理 WebSocket 訊息以進行即時更新（例如 `on_ws_message()`）。
5. 計算 PnL 和其他統計數據。
6. `stop()` 方法設定一個旗標 (`self.is_running = False`) 以優雅地退出主循環。

## 6. API 客戶端 (`api/`)

- `base_client.py` 提供一個 `ABC`，標準化了 `get_balance`, `execute_order`, `get_ticker` 等方法。
- 每個特定於交易所的客戶端（例如 `bp_client.py`）都實現了這些方法。
- 請求在 `auth.py` 或客戶端內部進行簽名。
- `BPClient` 包含一個重試機制，用於處理速率限制和連線錯誤。
- 透過 `proxy_utils.py` 整合了代理支援，該檔案從環境中讀取 `HTTP_PROXY`/`HTTPS_PROXY`。

## 7. Web 儀表板 (`web/`)

- 一個 Flask 應用程式提供後端。
- Flask-SocketIO 用於伺服器和瀏覽器之間的即時雙向通訊。
- **前端 (`static/js/app.js`)**:
    -   透過 WebSocket 連接到伺服器。
    -   處理 UI 事件（按鈕點擊、表單提交）。
    -   向伺服器發送命令（例如，啟動/停止機器人）。
    -   接收並顯示即時的 `stats_update` 事件。
- **後端 (`server.py`)**:
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
- **配置支持**: 支持傳統配置格式和新的多配置格式。

### 運作方式

1.  **設定**: 守護進程的行為在 `config/daemon_config.json` 中設定（傳統格式）或通過多配置格式設定。
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

## 9. 日誌管理系統 (`core/log_manager.py`)

專案採用了高級日誌管理系統，替代傳統的 nohup.out 方案：

### 主要功能

- **結構化日誌**: 支持傳統文本日誌和結構化 JSON 日誌格式
- **基於時間的輪轉**: 每日自動創建新的日誌文件，存放在以日期命名的目錄中
- **自動壓縮**: 舊日誌文件自動壓縮為 .gz 格式，節省磁盤空間
- **多級別日誌**: 分別記錄所有級別的日誌和僅錯誤級別的日誌
- **異步處理**: 支持異步日誌寫入，避免阻塞主線程
- **自動清理**: 定期清理超過指定天數的舊日誌文件

### 日誌文件結構

```
logs/
├── 2025-11-26/           # 按日期分組的日誌目錄
│   ├── trading_bot.log           # 主要日誌文件
│   ├── trading_bot_errors.log     # 錯誤日誌文件
│   ├── trading_bot_structured.log # 結構化 JSON 日誌
│   ├── bot_stdout.log            # 機器人標準輸出
│   └── bot_stderr.log            # 機器人錯誤輸出
└── 2025-11-27/           # 第二天的日誌目錄
    └── ...
```

### 進程管理

- **守護進程化**: 支持將進程轉為守護進程，完全脫離終端運行
- **PID 管理**: 自動管理 PID 文件，防止多個實例同時運行
- **優雅停止**: 支持優雅的進程停止，先發送 SIGTERM 再發送 SIGKILL

## 10. 監控系統 (`monitoring/monitoring.py`)

專案包含一個完整的監控和告警系統：

### 系統監控

- **資源監控**: 監控 CPU、內存、磁盤使用率和系統負載
- **進程監控**: 監控交易機器人進程狀態，檢測殭屍進程和資源使用過高
- **網絡監控**: 檢查與各交易所的網絡連通性

### 告警系統

- **多級告警**: 支持 INFO、WARNING、ERROR、CRITICAL 四個級別
- **多種通知方式**: 支持郵件、Telegram 和 Webhook 通知
- **告警歷史**: 保存告警歷史記錄，支持告警確認

### 性能監控

- **性能數據收集**: 定期收集系統和應用性能指標
- **性能報告**: 生成指定時間範圍內的性能統計報告
- **資源使用趨勢**: 跟蹤 CPU、內存、磁盤使用趨勢

## 11. 輸入驗證框架 (`utils/input_validation.py`)

專案採用了統一的輸入驗證框架，解決 code review 中識別的輸入驗證不足問題：

### 驗證器組件

- **ValidationRule**: 單個驗證規則類，包含驗證邏輯和錯誤消息
- **InputValidator**: 輸入驗證器主類，管理多個驗證規則
- **CommonRules**: 常用驗證規則集合，包含正數、價格、百分比等驗證

### 專用驗證器

- **WebApiValidator**: Web API 專用驗證器，用於驗證 Web API 參數
- **StrategyValidator**: 策略參數專用驗證器，用於驗證策略參數

### 驗證功能

- **單字段驗證**: 對單個字段應用多個驗證規則
- **跨字段驗證**: 驗證多個字段之間的邏輯關係
- **錯誤收集**: 收集所有驗證錯誤，一次性返回

## 12. 異常處理 (`core/exceptions.py`)

專案定義了完整的異常處理層次結構：

### 配置相關異常

- **ConfigError**: 配置相關錯誤基類
- **ConfigValidationError**: 配置驗證錯誤
- **ConfigLoadError**: 配置加載錯誤
- **ConfigSaveError**: 配置保存錯誤
- **ConfigBackupError**: 配置備份錯誤
- **ConfigRestoreError**: 配置恢復錯誤
- **EnvironmentVariableError**: 環境變量錯誤

### 守護進程相關異常

- **DaemonError**: 守護進程相關錯誤基類
- **DaemonStartError**: 守護進程啟動錯誤
- **DaemonStopError**: 守護進程停止錯誤
- **DaemonConfigError**: 守護進程配置錯誤

這種異常處理結構提供了更精確的錯誤分類和處理，便於調試和錯誤恢復。

## 13. 設定 (`config.py`)

-   設定在 `config.py` 中管理。
-   它使用 `python-dotenv` 從專案根目錄的 `.env` 檔案載入環境變數。
-   它定義了所有支援交易所的 API 金鑰、密鑰和基礎 URL。
-   它還包括代理、資料庫和日誌的設定。

## 14. 使用方法

本程序提供四種運行模式，您可以根據需求選擇：

### 運行模式說明

| 模式 | 命令 | 適用場景 | 特點 |
|------|------|---------|------|
| **Web 控制枱** | `python run.py --web` | 可視化操作和監控 | 圖形界面、實時數據、易於上手 |
| **命令行界面 (CLI)** | `python run.py --cli` | 交互式配置 | 菜單導航、逐步配置、適合測試 |
| **快速啟動** | `python run.py [參數]` | 自動化運行 | 直接啟動、適合腳本化部署 |
| **守護進程模式** | `python core/daemon_manager.py start --daemon` | 生產環境部署 | 背景運行、自動重啟、高可用性 |

> **推薦順序**：新手建議先用 Web 控制枱熟悉功能 → CLI 測試參數 → 守護進程模式生產部署

---

### 模式一：Web 控制枱

程序提供了直觀的 Web 控制枱界面，方便可視化管理和監控交易策略。

#### 啟動步驟

```bash
# 啟動 Web 服務器（默認端口 5000）
python run.py --web
```

#### 訪問控制枱

啟動後，在瀏覽器中訪問：
```
http://localhost:5000
```

#### Web 界面功能

- **實時監控**：查看交易統計、餘額、盈虧等實時數據（每5秒更新）
- **策略管理**：啟動/停止做市策略，支持多種策略類型
- **參數配置**：
  - 交易所選擇（Backpack、Aster、Paradex）
  - 市場類型（現貨 / 永續合約）
  - 策略類型（標準做市 / Maker-Taker 對沖 / 網格交易）
  - 交易對、價差、訂單數量等
  - 永續合約參數（目標倉位、最大倉位、止損止盈等）
  - 網格交易參數（網格數量、價格範圍、網格模式等）
  - 現貨重平衡參數
- **數據展示**：
  - 當前價格和餘額（只顯示報價資產 USDT/USDC/USD）
  - 交易統計（買賣筆數、成交量、手續費）
  - 盈虧分析（已實現/未實現盈虧、累計盈虧、磨損率）
  - 運行時間統計

#### 使用示例

1. 啟動 Web 服務器
2. 在瀏覽器打開控制枱
3. 配置環境變量（API Key 需提前在 .env 文件中設置）
4. 選擇交易所和交易對
5. 設置策略參數
6. 點擊"啟動機器人"開始交易
7. 實時查看交易狀態和統計數據
8. 需要停止時點擊"停止機器人"

#### 注意事項

- Web 服務器需要持續運行以監控策略
- API 密鑰通過環境變量讀取，不會在 Web 界面中顯示
- 停止策略後統計數據會保留，方便查看最終結果

---

### 模式二：命令行界面 (CLI)

交互式命令行界面，提供菜單導航和逐步配置。

#### 啟動步驟

```bash
python run.py --cli
```

#### 主要功能

- `1 - 查詢餘額`: 查看所有已配置交易所的資產餘額
- `2 - 查詢訂單簿`: 查看指定交易對的買賣盤口
- `3 - 下單`: 手動下單測試
- `4 - 取消訂單`: 取消指定訂單
- `5 - 執行做市策略`: 交互式配置並啟動做市策略
- `6 - 查看市場信息`: 查看交易對詳細信息
- `7 - 查看波動率`: 分析市場波動率
- `8 - 重平設置管理`: 查看和測試重平衡配置
- `9 - 資料庫管理`: 切換資料庫寫入功能
- `0 - 退出`: 退出程序

> **適合場景**：參數測試、功能驗證、逐步配置

---

### 模式三：快速啟動

直接通過命令行參數啟動策略，適合自動化部署和腳本運行。

#### 快速示例

```bash
# BackPack 現貨做市
python run.py --exchange backpack --symbol SOL_USDC --spread 0.01 --max-orders 3 --duration 3600 --interval 60

# BackPack Maker-Taker 現貨對沖
python run.py --exchange backpack --symbol SOL_USDC --spread 0.01 --strategy maker_hedge --duration 3600 --interval 30

# BackPack 永續做市
python run.py --exchange backpack --market-type perp --symbol SOL_USDC_PERP --spread 0.01 --quantity 0.1 --max-orders 2 --target-position 0 --max-position 5 --position-threshold 2 --inventory-skew 0 --stop-loss -1 --take-profit 5 --duration 3600 --interval 10

# BackPack Maker-Taker 永續對沖
python run.py --exchange backpack --market-type perp --symbol SOL_USDC_PERP --spread 0.01 --quantity 0.1 --strategy maker_hedge --target-position 0 --max-position 5 --position-threshold 2 --duration 3600 --interval 8

# BackPack 現貨網格交易（自動價格範圍）
python run.py --exchange backpack --symbol SOL_USDC --strategy grid --auto-price --grid-num 10 --quantity 0.1 --duration 3600 --interval 60

# BackPack 永續合約網格交易（自動價格範圍）
python run.py --exchange backpack --market-type perp --symbol SOL_USDC_PERP --strategy perp_grid --grid-type neutral --auto-price --price-range 5 --grid-num 10 --quantity 0.1 --max-position 2.0 --duration 3600 --interval 60
```

> **適合場景**：自動化部署、定時任務、批量運行  
> **完整示例和參數說明請查看**：[策略文檔](#-策略文檔)

---

### 模式四：守護進程模式

生產環境推薦的部署方式，提供高可用性和自動恢復功能。

#### 啟動守護進程

```bash
# 啟動守護進程（背景運行）
python core/daemon_manager.py start --daemon

# 使用自定義配置文件
python core/daemon_manager.py start --daemon --config /path/to/config.json
```

#### 管理守護進程

```bash
# 查看狀態
python core/daemon_manager.py status

# 停止守護進程
python core/daemon_manager.py stop

# 重啟守護進程
python core/daemon_manager.py restart
```

#### 守護進程優勢

- **背景運行**: 完全脫離終端，SSH 斷開後繼續運行
- **自動重啟**: 程序崩潰後自動重啟，可配置重啟次數和延遲
- **資源監控**: 定期檢查系統資源使用情況
- **日誌管理**: 自動管理日誌文件，避免日誌過大
- **健康檢查**: 定期檢查程序健康狀態

#### 配置文件

守護進程使用 `config/daemon_config.json`（傳統格式）或新的多配置格式進行配置。新的多配置格式支持更靈活的配置管理，包括配置模板、版本控制和環境變量支持。

> **適合場景**：生產環境部署、長期運行、無人值守