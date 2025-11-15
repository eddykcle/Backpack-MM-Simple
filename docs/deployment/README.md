# 部署運維指南

這個目錄包含了服務器部署、運維管理和故障排除的詳細文檔。

## 🚀 部署指南

### 基礎部署
- [SSH 斷開連接測試指南](./SSH_DISCONNECT_TEST.md) - 確保系統在SSH斷開後繼續運行
- [Uptime Kuma 監聽設置](./UPTIME_KUMA_SETUP.md) - 配置外部監控系統
- [Git Fork 工作流程](./SETUP_FORK_WORKFLOW.md) - 版本控制和代碼管理

### 高級部署
- [Docker 容器化部署](./docker-deployment.md) - 使用Docker部署系統
- [負載均衡配置](./load-balancing.md) - 多服務器負載均衡
- [自動化部署](./ci-cd.md) - CI/CD流水線配置

## 🔧 運維管理

### 日常維護
- [日誌管理](./log-management.md) - 日誌查看和清理
- [性能監控](./performance-monitoring.md) - 系統性能優化
- [備份策略](./backup-strategy.md) - 數據備份和恢復

### 安全管理
- [安全加固](./security-hardening.md) - 系統安全配置
- [訪問控制](./access-control.md) - 用戶權限管理
- [審計日誌](./audit-logs.md) - 安全審計配置

## 📊 監控告警

### 系統監控
- [資源監控](./resource-monitoring.md) - CPU、內存、磁盤監控
- [網絡監控](./network-monitoring.md) - 網絡連接和延遲監控
- [應用監控](./application-monitoring.md) - 應用程序健康檢查

### 告警配置
- [郵件告警](./email-alerts.md) - 郵件通知配置
- [Telegram 告警](./telegram-alerts.md) - Telegram機器人配置
- [Webhook 告警](./webhook-alerts.md) - 自定義Webhook配置

## 🛠️ 故障排除

### 常見問題
- [啟動失敗](./startup-issues.md) - 系統無法啟動的解決方案
- [性能問題](./performance-issues.md) - 系統性能下降處理
- [連接問題](./connection-issues.md) - 網絡連接故障排除

### 緊急處理
- [系統崩潰](./system-crash.md) - 系統崩潰恢復流程
- [數據恢復](./data-recovery.md) - 數據損壞恢復
- [服務遷移](./service-migration.md) - 服務器遷移指南

## 📋 部署檢查清單

### 基礎部署檢查
- [ ] 系統環境配置完成
- [ ] 依賴庫安裝完成
- [ ] 配置文件設置正確
- [ ] API密鑰配置完成
- [ ] 守護進程測試通過
- [ ] SSH斷開連接測試通過

### 監控配置檢查
- [ ] Uptime Kuma監控配置完成
- [ ] 告警通知測試通過
- [ ] 日誌輪轉配置正確
- [ ] 性能監控啟用

### 安全檢查
- [ ] 防火牆配置正確
- [ ] 訪問權限設置完成
- [ ] 敏感信息加密存儲
- [ ] 定期備份策略配置

## 🔗 相關鏈接

- [新手入門指南](../getting-started/) - 基礎知識和配置
- [策略詳細說明](../strategies/) - 深入了解各種交易策略
- [系統管理文檔](../system/) - 系統配置和監控

## 💡 最佳實踐

### 部署建議
1. **測試環境先行** - 在測試環境驗證所有配置
2. **逐步部署** - 分階段部署，降低風險
3. **監控覆蓋** - 確保所有關鍵組件都有監控
4. **文檔記錄** - 記錄所有配置和修改

### 運維建議
1. **定期檢查** - 定期檢查系統狀態和日誌
2. **備份策略** - 建立完善的備份和恢復機制
3. **容量規劃** - 提前規劃系統容量擴展
4. **安全更新** - 及時更新系統和依賴的安全補丁

## ⚠️ 重要提醒

- 在生產環境部署前，請務必在測試環境驗證
- 確保有完整的備份和恢復方案
- 配置適當的監控和告警機制
- 定期檢查和更新系統安全配置
