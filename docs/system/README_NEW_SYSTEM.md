# 新的日誌和進程管理系統

## 概述

這個新的系統旨在替代傳統的 `nohup.out`，提供更專業、結構化的日誌管理、進程守護和系統監控功能。

## 主要功能

### 1. 高級日誌管理 (`log_manager.py`)

- **結構化日誌**: 支持JSON格式的結構化日誌，便於程序解析
- **日誌輪轉**: 自動輪轉日誌文件，防止無限增長
- **壓縮存儲**: 自動壓縮舊的日誌文件，節省磁盤空間
- **多級別分類**: 分離一般日誌、錯誤日誌和結構化日誌
- **異步寫入**: 避免日誌寫入阻塞主線程
- **自動清理**: 定期清理超過指定天數的舊日誌

#### 日誌文件結構
```
logs/
├── trading_bot.log              # 主要日誌文件
├── trading_bot_errors.log       # 錯誤日誌
├── trading_bot_structured.log   # 結構化日誌
├── stdout.log                   # 標準輸出
├── stderr.log                   # 標準錯誤
└── process.pid                  # 進程PID文件
```

### 2. 進程守護管理 (`daemon_manager.py`)

- **守護進程化**: 自動將進程轉為守護進程
- **PID管理**: 自動管理PID文件，防止重複啟動
- **自動重啟**: 進程崩潰時自動重啟，支持重試限制
- **健康檢查**: 定期檢查進程健康狀態
- **資源監控**: 監控進程的CPU和內存使用
- **優雅停止**: 支持SIGTERM和SIGINT信號處理

#### 命令行使用
```bash
# 啟動守護進程
python daemon_manager.py start --daemon

# 停止守護進程
python daemon_manager.py stop

# 重啟守護進程
python daemon_manager.py restart

# 查看狀態
python daemon_manager.py status
```

### 3. 系統監控和告警 (`monitoring.py`)

- **系統資源監控**: CPU、內存、磁盤使用率
- **進程狀態監控**: 監控交易機器人進程狀態
- **網絡連接檢查**: 檢查關鍵服務的網絡連接
- **性能數據收集**: 收集歷史性能數據
- **多種告警方式**: 郵件、Telegram、Webhook
- **告警歷史**: 記錄和管理告警歷史

#### 支持的告警類型
- 系統資源告警 (CPU、內存、磁盤)
- 進程狀態告警 (進程不存在、殭屍進程)
- 網絡連接告警 (服務不可達)
- 自定義告警

### 4. 配置文件 (`daemon_config.json`)

```json
{
  "python_path": ".venv/bin/python3",
  "script_path": "run.py",
  "working_dir": ".",
  "log_dir": "logs",
  "max_restart_attempts": 3,
  "restart_delay": 60,
  "health_check_interval": 30,
  "memory_limit_mb": 2048,
  "cpu_limit_percent": 80,
  "auto_restart": true,
  "environment": {},
  "bot_args": ["--exchange", "backpack", "--symbol", "SOL_USDC"]
}
```

## 與 nohup 的對比

| 功能 | nohup | 新系統 |
|------|-------|--------|
| 日誌管理 | 單一文件，無輪轉 | 多文件分類，自動輪轉和壓縮 |
| 錯誤處理 | stderr混合在stdout | 分離的錯誤日誌文件 |
| 進程守護 | 需要配合&使用 | 內建守護進程化 |
| 自動重啟 | 不支持 | 支持崩潰自動重啟 |
| 健康監控 | 無 | 完整的系統和進程監控 |
| 告警通知 | 無 | 支持郵件、Telegram、Webhook |
| 結構化日誌 | 無 | 支持JSON格式結構化日誌 |
| 性能監控 | 無 | 歷史性能數據收集和分析 |

## 快速開始

### 1. 安裝依賴
```bash
pip install psutil requests
```

### 2. 配置系統
編輯 `daemon_config.json` 文件，設置您的交易參數：

```json
{
  "python_path": ".venv/bin/python3",
  "script_path": "run.py",
  "bot_args": [
    "--exchange", "backpack",
    "--market-type", "perp",
    "--symbol", "BTC_USDC_PERP",
    "--strategy", "perp_grid",
    "--grid-type", "short",
    "--grid-lower", "78000",
    "--grid-upper", "102000",
    "--grid-num", "80"
  ]
}
```

### 3. 啟動系統
```bash
# 啟動守護進程
python daemon_manager.py start --daemon

# 查看狀態
python daemon_manager.py status
```

### 4. 啟動監控
```bash
# 在另一個終端啟動監控
python monitoring.py
```

## 高級用法

### 自定義日誌記錄
```python
from log_manager import get_logger

logger = get_logger("my_component")
logger.info("普通日誌消息")
logger.error("錯誤日誌", error_code="E001", details={"field": "value"})
logger.log_structured("INFO", "結構化日誌", {
    "event": "trade_executed",
    "price": 100.5,
    "quantity": 1.5
})
```

### 自定義告警
```python
from monitoring import SystemMonitor, AlertLevel, AlertType

monitor = SystemMonitor(config)
monitor._create_alert(
    AlertLevel.WARNING,
    AlertType.CUSTOM,
    "自定義告警",
    "這是一個自定義告警消息",
    {"custom_data": "value"}
)
```

### 配置通知
編輯監控配置以啟用通知：

```json
{
  "notifications": {
    "email": {
      "enabled": true,
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "username": "your-email@gmail.com",
      "password": "your-app-password",
      "sender": "your-email@gmail.com",
      "recipients": ["recipient@example.com"]
    },
    "telegram": {
      "enabled": true,
      "bot_token": "your-bot-token",
      "chat_ids": ["your-chat-id"]
    },
    "webhook": {
      "urls": ["https://your-webhook-url.com/alert"]
    }
  }
}
```

## 故障排除

### 日誌文件過大
- 系統會自動輪轉和壓縮日誌文件
- 可以手動運行 `cleanup_old_logs()` 清理舊日誌

### 進程無法啟動
- 檢查配置文件中的路徑是否正確
- 查看 `logs/trading_bot_errors.log` 中的錯誤信息
- 確保有足夠的系統資源

### 監控告警過於頻繁
- 調整監控閾值配置
- 增加檢查間隔時間
- 設置告警冷卻時間

## 性能考慮

- **日誌異步寫入**: 不會阻塞主交易邏輯
- **智能輪轉**: 只在需要時進行日誌輪轉
- **資源限制**: 可配置內存和CPU使用限制
- **清理策略**: 自動清理舊日誌，防止磁盤空間耗盡

## 安全建議

- 保護好配置文件中的敏感信息（API密鑰、郵件密碼等）
- 設置適當的文件權限，防止未授權訪問日誌
- 定期審查告警配置，避免信息洩露
- 使用應用專用密碼而非主郵件密碼

## 更新日誌

### v1.0.0 (當前版本)
- 實現基礎的日誌管理系統
- 添加進程守護功能
- 實現系統監控和告警
- 支持多種通知方式
- 提供完整的配置文件支持

## 未來計劃

- [ ] Web界面管理
- [ ] 更多交易所API集成
- [ ] 機器學習異常檢測
- [ ] 分佈式部署支持
- [ ] 更多通知渠道（Slack、Discord等）
- [ ] 性能優化和資源使用優化

## 支持和貢獻

如果您遇到問題或有改進建議，請：
1. 查看日誌文件了解詳細錯誤信息
2. 檢查配置文件格式是否正確
3. 確保所有依賴已正確安裝
4. 提交Issue或Pull Request

## 許可證

本項目採用MIT許可證，詳見LICENSE文件。
