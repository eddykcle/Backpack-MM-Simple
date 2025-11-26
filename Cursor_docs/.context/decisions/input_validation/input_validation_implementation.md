# 輸入驗證實施計劃

## 實施概述

本文檔提供了輸入驗證框架的具體實施步驟，包括代碼修改、測試策略和部署計劃。

## 實施優先級

### 🔴 高優先級（立即修復）
1. **Web API 端點驗證** - 防止直接的攻擊面
2. **CLI URL 驗證** - 防止 SSRF 攻擊
3. **價格範圍合理性檢查** - 防止策略異常

### 🟡 中優先級（後續改進）
4. **策略層全面驗證** - 提高系統穩定性
5. **統一錯誤處理** - 改善用戶體驗
6. **性能優化** - 確保驗證不影響性能

## 詳細實施步驟

### 階段 1: 創建驗證框架核心

#### 1.1 創建 `utils/input_validation.py`

```python
"""
統一輸入驗證框架
用於解決 code review 中識別的輸入驗證不足問題
"""
import re
from typing import Any, Callable, Dict, List, Tuple, Optional
from core.logger import setup_logger

logger = setup_logger("input_validation")

class ValidationError(Exception):
    """驗證錯誤異常"""
    pass

class ValidationRule:
    """單個驗證規則"""
    def __init__(self, name: str, validator: Callable[[Any], bool], error_message: str):
        self.name = name
        self.validator = validator
        self.error_message = error_message
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        """驗證給定值"""
        try:
            if value is None:
                # None 值通常表示可選參數，除非有特殊規則
                return True, ""
            result = self.validator(value)
            return result, self.error_message if not result else ""
        except Exception as e:
            logger.warning(f"驗證規則 {self.name} 執行失敗: {e}")
            return False, f"驗證失敗: {str(e)}"

class InputValidator:
    """輸入驗證器主類"""
    def __init__(self, name: str = "default"):
        self.name = name
        self.rules: Dict[str, List[ValidationRule]] = {}
        self.cross_field_rules: List[ValidationRule] = []
    
    def add_rule(self, field_name: str, rule: ValidationRule):
        """添加字段驗證規則"""
        if field_name not in self.rules:
            self.rules[field_name] = []
        self.rules[field_name].append(rule)
        logger.debug(f"為驗證器 {self.name} 添加規則 {rule.name} 到字段 {field_name}")
    
    def add_cross_field_rule(self, rule: ValidationRule):
        """添加跨字段驗證規則"""
        self.cross_field_rules.append(rule)
        logger.debug(f"為驗證器 {self.name} 添加跨字段規則 {rule.name}")
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
        """驗證輸入數據"""
        errors: Dict[str, List[str]] = {}
        is_valid = True
        
        logger.debug(f"開始驗證數據: {data}")
        
        # 單字段驗證
        for field_name, field_rules in self.rules.items():
            field_errors: List[str] = []
            value = data.get(field_name)
            
            for rule in field_rules:
                valid, error_msg = rule.validate(value)
                if not valid:
                    field_errors.append(error_msg)
                    is_valid = False
                    logger.warning(f"字段 {field_name} 驗證失敗: {error_msg}")
            
            if field_errors:
                errors[field_name] = field_errors
        
        # 跨字段驗證
        for rule in self.cross_field_rules:
            valid, error_msg = rule.validate(data)
            if not valid:
                # 跨字段錯誤添加到通用錯誤字段
                if "general" not in errors:
                    errors["general"] = []
                errors["general"].append(error_msg)
                is_valid = False
                logger.warning(f"跨字段驗證失敗: {error_msg}")
        
        logger.debug(f"驗證完成: {'通過' if is_valid else '失敗'}")
        if errors:
            logger.debug(f"驗證錯誤: {errors}")
        
        return is_valid, errors

# 預定義驗證規則
class CommonRules:
    """常用驗證規則集合"""
    
    # 基本類型驗證
    POSITIVE_NUMBER = ValidationRule(
        name="positive_number",
        validator=lambda x: isinstance(x, (int, float)) and x > 0,
        error_message="必須為正數"
    )
    
    NON_NEGATIVE_NUMBER = ValidationRule(
        name="non_negative_number",
        validator=lambda x: isinstance(x, (int, float)) and x >= 0,
        error_message="必須為非負數"
    )
    
    # 價格驗證
    REASONABLE_PRICE = ValidationRule(
        name="reasonable_price",
        validator=lambda x: isinstance(x, (int, float)) and 0.0001 <= x <= 1000000,
        error_message="價格超出合理範圍 (0.0001 - 1000000)"
    )
    
    # 網格參數驗證
    GRID_NUM_RANGE = ValidationRule(
        name="grid_num_range",
        validator=lambda x: isinstance(x, int) and 2 <= x <= 100,
        error_message="網格數量必須在 2-100 之間"
    )
    
    PERCENTAGE_RANGE = ValidationRule(
        name="percentage_range",
        validator=lambda x: isinstance(x, (int, float)) and 0.1 <= x <= 50,
        error_message="百分比必須在 0.1%-50% 之間"
    )
    
    # URL 驗證（防 SSRF）
    URL_PATTERN = re.compile(
        r'^https?://'
        r'(127\.0\.0\.1|localhost|'
        r'192\.168\.\d+\.\d+|'
        r'10\.\d+\.\d+\.\d+|'
        r'172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+)'
        r'(?::\d+)?'
        r'(?:/.*)?$',
        re.IGNORECASE
    )
    
    SAFE_URL = ValidationRule(
        name="safe_url",
        validator=lambda url: bool(CommonRules.URL_PATTERN.match(url)),
        error_message="URL 不在允許的白名單內（只允許本地和內網地址）"
    )
    
    HTTPS_ONLY = ValidationRule(
        name="https_only",
        validator=lambda url: url.startswith('https://'),
        error_message="只允許 HTTPS 協議"
    )
    
    @staticmethod
    def grid_range_logic():
        """網格範圍邏輯驗證（跨字段）"""
        return ValidationRule(
            name="grid_range_logic",
            validator=lambda data: (
                data.get('grid_lower_price') is None or 
                data.get('grid_upper_price') is None or 
                data['grid_lower_price'] < data['grid_upper_price']
            ),
            error_message="網格下限價格必須小於上限價格"
        )
```

