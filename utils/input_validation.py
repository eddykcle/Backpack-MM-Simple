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
        # URL 驗證規則（防止 SSRF 攻擊，只允許本地和內網地址）
        self.add_rule('base_url', ValidationRule(
            name="local_url",
            validator=lambda x: x is None or bool(self.LOCAL_URL_PATTERN.match(str(x))),
            error_message="只允許訪問本地或內網地址 (localhost, 127.0.0.1, 10.x.x.x, 172.16-31.x.x, 192.168.x.x)"
        ))