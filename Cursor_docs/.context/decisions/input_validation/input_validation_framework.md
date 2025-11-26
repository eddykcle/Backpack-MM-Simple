# 輸入驗證框架設計

## 概述

本文檔描述了一個統一的輸入驗證框架，用於解決 code review 中識別的「輸入驗證不足」安全問題。該框架將應用於 Web API 端點、CLI 命令和策略層的參數驗證。

## 風險分析總結

基於 code review 報告和代碼分析，識別出以下主要風險點：

### 1. Web API 端點風險
- **位置**: [`web/server.py:405-410`](web/server.py:405)
- **問題**: `/api/grid/adjust` 端點只檢查數值類型，未驗證價格範圍合理性
- **風險**: 可能導致策略異常行為或資金損失

### 2. CLI 命令風險
- **位置**: [`cli/commands.py:946-950`](cli/commands.py:946)
- **問題**: 直接向用戶輸入的 URL 發送請求，可能被用於 SSRF 攻擊
- **風險**: 服務器端請求偽造攻擊

### 3. 策略層驗證缺失
- **位置**: 多處網格價格參數處理
- **問題**: 缺少價格範圍合理性檢查
- **風險**: 極端值導致策略異常

## 統一驗證框架設計

### 核心組件

#### 1. ValidationRule 類
```python
class ValidationRule:
    def __init__(self, name: str, validator: Callable, error_message: str):
        self.name = name
        self.validator = validator
        self.error_message = error_message
    
    def validate(self, value) -> Tuple[bool, str]:
        try:
            result = self.validator(value)
            return result, self.error_message if not result else ""
        except Exception as e:
            return False, f"驗證失敗: {str(e)}"
```

#### 2. InputValidator 類
```python
class InputValidator:
    def __init__(self):
        self.rules = {}
    
    def add_rule(self, field_name: str, rule: ValidationRule):
        if field_name not in self.rules:
            self.rules[field_name] = []
        self.rules[field_name].append(rule)
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
        errors = {}
        is_valid = True
        
        for field_name, field_rules in self.rules.items():
            field_errors = []
            value = data.get(field_name)
            
            for rule in field_rules:
                valid, error_msg = rule.validate(value)
                if not valid:
                    field_errors.append(error_msg)
                    is_valid = False
            
            if field_errors:
                errors[field_name] = field_errors
        
        return is_valid, errors
```

### 預定義驗證規則

#### 價格驗證規則
```python
# 正數檢查
positive_number = ValidationRule(
    name="positive_number",
    validator=lambda x: x is None or (isinstance(x, (int, float)) and x > 0),
    error_message="必須為正數"
)

# 價格範圍合理性檢查
reasonable_price_range = ValidationRule(
    name="reasonable_price_range",
    validator=lambda x: x is None or (isinstance(x, (int, float)) and 0.0001 <= x <= 1000000),
    error_message="價格超出合理範圍 (0.0001 - 1000000)"
)

# 網格範圍邏輯檢查
grid_range_logic = ValidationRule(
    name="grid_range_logic",
    validator=lambda data: (
        data.get('grid_lower_price') is None or 
        data.get('grid_upper_price') is None or 
        data['grid_lower_price'] < data['grid_upper_price']
    ),
    error_message="網格下限價格必須小於上限價格"
)
```

#### URL 驗證規則（防 SSRF）
```python
# 允許的 URL 模式
ALLOWED_URL_PATTERNS = [
    r'^https?://127\.0\.0\.1:\d+',
    r'^https?://localhost:\d+',
    r'^https?://192\.168\.\d+\.\d+:\d+',
    r'^https?://10\.\d+\.\d+\.\d+:\d+',
]

# URL 白名單驗證
url_whitelist = ValidationRule(
    name="url_whitelist",
    validator=lambda url: any(re.match(pattern, url) for pattern in ALLOWED_URL_PATTERNS),
    error_message="URL 不在允許的白名單內"
)

# 協議檢查
https_only = ValidationRule(
    name="https_only",
    validator=lambda url: url.startswith('https://'),
    error_message="只允許 HTTPS 協議"
)
```

### 應用層驗證器

