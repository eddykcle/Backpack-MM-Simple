# 多實例守護進程統一入口決策

## 背景
- 原先 `core/daemon_manager.py` 與 `cli/instance_cli.py` 都提供實例管理命令，導致 list/cleanup 等功能重複，使用者必須記住兩套入口。
- `TradingBotDaemon` 內部自行以 JSON 操作 `logs/instances.json`，未重用 `core.instance_manager.InstanceRegistry`，造成註冊/註銷邏輯重複且難以維護。
- 計畫（`Cursor_docs/.context/sessions/merge-instance-cli.plan.md`）要求以 `daemon_manager.py` 作為唯一 CLI，以最簡方案支援多個 grid bot 同時運行。

## 決策摘要
1. **守護進程統一註冊機制**：`TradingBotDaemon` 直接建立 `InstanceRegistry` 實例，並用它處理 `register/unregister`，擺脫手寫 JSON 流程，讓所有實例在單一註冊表中維持一致狀態。
2. **淘汰舊 CLI**：刪除 `cli/instance_cli.py` 及其測試依賴，確定所有列出、清理、狀態查詢等功能都由 `daemon_manager.py` 的子命令提供，減少記憶負擔。
3. **測試對齊**：Phase 5 與 Phase 6 測試調整為僅驗證 `InstanceRegistry` 與 `daemon_manager` 行為，不再嘗試匯入或執行已移除的 CLI，確保自動化檢查聚焦於統一入口。

## 實作重點
- `core/daemon_manager.py`：
  - 匯入 `InstanceRegistry`，在 `TradingBotDaemon.__init__` 中初始化並保存至 `self.registry`。
  - `_register_instance()`/`_unregister_instance()` 改為呼叫 `InstanceRegistry.register()` 與 `unregister()`，並保留原有記錄欄位（config_file、pid、log_dir、web_port、started_at、status）。
- `cli/instance_cli.py`：整個檔案移除，後續 CLI 功能以 `python core/daemon_manager.py <action>` 使用。
- 測試更新：
  - `tests/test_phase5_instance_manager.py` 僅保留 `test_instance_registry()`；主程式直接依照此函式結果回傳 exit code。
  - `tests/test_phase6_integration.py` 移除 `test_instance_cli()`，其餘步驟仍覆蓋配置、隔離、daemon CLI、併發啟動等情境。

## 測試
- `.venv/bin/python3 tests/test_phase5_instance_manager.py`
  - 結果：所有註冊、查詢、列表、更新、清理與持久化用例通過。
- Phase 6 測試因依賴實際 API/執行序列，未在此次修改中重新跑；待需要時可使用 `python core/daemon_manager.py list` 等命令人工驗證多實例資訊同步。

## 風險與後續
- `cli/instance_cli.py` 使用者需要切換到 `daemon_manager.py` 的子命令；需在 README/運維文檔中提醒。
- `InstanceRegistry` 目前僅在守護進程啟停時更新，若後續要支援進程內狀態更新（例如健康檢查）可能需要新增 `update()` 調用。
- 如需重新整合 `cleanup`/`stats` 等命令，可在 `daemon_manager.py` 補上相應 action，以保持原 CLI 等價能力。
