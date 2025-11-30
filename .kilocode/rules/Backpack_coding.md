# Backpack_coding.md

## 專案上下文與記憶 (Project Context & Memory)

1.  **啟動指令 (Execution Command)**:
    標準的啟動方式如下：
    ```bash
    .venv/bin/python3 core/daemon_manager.py start --daemon
    ```
    *注意：這能確保機器人在背景運行，並使用正確的虛擬環境。*
    **重要：** 我主要透過守護進程 (Daemon) 模式運行程序。

    *   核心配置由 **`config/daemon_config.json`** 控制。
    *   開發新功能或策略時，必須確保參數是從此 JSON 文件中讀取，而不是硬編碼 (Hardcoding)。
    *   請確保新功能可以被 `daemon_manager` 正確加載和管理。

2. **運行環境（Environment）**:
   * cd /home/eddy/Backpack-MM-Simple && .venv/bin/python3

3. **測試（Testing）**:
   * 使用 unittesting

4.   **參考文檔 (Reference document)**:
    * BACKPACK exchange api document: **`/home/eddy/Backpack-MM-Simple/Reference/Backpack_Exchange_API.json`**
    * **Codemap**: 參考 `codemap.md`。
    * **API KEY 存放template**：參考 `env.example`。