#### Web API 驗證器
```python
class WebApiValidator(InputValidator):
    def __init__(self):
        super().__init__()
        self._setup_grid_adjust_rules()
    
    def _setup_grid_adjust_rules(self):
        # 網格下限價格驗證
        self.add_rule('grid_lower_price', positive_number)
        self.add_rule('grid_lower_price', reasonable_price_range)
        
        # 網格上限價格驗證
        self.add_rule('grid_upper_price', positive_number)
        self.add_rule('grid_upper_price', reasonable_price_range)
        
        # 網格範圍邏輯驗證（需要同時檢查兩個值）
        self.add_rule('grid_range', grid_range_logic)
```

#### CLI 驗證器
```python
class CliValidator(InputValidator):
    def __init__(self):
        super().__init__()
        self._setup_url_validation()
    
    def _setup_url_validation(self):
        self.add_rule('base_url', url_whitelist)
        self.add_rule('base_url', https_only)
```

#### 策略參數驗證器
```python
class StrategyValidator(InputValidator):
    def __init__(self):
        super().__init__()
        self._setup_strategy_rules()
    
    def _setup_strategy_rules(self):
        # 網格數量驗證
        self.add_rule('grid_num', ValidationRule(
            name="grid_num_range",
            validator=lambda x: isinstance(x, int) and 2 <= x <= 100,
            error_message="網格數量必須在 2-100 之間"
        ))
        
        # 價格範圍百分比驗證
        self.add_rule('price_range_percent', ValidationRule(
            name="price_range_percent",
            validator=lambda x: isinstance(x, (int, float)) and 0.1 <= x <= 50,
            error_message="價格範圍百分比必須在 0.1%-50% 之間"
        ))
```

## 實施計劃

### 階段 1: 創建驗證框架
1. 創建 `utils/input_validation.py` 模塊
2. 實現核心驗證類別
3. 定義預設驗證規則

### 階段 2: Web API 增強
1. 修改 [`web/server.py`](web/server.py) 中的 `/api/grid/adjust` 端點
2. 添加輸入驗證中間件
3. 實現錯誤響應標準化

### 階段 3: CLI 命令增強
1. 修改 [`cli/commands.py`](cli/commands.py) 中的 `grid_adjust_command`
2. 添加 URL 白名單驗證
3. 實現 SSRF 防護

### 階段 4: 策略層增強
1. 修改網格策略初始化邏輯
2. 添加參數合理性檢查
3. 實現運行時參數驗證

### 階段 5: 測試和文檔
1. 編寫單元測試
2. 更新 API 文檔
3. 創建使用指南

## 具體實施細節

### Web API 端點修改

#### 修改前 ([`web/server.py:387-442`](web/server.py:387))
```python
@app.route('/api/grid/adjust', methods=['POST'])
def adjust_grid_range():
    # 現有代碼缺少輸入驗證
    data = request.json or {}
    upper_raw = data.get('grid_upper_price')
    lower_raw = data.get('grid_lower_price')
    
    new_upper = float(upper_raw) if upper_raw is not None else None
    new_lower = float(lower_raw) if lower_raw is not None else None
    # ... 缺少驗證邏輯
```

#### 修改後
```python
from utils.input_validation import WebApiValidator

@app.route('/api/grid/adjust', methods=['POST'])
def adjust_grid_range():
    """在機器人運行期間調整網格上下限"""
    global current_strategy

    if not bot_status.get('running'):
        return jsonify({'success': False, 'message': '機器人未運行，無法調整網格'}), 400

    if not current_strategy:
        return jsonify({'success': False, 'message': '沒有可調整的策略實例'}), 400

    if not hasattr(current_strategy, 'adjust_grid_range'):
        return jsonify({'success': False, 'message': '當前策略不支援網格調整'}), 400

    try:
        data = request.json or {}
        
        # 輸入驗證
        validator = WebApiValidator()
        is_valid, errors = validator.validate(data)
        
        if not is_valid:
            error_messages = []
            for field, field_errors in errors.items():
                error_messages.extend(field_errors)
            
            return jsonify({
                'success': False, 
                'message': '輸入驗證失敗: ' + '; '.join(error_messages)
            }), 400

        # 類型轉換（驗證通過後）
        upper_raw = data.get('grid_upper_price')
        lower_raw = data.get('grid_lower_price')

        new_upper = float(upper_raw) if upper_raw is not None else None
        new_lower = float(lower_raw) if lower_raw is not None else None

    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': '網格上下限必須為數值'}), 400

    if new_lower is None and new_upper is None:
        return jsonify({'success': False, 'message': '請至少提供新的上限或下限'}), 400

    # ... 其餘邏輯保持不變
```

