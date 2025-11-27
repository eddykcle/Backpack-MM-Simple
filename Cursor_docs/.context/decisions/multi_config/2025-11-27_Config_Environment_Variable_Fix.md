# 配置文件環境變量不匹配問題修復

## 背景
- 交易機器人守護進程啟動失敗，循環重啟
- 錯誤信息顯示配置驗證失敗：`api_key 應該使用環境變量格式: ${VARIABLE_NAME}`
- 問題根源：配置文件使用 `${BACKPACK_URL}` 但 `.env.example` 定義的是 `BASE_URL`

## 決策摘要
1. **修改所有 Backpack 配置文件的環境變量名稱**
   - 將 `${BACKPACK_URL:-https://api.backpack.exchange}` 改為 `${BASE_URL:-https://api.backpack.work}`
   - 確保與 `.env.example` 中的環境變量名稱一致

2. **修復守護進程配置加載邏輯**
   - 修改 `daemon_manager.py` 中的 `_load_multi_config()` 方法
   - 先使用 `expand_vars=False` 加載配置進行驗證
   - 驗證通過後再展開環境變量

## 操作流程
1. 停止當前失敗的守護進程
2. 修改配置文件中的環境變量引用
3. 修復守護進程的配置驗證邏輯
4. 重新啟動守護進程
5. 驗證交易機器人正常運行

## 風險與建議
- 確保環境變量在 `.env` 文件中正確設置
- 使用 `BASE_URL` 而非 `BACKPACK_URL` 作為環境變量名稱
- 守護進程現在會正確驗證環境變量格式

## 常見操作問答
- **為什麼需要修改環境變量名稱？**
  確保配置文件與 `.env.example` 中定義的環境變量名稱一致，避免混淆。

- **守護進程如何處理環境變量？**
  先驗證配置文件中的環境變量格式，然後再展開實際值。

## 本次代碼更新概括
1. **配置文件層**: 修改了 5 個配置文件的環境變量引用
2. **守護進程層**: 修復了配置驗證和環境變量展開的順序問題

### 涉及檔案
- `config/active/backpack_eth_usdc_perp_grid.json`
- `config/templates/backpack_perp_grid.json`
- `config/templates/backpack_spot_grid.json`
- `config/active/test_backpack_sol_usdc_spot_grid.json`
- `config/active/test_backpack_sol_usdc_spot_grid_env.json`
- `core/daemon_manager.py`