#### 1.2 創建專用驗證器

```python
# 在同一文件中繼續添加

class WebApiValidator(InputValidator):
    """Web API 專用驗證器"""
    def __init__(self):
        super().__init__("web_api")
        self._setup_grid_adjust_rules()
    
    def _setup_grid_adjust_rules(self):
        """設置網格調整驗證規則"""
        # 網格下限價格驗證
        self.add_rule('grid_lower_price', CommonRules.POSITIVE_NUMBER)
        self.add_rule('grid_lower_price', CommonRules.REASONABLE_PRICE)
        
        # 網格上限價格驗證
        self.add_rule('grid_upper_price', CommonRules.POSITIVE_NUMBER)
        self.add_rule('grid_upper_price', CommonRules.REASONABLE_PRICE)
        
        # 跨字段驗證
        self.add_cross_field_rule(CommonRules.grid_range_logic())

class CliValidator(InputValidator):
    """CLI 專用驗證器"""
    def __init__(self):
        super().__init__("cli")
        self._setup_url_validation()
    
    def _setup_url_validation(self):
        """設置 URL 驗證規則"""
        self.add_rule('base_url', CommonRules.SAFE_URL)
        # 注意：HTTPS_ONLY 視具體需求而定，內網可能用 HTTP

class StrategyValidator(InputValidator):
    """策略參數專用驗證器"""
    def __init__(self):
        super().__init__("strategy")
        self._setup_strategy_rules()
    
    def _setup_strategy_rules(self):
        """設置策略參數驗證規則"""
        # 網格數量驗證
        self.add_rule('grid_num', CommonRules.GRID_NUM_RANGE)
        
        # 價格範圍百分比驗證
        self.add_rule('price_range_percent', CommonRules.PERCENTAGE_RANGE)
        
        # 網格價格驗證
        self.add_rule('grid_lower_price', CommonRules.POSITIVE_NUMBER)
        self.add_rule('grid_lower_price', CommonRules.REASONABLE_PRICE)
        
        self.add_rule('grid_upper_price', CommonRules.POSITIVE_NUMBER)
        self.add_rule('grid_upper_price', CommonRules.REASONABLE_PRICE)
        
        # 跨字段驗證
        self.add_cross_field_rule(CommonRules.grid_range_logic())
```

