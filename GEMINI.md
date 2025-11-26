# Gemini 專案上下文 (Project Context)

## 1. 項目概覽 (Project Overview)
這是一個基於 Python 的加密貨幣做市商 (Market Maker) 與網格交易 (Grid Trading) 機器人。
主要針對 **Backpack Exchange**，同時包含 Lighter、Paradex 等其他交易所的接口。系統設計為守護進程 (Daemon) 架構，以支援持續運行。

## 2. 架構與核心模組 (Architecture & Core Modules)
*   **`api/`**: 交易所 API 封裝 (Backpack, Lighter, Paradex)。
*   **`strategies/`**: 交易策略邏輯 (Grid, Maker/Taker Hedge, Perp MM)。
*   **`core/`**: 核心系統邏輯。
    *   `daemon_manager.py`: 程序的管理入口。
    *   `log_manager.py` / `logger.py`: 統一的日誌系統。
*   **`database/`**: 數據庫交互與持久化。
*   **`web/`**: 監控面板與網頁服務器。
*   **`config/`**: 存放核心配置文件，如 `daemon_config.json`。

## 3. 運行與配置規範 (Runtime & Configuration)
**重要：** 本專案設計為守護進程 (Daemon) 模式運行。

1.  **啟動指令 (Execution Command)**:
    標準的啟動方式如下：
    ```bash
    .venv/bin/python3 core/daemon_manager.py start --daemon
    ```
    *注意：這能確保機器人在背景運行，並使用正確的虛擬環境。*

2.  **配置管理 (Configuration)**:
    *   核心配置由 **`config/daemon_config.json`** 控制。
    *   開發新功能或策略時，必須確保參數是從此 JSON 文件中讀取，而不是硬編碼 (Hardcoding)。
    *   這確保了新功能可以被 `daemon_manager` 正確加載和管理。

## 4. 開發規範 (Development Guidelines)
*   **日誌 (Logging)**: **嚴禁使用 `print()`**。必須使用 `core.logger` 模組進行記錄，因為 Daemon 在後台運行時無法直接查看標準輸出。
*   **異步 (Async)**: 專案廣泛使用 `asyncio`，請確保新的 I/O 操作（如 API 請求、數據庫讀寫）保持異步特性，避免阻塞主線程。
*   **類型提示 (Type Hinting)**: 建議使用 Python Type Hints 以增加代碼可讀性與維護性。

## 5. 環境與安全 (Environment & Security)
*   **虛擬環境**: 位於 `.venv/`。
*   **依賴管理**: 使用 `requirements.txt` 管理。
*   **安全**: 絕對不要將真實的 API Key 或私鑰提交到 Git。請使用環境變數 (`.env`) 或安全的配置加載方式。

## 6. 參考文檔
*   **Codemap**: 參考 `codemap.md`。

## 7. 當前任務與備忘 (Memory & Context)
*(此處可由 AI 或開發者根據當前開發進度動態更新)*
*   目前關注點：確保所有新策略都能透過 `daemon_config.json` 正確初始化。