### CLI 命令修改

#### 修改前 ([`cli/commands.py:930-979`](cli/commands.py:930))
```python
def grid_adjust_command():
    """透過 Web 控制端即時調整網格上下限"""
    # 現有代碼缺少 URL 驗證
    base_url_input = input(f"請輸入 Web 控制端地址 (默認 {default_base}): ").strip()
    base_url = base_url_input or default_base
    # ... 直接使用用戶輸入的 URL
```

#### 修改後
```python
from utils.input_validation import CliValidator

def grid_adjust_command():
    """透過 Web 控制端即時調整網格上下限"""
    default_host = os.getenv('WEB_HOST', '127.0.0.1')
    default_port = os.getenv('WEB_PORT', '5000')
    default_base = os.getenv('WEB_API_BASE', f"http://127.0.0.1:{default_port}")

    print("\n=== 網格範圍調整 ===")
    base_url_input = input(f"請輸入 Web 控制端地址 (默認 {default_base}): ").strip()
    base_url = base_url_input or default_base
    base_url = base_url.rstrip('/')

    # URL 驗證
    validator = CliValidator()
    is_valid, errors = validator.validate({'base_url': base_url})
    
    if not is_valid:
        error_messages = []
        for field, field_errors in errors.items():
            error_messages.extend(field_errors)
        
        print(f"錯誤: {'; '.join(error_messages)}")
        print("只允許訪問本地或內網地址，例如:")
        print("  - http://127.0.0.1:5000")
        print("  - https://localhost:5000")
        print("  - http://192.168.1.100:5000")
        return

    # ... 其餘邏輯保持不變
```

### 策略層驗證增強

#### 網格策略初始化驗證
```python
from utils.input_validation import StrategyValidator

class GridStrategy(MarketMaker):
    def __init__(self, ...):
        # 參數驗證
        validator = StrategyValidator()
        params = {
            'grid_num': grid_num,
            'price_range_percent': price_range_percent,
            'grid_lower_price': grid_lower_price,
            'grid_upper_price': grid_upper_price,
        }
        
        is_valid, errors = validator.validate(params)
        if not is_valid:
            error_messages = []
            for field, field_errors in errors.items():
                error_messages.extend(field_errors)
            
            raise ValueError(f"參數驗證失敗: {'; '.join(error_messages)}")
        
        # ... 其餘初始化邏輯
```

## 安全措施

### 1. 防禦性編程
- 所有外部輸入都必須經過驗證
- 使用白名單而非黑名單方法
- 實施多層驗證（類型、範圍、業務邏輯）

### 2. 錯誤處理
- 統一的錯誤響應格式
- 不暴露內部系統信息
- 詳細的驗證失敗日誌

### 3. 日誌記錄
- 記錄所有驗證失敗事件
- 包含客戶端 IP、時間戳、失敗原因
- 定期審查異常模式

## 測試策略

### 單元測試覆蓋
1. 邊界值測試
2. 惡意輸入測試
3. SSRF 攻擊模擬
4. 極端值處理測試

### 集成測試
1. Web API 端到端測試
2. CLI 命令集成測試
3. 策略初始化測試

## 性能考慮

1. **驗證快取**: 對重複驗證的值進行快取
2. **早期退出**: 第一個驗證失敗時立即返回
3. **異步驗證**: 對複雜驗證考慮異步處理

## 維護和擴展

1. **規則註冊機制**: 允許動態註冊新的驗證規則
2. **配置化驗證**: 通過配置文件調整驗證參數
3. **插件化架構**: 支持自定義驗證器

## 總結

這個統一輸入驗證框架將：

1. **解決安全漏洞**: 修復 code review 中識別的所有輸入驗證問題
2. **提高代碼質量**: 統一驗證邏輯，減少重複代碼
3. **增強可維護性**: 集中管理驗證規則，易於更新和擴展
4. **改善用戶體驗**: 提供清晰的錯誤信息和指導

實施這個框架將顯著提升系統的安全性、穩定性和可維護性。