### 階段 2: 修改 Web API 端點

#### 2.1 修改 `web/server.py` 中的 `/api/grid/adjust` 端點

```python
# 在文件頂部添加導入
from utils.input_validation import WebApiValidator, ValidationError

# 替換原有的 adjust_grid_range 函數
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
            # 格式化錯誤信息
            error_messages = []
            for field, field_errors in errors.items():
                if field == "general":
                    error_messages.extend(field_errors)
                else:
                    for error in field_errors:
                        error_messages.append(f"{field}: {error}")
            
            logger.warning(f"網格調整請求驗證失敗: {error_messages}")
            return jsonify({
                'success': False, 
                'message': '輸入驗證失敗: ' + '; '.join(error_messages)
            }), 400

        # 類型轉換（驗證通過後）
        upper_raw = data.get('grid_upper_price')
        lower_raw = data.get('grid_lower_price')

        new_upper = float(upper_raw) if upper_raw is not None else None
        new_lower = float(lower_raw) if lower_raw is not None else None

    except (TypeError, ValueError) as e:
        logger.error(f"網格調整參數類型轉換失敗: {e}")
        return jsonify({'success': False, 'message': '網格上下限必須為數值'}), 400

    if new_lower is None and new_upper is None:
        return jsonify({'success': False, 'message': '請至少提供新的上限或下限'}), 400

    try:
        success = current_strategy.adjust_grid_range(new_lower, new_upper)
    except Exception as exc:
        logger.error("調整網格範圍時發生例外: %s", exc)
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'調整失敗: {exc}'}), 500

    if not success:
        return jsonify({'success': False, 'message': '策略拒絕調整或初始化失敗'}), 400

    stats_update = {
        'grid_lower_price': getattr(current_strategy, 'grid_lower_price', None),
        'grid_upper_price': getattr(current_strategy, 'grid_upper_price', None),
    }
    socketio.emit('grid_adjusted', stats_update)

    logger.info(
        "網格範圍調整成功: %.4f ~ %.4f",
        stats_update['grid_lower_price'] or 0,
        stats_update['grid_upper_price'] or 0,
    )

    return jsonify({
        'success': True,
        'message': '網格範圍已更新',
        'grid_lower_price': stats_update['grid_lower_price'],
        'grid_upper_price': stats_update['grid_upper_price'],
    })
```

#### 2.2 添加 API 錯誤處理中間件

```python
# 在 web/server.py 中添加
@app.errorhandler(ValidationError)
def handle_validation_error(error):
    """處理驗證錯誤"""
    return jsonify({
        'success': False,
        'message': f'驗證錯誤: {str(error)}'
    }), 400

@app.errorhandler(400)
def handle_bad_request(error):
    """處理錯誤請求"""
    return jsonify({
        'success': False,
        'message': '請求格式錯誤'
    }), 400
```

### 階段 3: 修改 CLI 命令

#### 3.1 修改 `cli/commands.py` 中的 `grid_adjust_command`

