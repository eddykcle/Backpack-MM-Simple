## 會話目標
- 讓 `run.py` 在 daemon 發送 SIGTERM 時能優雅停止，不再被強制殺掉。
- 修正 logging API 用法，避免結構化日誌報錯。
- 改善 WebSocket 關閉流程，減少背景執行緒阻塞進程退出。

## 主要變更
- `run.py` 新增 `StrategySignalHandler`，運行策略時臨時接管 SIGTERM/SIGINT，確保呼叫 `strategy.stop()` 後才退出。
- `strategies/market_maker.py` 在 `run()` 的 `finally` 內關閉 `ThreadPoolExecutor`，避免卡住。
- `core/daemon_manager.py` 新增 `bot_stop_timeout`/`bot_kill_timeout` 設定並改用 f-string 記錄日誌。
- `ws_client/client.py` 的 `close()` 與 `_force_close_connection()` 延長等待時間、必要時將舊 websocket thread 改為 daemon，並支援自動讀取 `HTTP(S)_PROXY`。

## 技術決策及原因
- 以 context manager 包裝信號處理，比 scattered try/except 更可控，並可於退出時恢復原 handler。
- 讓等待 timeout 可透過 `daemon_config.json` 調整，以符合不同策略的清理時間。
- WebSocket 線程延長 join 並設為 daemon，可避免系統層面視為仍在運行。
- `StructuredLogger` 只接受訊息字串與 kwargs，改用 f-string + `pid=...` 是最安全的寫法。

## 遺留問題
- 尚未實地驗證新的 shutdown 流程是否足夠，若仍超時需透過 `ps/strace` 找出阻塞點。
- WebSocket 以外的背景任務（REST 輪詢、資料庫寫入）仍可能造成退出延遲。
- `websocket` 模組的 lint 警告依然存在，需在環境中安裝對應套件或忽略。
20:00:56 - WARNING - {"timestamp": "2025-11-18T20:00:56.736464", "level": "WARNING", "logger": "trading_bot_daemon", "message": "進程未在 25 秒內終止，強制殺掉", "module": "", "function": null, "line": 0, "data": {"pid": 2975819}}
20:01:01 - ERROR - {"timestamp": "2025-11-18T20:01:01.763978", "level": "ERROR", "logger": "trading_bot_daemon", "message": "強制殺掉後 5 秒內仍未退出", "module": "", "function": null, "line": 0, "data": {"pid": 2975819}}
20:01:01 - INFO - {"timestamp": "2025-11-18T20:01:01.766746", "level": "INFO", "logger": "trading_bot_daemon", "message": "已停止 1 個 run.py 進程", "module": "log_manager", "function": "log_structured", "line": 221}


## 下一步建議
- 重啟 daemon 後再執行 `python core/daemon_manager.py stop` 測試，並用 `ps -p <pid>` 觀察退出狀態。
- 若仍超過 25 秒，適度調高 `bot_stop_timeout` 並檢查 `market_maker.log` 的 WARNING 以鎖定源頭。
- 視需要在策略 `stop()` 中加上全線程檢查，確保沒有遺漏的背景任務。
- 安裝 `websocket-client` 或設定 lint 例外，消除 IDE 警告。

