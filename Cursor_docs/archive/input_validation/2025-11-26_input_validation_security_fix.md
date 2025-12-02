# 輸入驗證安全修復

## 背景
根據 2025-11-22 的 code review 報告，系統存在多個嚴重的輸入驗證不足問題，包括：
- Web API 端點缺少身份驗證和輸入驗證
- CLI 命令可能被用於 SSRF 攻擊
- 策略層缺少價格範圍合理性檢查

這些問題可能導致策略異常行為、資金損失和安全漏洞。

## 決策摘要
1. **設計統一輸入驗證框架**
   - 創建可重用的驗證組件
   - 實現類型驗證、範圍檢查和業務邏輯驗證
   - 支持跨字段驗證規則

2. **修復 Web API 安全漏洞**
   - 在 `/api/grid/adjust` 端點添加完整輸入驗證
   - 實現價格範圍合理性檢查
   - 添加統一錯誤處理機制

3. **防禦 SSRF 攻擊**
   - 在 CLI 命令中實現 URL 白名單驗證
   - 只允許本地和內網地址
   - 添加協議檢查（優先 HTTPS）

4. **增強策略層驗證**
   - 在網格策略初始化時驗證參數
   - 添加運行時參數驗證
   - 實現價格範圍邏輯檢查

5. **實施防禦性編程**
   - 所有外部輸入都必須經過驗證
   - 使用白名單而非黑名單方法
   - 實施多層驗證機制

## 操作流程

### 階段 1: 框架開發（1-2 天）
1. 創建 `utils/input_validation.py` 模塊
2. 實現核心驗證類別（ValidationRule, InputValidator）
3. 定義預設驗證規則（CommonRules）
4. 創建專用驗證器（WebApiValidator, CliValidator, StrategyValidator）
5. 編寫單元測試

### 階段 2: Web API 修改（1 天）
1. 修改 `web/server.py` 中的 `/api/grid/adjust` 端點
2. 添加輸入驗證中間件
3. 實現統一錯誤響應格式
4. 編寫集成測試

### 階段 3: CLI 命令修改（1 天）
1. 修改 `cli/commands.py` 中的 `grid_adjust_command`
2. 添加 URL 白名單驗證
3. 實現 SSRF 防護機制
4. 改善用戶錯誤提示

### 階段 4: 策略層增強（1-2 天）
1. 修改 `strategies/grid_strategy.py` 和 `strategies/perp_grid_strategy.py`
2. 添加初始化參數驗證
3. 實現運行時參數驗證
4. 增強錯誤處理機制

### 階段 5: 測試和部署（1 天）
1. 運行完整測試套件
2. 性能測試和優化
3. 更新文檔
4. 生產環境部署

## 風險與建議

### 安全風險
- **驗證規則不完整**: 可能遺漏某些攻擊向量
  - **建議**: 定期審查和更新驗證規則
- **性能影響**: 驗證可能增加響應時間
  - **建議**: 實施驗證快取和早期退出機制
- **向後兼容性**: 新的驗證可能影響現有客戶端
  - **建議**: 提供可選的驗證開關和遷移指南

### 業務風險
- **過度驗證**: 可能阻止合法操作
  - **建議**: 詳細測試邊界情況，提供清晰的錯誤信息
- **用戶體驗**: 驗證失敗可能影響用戶操作
  - **建議**: 提供友好的錯誤提示和操作指導

### 技術風險
- **代碼複雜性**: 新的驗證框架增加系統複雜性
  - **建議**: 保持框架簡單，提供詳細文檔和示例
- **測試覆蓋**: 需要確保所有驗證路徑都被測試
  - **建議**: 實施全面的單元測試和集成測試

## 常見操作問答

### **問: 為什麼選擇白名單而不是黑名單方法？**
**答:** 白名單方法更安全，因為：
1. 明確定義允許的輸入範圍
2. 新的攻擊向量不會意外通過驗證
3. 更容易審計和維護安全規則

### **問: 如何處理現有系統的向後兼容性？**
**答:** 採用以下策略：
1. 保持現有 API 響應格式不變
2. 添加可選的驗證開關（通過環境變量控制）
3. 提供遷移文檔和工具
4. 分階段部署，先在測試環境驗證

### **問: 驗證失敗時如何記錄和處理？**
**答:** 實施多層記錄機制：
1. 詳細的驗證失敗日誌（包含客戶端信息）
2. 安全事件監控和告警
3. 定期審查異常模式
4. 用戶友好的錯誤信息（不暴露內部細節）

### **問: 如何確保驗證規則的有效性？**
**答:** 建立持續改進機制：
1. 定期安全審查和滲透測試
2. 監控新的攻擊技術和漏洞
3. 收集用戶反饋和異常報告
4. 定期更新驗證規則和模式

## 本次代碼更新概括

### **核心框架層**
- **新增**: `utils/input_validation.py` - 統一輸入驗證框架
  - ValidationRule 類：單個驗證規則實現
  - InputValidator 類：多規則組合驗證器
  - CommonRules 類：預定義常用驗證規則
  - 專用驗證器：WebApiValidator, CliValidator, StrategyValidator

### **Web API 層**
- **修改**: `web/server.py` 中的 `/api/grid/adjust` 端點
  - 添加完整輸入驗證邏輯
  - 實現價格範圍合理性檢查
  - 統一錯誤響應格式
  - 添加驗證失敗日誌記錄

### **CLI 層**
- **修改**: `cli/commands.py` 中的 `grid_adjust_command` 函數
  - 實現 URL 白名單驗證
  - 添加 SSRF 攻擊防護
  - 改善用戶錯誤提示和指導
  - 增強網絡請求錯誤處理

### **策略層**
- **修改**: `strategies/grid_strategy.py` 和 `strategies/perp_grid_strategy.py`
  - 添加初始化參數驗證
  - 實現運行時參數驗證
  - 增強 `adjust_grid_range` 方法的安全性
  - 改進錯誤處理和恢復機制

### **測試層**
- **新增**: `tests/test_input_validation.py` - 單元測試
  - 測試所有驗證規則的正確性
  - 邊界值和惡意輸入測試
  - 跨字段驗證測試
- **新增**: `tests/test_web_api_validation.py` - 集成測試
  - API 端點驗證測試
  - 錯誤響應格式測試
  - 安全攻擊模擬測試

### **文檔層**
- **新增**: `docs/input_validation_framework.md` - 框架設計文檔
- **新增**: `docs/input_validation_implementation.md` - 實施計劃文檔
- **更新**: 相關 API 文檔和使用指南

### 涉及檔案
- `utils/input_validation.py` (新增)
- `web/server.py` (修改)
- `cli/commands.py` (修改)
- `strategies/grid_strategy.py` (修改)
- `strategies/perp_grid_strategy.py` (修改)
- `tests/test_input_validation.py` (新增)
- `tests/test_web_api_validation.py` (新增)
- `docs/input_validation_framework.md` (新增)
- `docs/input_validation_implementation.md` (新增)