```python
# 在文件頂部添加導入
from utils.input_validation import CliValidator, ValidationError

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
        
        print(f"❌ 錯誤: {'; '.join(error_messages)}")
        print("\n📋 安全提示:")
        print("  只允許訪問本地或內網地址，例如:")
        print("    - http://127.0.0.1:5000")
        print("    - https://localhost:5000")
        print("    - http://192.168.1.100:5000")
        print("    - http://10.0.0.50:5000")
        print("  不允許訪問外部網址，防止 SSRF 攻擊")
        return

    lower_input = input("新的網格下限價格 (留空沿用當前設定): ").strip()
    upper_input = input("新的網格上限價格 (留空沿用當前設定): ").strip()

    payload = {}
    try:
        if lower_input:
            payload['grid_lower_price'] = float(lower_input)
        if upper_input:
            payload['grid_upper_price'] = float(upper_input)
    except ValueError:
        print("❌ 錯誤: 請輸入有效的數值。")
        return

    if not payload:
        print("⚠️  未輸入任何新範圍，操作已取消。")
        return

    endpoint = f"{base_url}/api/grid/adjust"
    print(f"🔄 正在向 {endpoint} 發送調整請求...")

    try:
        # 添加超時和驗證
        response = requests.post(
            endpoint, 
            json=payload, 
            timeout=15,
            headers={'Content-Type': 'application/json'}
        )
    except requests.exceptions.Timeout:
        print("❌ 錯誤: 請求超時，請檢查網絡連接或服務器狀態")
        return
    except requests.exceptions.ConnectionError:
        print("❌ 錯誤: 無法連接到服務器，請檢查地址是否正確")
        return
    except requests.RequestException as exc:
        print(f"❌ 錯誤: 發送請求失敗: {exc}")
        return

    try:
        result = response.json()
    except ValueError:
        print(f"❌ 錯誤: 服務端返回非JSON響應: {response.text}")
        return

    if response.ok and result.get('success'):
        lower = result.get('grid_lower_price')
        upper = result.get('grid_upper_price')
        print(f"✅ 網格範圍調整成功，新區間: {lower} ~ {upper}")
    else:
        message = result.get('message') if isinstance(result, dict) else response.text
        print(f"❌ 網格調整失敗: {message}")
```

### 階段 4: 增強策略層驗證

#### 4.1 修改 `strategies/grid_strategy.py`

```python
# 在文件頂部添加導入
from utils.input_validation import StrategyValidator, ValidationError

class GridStrategy(MarketMaker):
    def __init__(
        self,
        # ... 現有參數
        **kwargs,
    ) -> None:
        # 參數驗證
        self._validate_initialization_params(
            grid_lower_price, grid_upper_price, grid_num, 
            price_range_percent, order_quantity
        )
        
        # ... 現有初始化邏輯
    
    def _validate_initialization_params(
        self, 
        grid_lower_price: Optional[float],
        grid_upper_price: Optional[float], 
        grid_num: int,
        price_range_percent: float,
        order_quantity: Optional[float]
    ):
        """驗證初始化參數"""
        validator = StrategyValidator()
        params = {
            'grid_lower_price': grid_lower_price,
            'grid_upper_price': grid_upper_price,
            'grid_num': grid_num,
            'price_range_percent': price_range_percent,
        }
        
        # 只有在提供 order_quantity 時才驗證
        if order_quantity is not None:
            params['order_quantity'] = order_quantity
            validator.add_rule('order_quantity', CommonRules.POSITIVE_NUMBER)
        
        is_valid, errors = validator.validate(params)
        
        if not is_valid:
            error_messages = []
            for field, field_errors in errors.items():
                if field == "general":
                    error_messages.extend(field_errors)
                else:
                    for error in field_errors:
                        error_messages.append(f"{field}: {error}")
            
            raise ValidationError(f"網格策略參數驗證失敗: {'; '.join(error_messages)}")
    
    def adjust_grid_range(
        self,
        new_lower_price: Optional[float] = None,
        new_upper_price: Optional[float] = None,
    ) -> bool:
        """
        在策略運行期間動態調整網格上下限並重新初始化網格。
        """
        with self.grid_operation_lock:
            if new_lower_price is None and new_upper_price is None:
                logger.error("未提供新的網格上下限，調整已取消")
                return False

            # 驗證新參數
            validator = StrategyValidator()
            params = {
                'grid_lower_price': new_lower_price,
                'grid_upper_price': new_upper_price,
            }
            
            is_valid, errors = validator.validate(params)
            
            if not is_valid:
                error_messages = []
                for field, field_errors in errors.items():
                    if field == "general":
                        error_messages.extend(field_errors)
                    else:
                        for error in field_errors:
                            error_messages.append(error)
                
                logger.error(f"網格範圍調整參數驗證失敗: {'; '.join(error_messages)}")
                return False

            # ... 其餘邏輯保持不變
```

