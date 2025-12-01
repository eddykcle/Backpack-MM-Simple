# 系統管理文檔

這個目錄包含了系統配置、監控和管理的詳細文檔。

## 📚 完整文檔

**👉 [系統管理完整指南](./README_COMPLETE.md)** - 整合了所有系統管理相關的完整文檔，包含：
- 系統概述和組件介紹
- 核心功能詳解（日誌管理、進程守護、監控告警）
- SSH斷開連接支持技術原理
- 快速開始指南
- 高級用法和配置
- 測試驗證方法
- 故障排除指南
- 性能和安全考慮

## 🖥️ 系統組件

### 核心管理系統
- [守護進程管理器](../core/daemon_manager.py) - 進程守護和自動重啟
- [系統監控](../monitoring/monitoring.py) - 資源監控和告警系統
- [日誌管理器](../core/log_manager.py) - 結構化日誌和日誌輪轉

### 配置文件
- [守護進程配置](../config/daemon_config.json) - 系統運行參數配置

## 🔧 核心功能概覽

### 1. 高級日誌管理
- **結構化日誌**: JSON格式，便於程序解析
- **日誌輪轉**: 自動輪轉，防止無限增長
- **壓縮存儲**: 自動壓縮舊日誌，節省空間
- **多級別分類**: 分離一般、錯誤和結構化日誌
- **異步寫入**: 避免阻塞主線程
- **自動清理**: 定期清理超過指定天數的舊日誌

### 2. 進程守護管理
- **守護進程化**: 自動轉為守護進程，支持SSH斷開後繼續運行
- **PID管理**: 自動管理PID文件，防止重複啟動
- **自動重啟**: 進程崩潰時自動重啟，支持重試限制
- **健康檢查**: 定期檢查進程健康狀態
- **資源監控**: 監控CPU和內存使用
- **優雅停止**: 支持SIGTERM和SIGINT信號處理

### 3. 系統監控和告警
- **系統資源監控**: CPU、內存、磁盤使用率
- **進程狀態監控**: 監控交易機器人進程狀態
- **網絡連接檢查**: 檢查關鍵服務的網絡連接
- **性能數據收集**: 收集歷史性能數據
- **多種告警方式**: 郵件、Telegram、Webhook
- **告警歷史**: 記錄和管理告警歷史

## 🚀 快速開始

### 1. 安裝依賴
```bash
pip install psutil requests
```

### 2. 配置系統
編輯 `config/daemon_config.json` 文件，設置您的交易參數。

### 3. 啟動系統
```bash
# 啟動守護進程（推薦使用虛擬環境中的Python）

.venv/bin/python3 core/daemon_manager.py start --config config/active/backpack_eth_usdc_perp_grid.json --daemon

# 4. 等待幾秒確認啟動成功
sleep 5

.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_sol_01.json --daemon
.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_eth_02.json --daemon

# 查看狀態
.venv/bin/python3 core/daemon_manager.py status 

# 列出所有實例
.venv/bin/python3 core/daemon_manager.py list

# 停止所有守護進程
.venv/bin/python3 core/daemon_manager.py stop -

# 重啟守護進程
.venv/bin/python3 core/daemon_manager.py restart

**管理特定實例**：

# 停止特定實例
.venv/bin/python3 core/daemon_manager.py stop --config config/active/backpack_eth_usdc_perp_grid.json --daemon
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_sol_01.json --daemon
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_eth_02.json --daemon

# 重啟特定實例
.venv/bin/python3 core/daemon_manager.py restart --config config/active/bp_eth_02.json

# 查看特定實例狀態
.venv/bin/python3 core/daemon_manager.py status --config config/active/bp_sol_01.json
```

```

### 調整運行中的網格範圍

# 如果機器人正在運行，可以通過 CLI 調整網格上下限：

```bash
# 運行CLI模式
.venv/bin/python3 run.py --cli

選擇選單 10
輸入 Web 控制端地址: http://127.0.0.1:5000
輸入新的上下限
```

**注意**：如果已經激活虛擬環境（`source .venv/bin/activate`），也可以直接使用 `python` 或 `python3`。

### 4. 啟動監控
```bash
# 在另一個終端啟動監控
python monitoring/monitoring.py
```

## 📊 與傳統方案的對比

| 功能 | nohup | 新系統 | 說明 |
|------|-------|--------|------|
| 日誌管理 | 單一文件，無輪轉 | 多文件分類，自動輪轉和壓縮 | 更專業的日誌管理 |
| 錯誤處理 | stderr混合在stdout | 分離的錯誤日誌文件 | 更容易排查問題 |
| 進程守護 | 需要配合&使用 | 內建守護進程化 | 更可靠的後台運行 |
| 自動重啟 | 不支持 | 支持崩潰自動重啟 | 提高系統穩定性 |
| 健康監控 | 無 | 完整的系統和進程監控 | 及時發現問題 |
| 告警通知 | 無 | 支持郵件、Telegram、Webhook | 主動通知管理員 |
| 結構化日誌 | 無 | 支持JSON格式結構化日誌 | 便於程序解析 |
| 性能監控 | 無 | 歷史性能數據收集和分析 | 優化系統性能 |
| SSH斷開後運行 | ✅ | ✅ | 兩者都能實現 |

## 🔗 相關鏈接

- [系統管理完整指南](./README_COMPLETE.md) - **推薦閱讀** - 完整的系統管理文檔
- [策略詳細說明](../strategies/) - 深入了解各種交易策略
- [部署運維指南](../deployment/) - 服務器部署和維護

## 💡 使用建議

1. **生產環境** - 強烈建議使用守護進程模式
2. **監控配置** - 配置告警通知以及時發現問題
3. **資源限制** - 設置合理的內存和CPU限制
4. **定期維護** - 定期檢查日誌和系統狀態

> 💡 **提示**: 詳細的配置說明、高級用法、故障排除等內容，請參閱 [系統管理完整指南](./README_COMPLETE.md)
