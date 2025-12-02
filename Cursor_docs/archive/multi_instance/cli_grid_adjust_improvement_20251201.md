# CLI 網格調整功能多實例支持改進

**日期**: 2025-12-01  
**狀態**: 已完成  
**類型**: 功能改進  

## 問題背景

在多實例運行環境下，CLI 的網格調整功能 (`grid_adjust_command`) 存在以下問題：

1. **需要記住端口號**: 用戶必須記住每個實例對應的 Web 端口
2. **無法自動發現實例**: CLI 沒有利用 `InstanceRegistry` 來列出運行中的實例
3. **默認端口錯誤**: 默認使用 5000 端口，但多實例通常從 5001 開始

## 解決方案

### 改進項目

| 改進項 | 描述 |
|--------|------|
| 實例列表顯示 | 自動掃描運行中的實例，顯示實例ID、交易對、端口、策略 |
| 實例ID選擇 | 支持輸入 `bp_sol_01` 直接選擇，不需要記住端口 |
| 智能默認 | 只有一個實例時自動選擇，無需用戶輸入 |
| 多種輸入方式 | 支持序號、實例ID、端口號、完整URL |
| 狀態預覽 | 調整前顯示當前網格範圍和價格 |
| 安全驗證 | 防止 SSRF 攻擊，只允許本地/內網地址 |

## 實現細節

### 1. 新增 `CliValidator` 類

**文件**: `utils/input_validation.py`

```python
class CliValidator(InputValidator):
    """CLI 輸入專用驗證器"""
    
    # URL 驗證正則表達式（僅允許本地和內網地址）
    LOCAL_URL_PATTERN = re.compile(
        r'^https?://'
        r'(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|'
        r'172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}|'
        r'192\.168\.\d{1,3}\.\d{1,3})'
        r'(:\d{1,5})?'
        r'(/.*)?$',
        re.IGNORECASE
    )
    
    def __init__(self):
        super().__init__("cli")
        self._setup_cli_rules()
    
    def _setup_cli_rules(self):
        """設置 CLI 驗證規則"""
        self.add_rule('base_url', ValidationRule(
            name="local_url",
            validator=lambda x: x is None or bool(self.LOCAL_URL_PATTERN.match(str(x))),
            error_message="只允許訪問本地或內網地址"
        ))
```

### 2. 新增輔助函數

**文件**: `cli/commands.py`

| 函數 | 功能 |
|------|------|
| `_get_running_instances()` | 獲取運行中的實例列表（支持 InstanceRegistry 和配置文件掃描雙重機制） |
| `_scan_active_configs_for_ports()` | 掃描活躍配置文件獲取端口信息 |
| `_check_port_responsive()` | 檢查端口是否有響應的服務 |
| `_display_running_instances()` | 格式化顯示運行中的實例列表 |
| `_select_instance()` | 用戶選擇實例（支持序號/實例ID/URL/端口） |

### 3. 實例發現機制

採用雙重機制確保實例能被發現：

1. **InstanceRegistry 優先**: 從 `logs/instances.json` 讀取已註冊的實例
2. **配置文件掃描備用**: 掃描 `config/active/*.json` 獲取端口配置
3. **健康檢查驗證**: 通過 `/health` 端點確認服務是否運行

```python
def _get_running_instances() -> List[Dict[str, Any]]:
    registry = InstanceRegistry()
    running_instances = []
    
    # 從 InstanceRegistry 獲取運行中的實例
    instances = registry.list_instances(include_dead=False)
    
    for inst in instances:
        # 處理實例信息...
        
    # 如果 InstanceRegistry 沒有數據，嘗試從活躍配置文件中掃描
    if not running_instances:
        running_instances = _scan_active_configs_for_ports()
    
    return running_instances
```

## 用戶交互示例

### 場景 1: 多個實例運行時

```
==================================================
        🔧 網格範圍調整工具
==================================================

📋 運行中的實例 (2 個):
──────────────────────────────────────────────────────────────────────
序號 實例ID           交易對              端口   策略        
──────────────────────────────────────────────────────────────────────
1    bp_sol_01        SOL_USDC_PERP       5001   perp_grid   
2    bp_eth_02        ETH_USDC_PERP       5002   perp_grid   
──────────────────────────────────────────────────────────────────────

請選擇要調整的實例:
  輸入序號 (1, 2, ...) 選擇對應實例
  輸入實例ID (如 bp_sol_01) 直接選擇
  輸入完整地址 (如 http://127.0.0.1:5001) 直接使用
  按 Enter 取消操作

請選擇: bp_sol_01

📍 目標地址: http://127.0.0.1:5001

📊 當前網格狀態:
   網格範圍: 121.0 ~ 135.0
   當前價格: 128.5

--------------------------------------------------
新的網格下限價格 (留空沿用當前設定): 118
新的網格上限價格 (留空沿用當前設定): 140

🔄 正在向 http://127.0.0.1:5001/api/grid/adjust 發送調整請求...

✅ 網格範圍調整成功!
   新區間: 118.0 ~ 140.0
```

### 場景 2: 單個實例運行時（自動選擇）

```
==================================================
        🔧 網格範圍調整工具
==================================================

📋 運行中的實例 (1 個):
──────────────────────────────────────────────────────────────────────
序號 實例ID           交易對              端口   策略        
──────────────────────────────────────────────────────────────────────
1    bp_sol_01        SOL_USDC_PERP       5001   perp_grid   
──────────────────────────────────────────────────────────────────────

🎯 自動選擇唯一運行的實例: bp_sol_01 (SOL_USDC_PERP)

📍 目標地址: http://127.0.0.1:5001
...
```

### 場景 3: 無運行實例時

```
==================================================
        🔧 網格範圍調整工具
==================================================

📋 未發現運行中的實例
   提示: 請確保實例已啟動並配置了 Web 端口

💡 您也可以手動輸入 Web 控制端地址

請輸入 Web 控制端地址 (默認 http://127.0.0.1:5000, 按 Enter 取消): 
```

## 修改的文件

1. **`utils/input_validation.py`**
   - 新增 `CliValidator` 類，用於 CLI URL 驗證

2. **`cli/commands.py`**
   - 新增導入: `CliValidator`, `InstanceRegistry`, 類型提示
   - 新增 `_get_running_instances()` 函數
   - 新增 `_scan_active_configs_for_ports()` 函數
   - 新增 `_check_port_responsive()` 函數
   - 新增 `_display_running_instances()` 函數
   - 新增 `_select_instance()` 函數
   - 重寫 `grid_adjust_command()` 函數

## 向後兼容性

- ✅ 完全向後兼容
- 仍支持手動輸入 URL 地址
- 環境變量 `WEB_HOST`, `WEB_PORT`, `WEB_API_BASE` 仍然有效

## 安全考慮

- URL 驗證只允許本地和內網地址
- 防止 SSRF（服務端請求偽造）攻擊
- 支持的地址範圍:
  - `localhost`
  - `127.0.0.1`
  - `10.x.x.x` (Class A 私有網絡)
  - `172.16-31.x.x` (Class B 私有網絡)
  - `192.168.x.x` (Class C 私有網絡)

## 測試建議

1. 啟動單個實例，驗證自動選擇功能
2. 啟動多個實例，測試各種選擇方式（序號、ID、URL、端口）
3. 無實例運行時，測試手動輸入流程
4. 驗證安全限制（嘗試輸入外部 URL）