### 階段 5: 測試策略

#### 5.1 創建測試文件 `tests/test_input_validation.py`

```python
"""
輸入驗證框架測試
"""
import pytest
from utils.input_validation import (
    WebApiValidator, CliValidator, StrategyValidator,
    CommonRules, ValidationError
)

class TestCommonRules:
    """測試常用驗證規則"""
    
    def test_positive_number(self):
        """測試正數驗證"""
        assert CommonRules.POSITIVE_NUMBER.validate(1.0)[0] == True
        assert CommonRules.POSITIVE_NUMBER.validate(0)[0] == False
        assert CommonRules.POSITIVE_NUMBER.validate(-1)[0] == False
        assert CommonRules.POSITIVE_NUMBER.validate(None)[0] == True  # 可選參數
    
    def test_reasonable_price(self):
        """測試合理價格驗證"""
        assert CommonRules.REASONABLE_PRICE.validate(100.0)[0] == True
        assert CommonRules.REASONABLE_PRICE.validate(0.0001)[0] == True
        assert CommonRules.REASONABLE_PRICE.validate(0.00001)[0] == False
        assert CommonRules.REASONABLE_PRICE.validate(1000001)[0] == False
    
    def test_safe_url(self):
        """測試安全 URL 驗證"""
        valid_urls = [
            "http://127.0.0.1:5000",
            "https://localhost:5000",
            "http://192.168.1.100:5000",
            "http://10.0.0.50:5000",
        ]
        
        invalid_urls = [
            "https://google.com",
            "http://example.com",
            "ftp://127.0.0.1:5000",
        ]
        
        for url in valid_urls:
            assert CommonRules.SAFE_URL.validate(url)[0] == True, f"URL {url} 應該有效"
        
        for url in invalid_urls:
            assert CommonRules.SAFE_URL.validate(url)[0] == False, f"URL {url} 應該無效"

class TestWebApiValidator:
    """測試 Web API 驗證器"""
    
    def test_valid_grid_adjust_data(self):
        """測試有效的網格調整數據"""
        validator = WebApiValidator()
        data = {
            'grid_lower_price': 100.0,
            'grid_upper_price': 200.0,
        }
        
        is_valid, errors = validator.validate(data)
        assert is_valid == True
        assert errors == {}
    
    def test_invalid_grid_range(self):
        """測試無效的網格範圍"""
        validator = WebApiValidator()
        data = {
            'grid_lower_price': 200.0,
            'grid_upper_price': 100.0,  # 上限小於下限
        }
        
        is_valid, errors = validator.validate(data)
        assert is_valid == False
        assert "general" in errors
    
    def test_extreme_prices(self):
        """測試極端價格"""
        validator = WebApiValidator()
        data = {
            'grid_lower_price': 0.00001,  # 太小
            'grid_upper_price': 1000000.0,
        }
        
        is_valid, errors = validator.validate(data)
        assert is_valid == False
        assert "grid_lower_price" in errors

class TestCliValidator:
    """測試 CLI 驗證器"""
    
    def test_valid_local_urls(self):
        """測試有效的本地 URL"""
        validator = CliValidator()
        valid_urls = [
            "http://127.0.0.1:5000",
            "https://localhost:5000",
        ]
        
        for url in valid_urls:
            data = {'base_url': url}
            is_valid, errors = validator.validate(data)
            assert is_valid == True, f"URL {url} 應該有效"
    
    def test_invalid_external_urls(self):
        """測試無效的外部 URL"""
        validator = CliValidator()
        invalid_urls = [
            "https://google.com",
            "http://example.com",
        ]
        
        for url in invalid_urls:
            data = {'base_url': url}
            is_valid, errors = validator.validate(data)
            assert is_valid == False, f"URL {url} 應該無效"
            assert "base_url" in errors

class TestStrategyValidator:
    """測試策略驗證器"""
    
    def test_valid_strategy_params(self):
        """測試有效的策略參數"""
        validator = StrategyValidator()
        data = {
            'grid_num': 10,
            'price_range_percent': 5.0,
            'grid_lower_price': 100.0,
            'grid_upper_price': 200.0,
        }
        
        is_valid, errors = validator.validate(data)
        assert is_valid == True
        assert errors == {}
    
    def test_invalid_grid_num(self):
        """測試無效的網格數量"""
        validator = StrategyValidator()
        data = {
            'grid_num': 1,  # 太少
        }
        
        is_valid, errors = validator.validate(data)
        assert is_valid == False
        assert "grid_num" in errors
```

