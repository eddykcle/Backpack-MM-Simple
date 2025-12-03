# Grid Range Adjustment Notes

## 背景
- 需在有持倉的情況下靈活上調網格上限／下限，避免價格突破後策略停擺。
- 操作必須不打斷正在運行的策略，而且僅經由 CLI 入口觸發（無需 Web UI 操作）。

## 決策摘要
1. **策略層新增熱調整能力**  
   - `GridStrategy` / `PerpGridStrategy` 提供 `adjust_grid_range()`，可在 `RLock` 保護下重新設定價格區間並重建網格掛單，同時保留成交紀錄與倉位。  
   - 調整過程失敗時會自動回退至原設定並嘗試重新初始化，確保資金安全。
2. **控制層提供 API 入口**  
   - `POST /api/grid/adjust` 由 `web/server.py` 暴露，驗證策略類型後呼叫上述方法，並廣播最新區間。
3. **CLI 儀表板串接 API**  
   - `cli/commands.py` 新增「調整運行中網格」命令（主選單 10），可指定 Web 控制端 URL 與新的上下限，並立即查看回應。

## 操作流程
1. 啟動 Web 控制端並透過其啟動網格策略（Spot 或 Perp）。
2. 在 CLI 主選單選擇 `10 - 調整運行中網格範圍`，輸入 Web 主機位址與新的上下限（可單獨調整某一側）。  
3. 服務端會：
   - 驗證參數 → `adjust_grid_range()` → 取消舊掛單 → 依新區間重建網格。  
   - 於 SocketIO 廣播事件 `grid_adjusted`，供儀表板/監控即時刷新。

## 風險與建議
- 需確保 Web 控制端可連線（預設 `http://127.0.0.1:5000`）。CLI 提供自訂 URL 以支援遠端部署。  
- 若帳戶可用資金不足以在新區間補齊掛單，策略會記錄警告但保持新設定。  
- 調整期間 `grid_operation_lock` 會阻塞例行補單，避免競態；請避免頻繁地在短時間內重置，以免觸發交易所速率限制。  
- 後續可依需求延伸：驗證建議區間、批量記錄多次調整歷史。 

## 常見操作問答
- **若策略是透過 `core/daemon_manager.py start` 啟動的，CLI 是否仍可調整網格？**  
  可以。守護程式最終仍是呼叫 `run.py`，而 `run.py` 在直接執行策略時會自動於背景啟動 Web 控制端 (`start_web_server_in_background`)。只要 5000 連線暢通，CLI 主選單 10 或直接呼叫 `/api/grid/adjust` 都能修改區間。
- **使用 `python run.py --cli` 發送調整後，關閉本地電腦會中斷策略嗎？**  
  不會。CLI 只是一次性把 HTTP 請求送到遠端 Web 控制端；指令送達並生效後，遠端機器上的 bot 照常運作。日後若要再次調整，只需重新連線並再執行 CLI 或 API 請求即可。

## 本次代碼更新概括
1. **策略層**：`GridStrategy` 及 `PerpGridStrategy` 新增 `grid_operation_lock` 與 `adjust_grid_range()`，允許在鎖保護下重新計算網格並自動回退失敗情境。  
2. **控制層 API**：`web/server.py` 新增 `POST /api/grid/adjust`，僅當前策略支援網格且正在運行時才受理，成功後透過 SocketIO 推播 `grid_adjusted`。  
3. **CLI 入口**：`cli/commands.py` 加入主選單項目 10（`grid_adjust_command`），可輸入 Web 端位址及新上下限，並透過 `requests` 呼叫上述 API。  
4. **文檔**：本決策檔補充了操作流程、FAQ，以及 CLI/Daemon/遠端互動時的注意事項，供後續維運參考。

### 涉及檔案
- `strategies/grid_strategy.py`
- `strategies/perp_grid_strategy.py`
- `web/server.py`
- `cli/commands.py`
- `Cursor_docs/.context/decisions/grid_enhancement.md`
