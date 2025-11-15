# Uptime Kuma 監聽設置指南

## 功能說明

現在當你使用 terminal 執行策略時，程序會自動在後台啟動 Web 服務器，提供健康檢查端點供 Uptime Kuma 監聽。

## 使用方法

### 1. 執行策略命令

使用daemon系統來管理策略進程（推薦方式）：

```bash
# 使用daemon系統啟動策略
python3 core/daemon_manager.py start --daemon

# 或者指定配置文件路徑
python3 core/daemon_manager.py start --daemon --config config/daemon_config.json

# 或者直接在終端執行策略（daemon會自動管理）
python3 run.py \
  --exchange backpack \
  --market-type perp \
  --symbol BTC_USDC_PERP \
  --strategy perp_grid \
  --grid-type short \
  --grid-lower 78000 \
  --grid-upper 102000 \
  --grid-num 80 \
  --grid-mode geometric \
  --max-position 0.03 \
  --stop-loss 375 \
  --take-profit 500 \
  --duration 1209600 \
  --interval 300
```

### 2. Web 服務器自動啟動

執行上述命令後，程序會自動：
- 在後台啟動 Web 服務器（端口 5000）
- 提供健康檢查端點

### 3. 健康檢查端點

- **健康檢查**: `http://localhost:5000/health`
- **詳細狀態**: `http://localhost:5000/health/detailed`
- **Web 界面**: `http://localhost:5000`

### 4. Uptime Kuma 設置

在 Uptime Kuma 中添加監聽：

1. 添加新的監聽
2. 監聽類型選擇 "HTTP(s)"
3. URL 填寫: `http://你的服務器IP:5000/health`
4. 設置合適的檢查間隔（建議 60 秒）
5. 保存設置

## 響應說明

### 策略運行中 (HTTP 200)
```json
{
  "status": "healthy",
  "running": true,
  "timestamp": "2024-01-01T12:00:00"
}
```

### 策略停止 (HTTP 503)
```json
{
  "status": "unhealthy", 
  "running": false,
  "timestamp": "2024-01-01T12:00:00"
}
```

## 測試功能

你可以使用 curl 測試健康檢查端點：

```bash
# 測試健康檢查端點
curl http://localhost:5000/health

# 測試詳細狀態端點
curl http://localhost:5000/health/detailed
```

## 注意事項

1. **端口衝突**: 如果端口 5000 被占用，服務器會自動尋找其他可用端口
2. **防火牆**: 確保服務器的 5000 端口對外開放
3. **遠程訪問**: 使用服務器IP地址而非 localhost 進行遠程監聽

## 故障排除

### Web 服務器未啟動
檢查日誌中是否有相關錯誤信息，通常會顯示：
```
Web服務器已在後台啟動，可通過 http://localhost:5000 訪問
健康檢查端點: http://localhost:5000/health
```

### Uptime Kuma 顯示離線
1. 確認 Web 服務器已啟動
2. 檢查網絡連接
3. 確認 URL 格式正確：`http://IP:5000/health`

## 技術實現

此功能通過以下方式實現：
1. 修改 `run.py` 在 terminal 執行策略時自動啟動 Web 服務器
2. 在 `web/server.py` 中添加健康檢查端點
3. 根據策略運行狀態返回相應的 HTTP 狀態碼

## 相關文件位置

- **守護進程管理器**: `core/daemon_manager.py`
- **配置文件**: `config/daemon_config.json`
- **主程序**: `run.py`
- **Web服務器**: `web/server.py`