#### 5.2 創建集成測試

```python
# tests/test_web_api_validation.py
"""
Web API 驗證集成測試
"""
import pytest
import json
from web.server import app

class TestGridAdjustValidation:
    """測試網格調整 API 驗證"""
    
    def test_valid_request(self, client):
        """測試有效請求"""
        response = client.post('/api/grid/adjust', 
            json={'grid_lower_price': 100.0, 'grid_upper_price': 200.0})
        
        assert response.status_code == 400  # 因為機器人未運行，但驗證應通過
        data = json.loads(response.data)
        assert '輸入驗證失敗' not in data['message']
    
    def test_invalid_price_range(self, client):
        """測試無效價格範圍"""
        response = client.post('/api/grid/adjust',
            json={'grid_lower_price': 200.0, 'grid_upper_price': 100.0})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert '輸入驗證失敗' in data['message']
    
    def test_extreme_prices(self, client):
        """測試極端價格"""
        response = client.post('/api/grid/adjust',
            json={'grid_lower_price': 0.00001, 'grid_upper_price': 200.0})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert '輸入驗證失敗' in data['message']
```

## 部署計劃

### 階段 1: 框架開發（1-2 天）
1. 創建 `utils/input_validation.py`
2. 實現核心驗證類別
3. 編寫單元測試

### 階段 2: Web API 修改（1 天）
1. 修改 `/api/grid/adjust` 端點
2. 添加錯誤處理中間件
3. 編寫集成測試

### 階段 3: CLI 修改（1 天）
1. 修改 `grid_adjust_command`
2. 添加 SSRF 防護
3. 編寫測試

### 階段 4: 策略層修改（1-2 天）
1. 修改網格策略初始化
2. 添加運行時驗證
3. 編寫測試

### 階段 5: 測試和部署（1 天）
1. 運行完整測試套件
2. 性能測試
3. 文檔更新
4. 生產部署

## 風險緩解

### 1. 向後兼容性
- 保持現有 API 響應格式
- 添加可選的驗證開關
- 漸進式部署

### 2. 性能影響
- 驗證規則快取
- 早期退出機制
- 異步處理選項

### 3. 錯誤處理
- 詳細的日誌記錄
- 用戶友好的錯誤信息
- 優雅降級機制

## 監控和維護

### 1. 日誌監控
- 監控驗證失敗率
- 異常模式檢測
- 性能指標追蹤

### 2. 定期審查
- 驗證規則有效性檢查
- 新攻擊向量評估
- 規則更新需求評估

## 總結

這個實施計劃提供了：

1. **全面的安全修復**: 解決所有 code review 中識別的輸入驗證問題
2. **結構化的方法**: 分階段實施，降低風險
3. **完整的測試覆蓋**: 確保修改的正確性和穩定性
4. **可維護的架構**: 易於擴展和更新的驗證框架

實施這個計劃將顯著提升系統的安全性和穩定性。