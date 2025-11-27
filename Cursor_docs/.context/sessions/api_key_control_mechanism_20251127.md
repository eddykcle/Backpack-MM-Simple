# API Key 控制機制分析

## 日期
2025-11-27

## 問題
不同配置的交易所的 API key 是怎麼控制的？

## 分析結果

根據實施計劃文檔，不同配置的交易所 API key 是通過**環境變量**的方式控制的，這是一種安全且靈活的設計。

## API Key 控制機制

### 1. 環境變量替換系統

配置文件使用 `${VARIABLE_NAME}` 格式來引用環境變量：

```json
{
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}",
    "base_url": "https://api.backpack.exchange",
    "api_version": "v1",
    "default_window": "5000"
  }
}
```

### 2. 環境變量處理函數

系統實現了 `expand_env_vars()` 函數來處理這種替換：

```python
import re
import os

def expand_env_vars(text):
    """將 ${VAR_NAME} 格式替換為環境變量值"""
    pattern = r'\$\{([^}]+)\}'
    
    def replace_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    return re.sub(pattern, replace_var, text)
```

### 3. 不同交易所的環境變量命名

根據模板文件，每個交易所都有對應的環境變量：

- **Backpack**: `${BACKPACK_KEY}`, `${BACKPACK_SECRET}`
- **Aster**: `${ASTER_KEY}`, `${ASTER_SECRET}`
- **Paradex**: `${PARADEX_KEY}`, `${PARADEX_SECRET}`
- **Lighter**: `${LIGHTER_KEY}`, `${LIGHTER_SECRET}`

### 4. 安全優勢

這種設計有以下優勢：

1. **密鑰不存儲在配置文件中**：避免意外提交到版本控制系統
2. **環境隔離**：不同環境（開發、測試、生產）可以使用不同的密鑰
3. **動態配置**：可以在不修改配置文件的情況下更換密鑰
4. **多交易所支持**：可以同時配置多個交易所的密鑰

### 5. 實際使用示例

用戶需要在使用前設置環境變量：

```bash
# 設置 Backpack 密鑰
export BACKPACK_KEY="your_backpack_api_key"
export BACKPACK_SECRET="your_backpack_secret_key"

# 設置 Aster 密鑰
export ASTER_KEY="your_aster_api_key"
export ASTER_SECRET="your_aster_secret_key"
```

或者通過 `.env.example` 文件管理。

### 6. 配置驗證

系統還會在配置驗證時檢查環境變量是否存在，如果環境變量未設置，會保持原始的 `${VAR_NAME}` 格式，這可以幫助用戶識別缺失的環境變量。

## 參考文檔
- `Cursor_docs/.context/decisions/multi_config/multi_config_implementation_plan.md`
- `.env.example`

## 結論

這種環境變量的設計確保了 API 密鑰的安全性和靈活性，同時支持多交易所配置的動態管理。通過將敏感信息與配置文件分離，系統既保持了安全性，又提供了良好的可維護性。