# Backpack_coding.md

運行與配置規範 (Runtime & Configuration)
**重要：** 我主要投過守護進程 (Daemon) 模式運行程序。

1.  **啟動指令 (Execution Command)**:
    標準的啟動方式如下：
    ```bash
    .venv/bin/python3 core/daemon_manager.py start --daemon
    ```
    *注意：這能確保機器人在背景運行，並使用正確的虛擬環境。*

2.  **配置管理 (Configuration)**:
    *   核心配置由 **`config/daemon_config.json`** 控制。
    *   開發新功能或策略時，必須確保參數是從此 JSON 文件中讀取，而不是硬編碼 (Hardcoding)。
    *   請確保新功能可以被 `daemon_manager` 正確加載和管理。