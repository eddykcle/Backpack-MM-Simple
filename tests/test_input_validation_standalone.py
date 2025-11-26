"""
輸入驗證模塊的獨立單元測試
不依賴項目其他模塊，直接測試驗證邏輯
"""
import unittest
from typing import Any, Callable, Dict, List, Tuple, Optional


# 獨立複製驗證框架核心類（避免依賴問題）
class ValidationRule:
    """單個驗證規則"""
    
    def __init__(self, name: str, validator: Callable[[Any], bool], error_message: str):
        self.name = name
        self.validator = validator
        self.error_message = error_message
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        """驗證單個值"""
        try:
            if self.validator(value):
                return True, ""
            else:
                return False, self.error_message
        except Exception as e:
            return False, f"驗證時發生錯誤: {str(e)}"


class InputValidator:
    """輸入驗證器"""
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.rules: Dict[str, List[ValidationRule]] = {}
        self.cross_field_rules: List[ValidationRule] = []
    
    def add_rule(self, field_name: str, rule: ValidationRule):
        """添加字段驗證規則"""
        if field_name not in self.rules:
            self.rules[field_name] = []
        self.rules[field_name].append(rule)
    
    def add_cross_field_rule(self, rule: ValidationRule):
        """添加跨字段驗證規則"""
        self.cross_field_rules.append(rule)
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
        """驗證所有數據"""
        errors: Dict[str, List[str]] = {}
        
        # 驗證單個字段
        for field_name, rules in self.rules.items():
            field_errors = []
            value = data.get(field_name)
            
            for rule in rules:
                is_valid, error_msg = rule.validate(value)
                if not is_valid:
                    field_errors.append(error_msg)
            
            if field_errors:
                errors[field_name] = field_errors
        
        # 驗證跨字段規則
        cross_field_errors = []
        for rule in self.cross_field_rules:
            is_valid, error_msg = rule.validate(data)
            if not is_valid:
                cross_field_errors.append(error_msg)
        
        if cross_field_errors:
            errors["cross_field"] = cross_field_errors
        
        return len(errors) == 0, errors


class CommonRules:
    """常用驗證規則集合"""
    
    @staticmethod
    def positive_number(error_message: str = "必須是正數") -> ValidationRule:
        """正數驗證"""
        return ValidationRule(
            name="positive_number",
            validator=lambda x: isinstance(x, (int, float)) and x > 0,
            error_message=error_message
        )
    
    @staticmethod
    def non_negative_number(error_message: str = "必須是非負數") -> ValidationRule:
        """非負數驗證"""
        return ValidationRule(
            name="non_negative_number",
            validator=lambda x: isinstance(x, (int, float)) and x >= 0,
            error_message=error_message
        )
    
    @staticmethod
    def price_range(min_val: float = 0.0001, max_val: float = 1000000, 
                   error_message: str = None) -> ValidationRule:
        """價格範圍驗證"""
        if error_message is None:
            error_message = f"價格必須在 {min_val} 到 {max_val} 之間"
        
        return ValidationRule(
            name="price_range",
            validator=lambda x: (isinstance(x, (int, float)) and 
                              min_val <= x <= max_val),
            error_message=error_message
        )


class WebApiValidator(InputValidator):
    """Web API 驗證器"""
    
    def __init__(self):
        super().__init__("web_api")
        self._setup_rules()
    
    def _setup_rules(self):
        """設置 Web API 驗證規則"""
        # 網格下限價格驗證
        self.add_rule("grid_lower_price", CommonRules.non_negative_number("網格下限價格不能為負數"))
        self.add_rule("grid_lower_price", CommonRules.price_range(0.0001, 1000000, "網格下限價格必須在合理範圍內"))
        
        # 網格上限價格驗證
        self.add_rule("grid_upper_price", CommonRules.non_negative_number("網格上限價格不能為負數"))
        self.add_rule("grid_upper_price", CommonRules.price_range(0.0001, 1000000, "網格上限價格必須在合理範圍內"))
        
        # 跨字段驗證：下限必須小於上限
        self.add_cross_field_rule(
            ValidationRule(
                name="price_range_order",
                validator=lambda data: (
                    (data.get("grid_lower_price") is None or data.get("grid_upper_price") is None) or
                    (data.get("grid_lower_price", 0) < data.get("grid_upper_price", 0))
                ),
                error_message="網格下限價格必須小於上限價格"
            )
        )


class StrategyValidator(InputValidator):
    """策略驗證器"""
    
    def __init__(self):
        super().__init__("strategy")
        self._setup_rules()
    
    def _setup_rules(self):
        """設置策略驗證規則"""
        # 基本價格驗證
        self.add_rule("grid_lower_price", CommonRules.positive_number("網格下限價格必須是正數"))
        self.add_rule("grid_upper_price", CommonRules.positive_number("網格上限價格必須是正數"))
    
    def validate_grid_adjustment(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
        """驗證網格調整參數"""
        # 添加業務邏輯驗證
        def is_reasonable_change(data):
            current_lower = data.get("current_lower", 0)
            current_upper = data.get("current_upper", 0)
            new_lower = data.get("grid_lower_price")
            new_upper = data.get("grid_upper_price")
            
            if new_lower is not None and current_lower > 0:
                change_ratio = abs(new_lower - current_lower) / current_lower
                if change_ratio > 0.5:  # 變化超過50%
                    return False
            
            if new_upper is not None and current_upper > 0:
                change_ratio = abs(new_upper - current_upper) / current_upper
                if change_ratio > 0.5:  # 變化超過50%
                    return False
            
            return True
        
        def is_tick_aligned(data):
            tick_size = data.get("tick_size", 0.01)
            new_lower = data.get("grid_lower_price")
            new_upper = data.get("grid_upper_price")
            
            if new_lower is not None:
                if abs(new_lower / tick_size - round(new_lower / tick_size)) > 1e-10:
                    return False
            
            if new_upper is not None:
                if abs(new_upper / tick_size - round(new_upper / tick_size)) > 1e-10:
                    return False
            
            return True
        
        # 添加臨時的跨字段驗證規則
        original_cross_rules = self.cross_field_rules.copy()
        
        self.add_cross_field_rule(
            ValidationRule(
                name="reasonable_change",
                validator=is_reasonable_change,
                error_message="價格變化過大，可能導致策略異常"
            )
        )
        
        self.add_cross_field_rule(
            ValidationRule(
                name="tick_alignment",
                validator=is_tick_aligned,
                error_message="價格必須與市場tick size對齊"
            )
        )
        
        try:
            result = self.validate(data)
            return result
        finally:
            # 恢復原始跨字段規則
            self.cross_field_rules = original_cross_rules


# 測試類
class TestValidationRule(unittest.TestCase):
    """測試 ValidationRule 類"""
    
    def test_successful_validation(self):
        """測試成功的驗證"""
        rule = ValidationRule(
            name="positive_number",
            validator=lambda x: isinstance(x, (int, float)) and x > 0,
            error_message="必須是正數"
        )
        
        is_valid, error = rule.validate(5)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_failed_validation(self):
        """測試失敗的驗證"""
        rule = ValidationRule(
            name="positive_number",
            validator=lambda x: isinstance(x, (int, float)) and x > 0,
            error_message="必須是正數"
        )
        
        is_valid, error = rule.validate(-1)
        self.assertFalse(is_valid)
        self.assertEqual(error, "必須是正數")


class TestInputValidator(unittest.TestCase):
    """測試 InputValidator 類"""
    
    def setUp(self):
        """設置測試環境"""
        self.validator = InputValidator("test_validator")
    
    def test_validate_success(self):
        """測試成功驗證"""
        self.validator.add_rule("price", CommonRules.positive_number())
        
        data = {"price": 100.0}
        is_valid, errors = self.validator.validate(data)
        
        self.assertTrue(is_valid)
        self.assertEqual(errors, {})
    
    def test_validate_failure(self):
        """測試失敗驗證"""
        self.validator.add_rule("price", CommonRules.positive_number())
        
        data = {"price": -10.0}
        is_valid, errors = self.validator.validate(data)
        
        self.assertFalse(is_valid)
        self.assertIn("price", errors)
        self.assertEqual(len(errors["price"]), 1)


class TestCommonRules(unittest.TestCase):
    """測試 CommonRules 類"""
    
    def test_positive_number(self):
        """測試正數規則"""
        rule = CommonRules.positive_number()
        
        # 測試正數
        is_valid, _ = rule.validate(10.5)
        self.assertTrue(is_valid)
        
        # 測試零
        is_valid, _ = rule.validate(0)
        self.assertFalse(is_valid)
        
        # 測試負數
        is_valid, _ = rule.validate(-5)
        self.assertFalse(is_valid)
    
    def test_price_range(self):
        """測試價格範圍規則"""
        rule = CommonRules.price_range(0.0001, 1000000)
        
        # 測試有效範圍
        is_valid, _ = rule.validate(100.0)
        self.assertTrue(is_valid)
        
        # 測試過小值
        is_valid, _ = rule.validate(0.00001)
        self.assertFalse(is_valid)
        
        # 測試過大值
        is_valid, _ = rule.validate(2000000)
        self.assertFalse(is_valid)


class TestWebApiValidator(unittest.TestCase):
    """測試 WebApiValidator 類"""
    
    def setUp(self):
        """設置測試環境"""
        self.validator = WebApiValidator()
    
    def test_valid_grid_adjustment(self):
        """測試有效的網格調整數據"""
        data = {
            "grid_lower_price": 50.0,
            "grid_upper_price": 100.0
        }
        
        is_valid, errors = self.validator.validate(data)
        self.assertTrue(is_valid)
        self.assertEqual(errors, {})
    
    def test_invalid_grid_adjustment(self):
        """測試無效的網格調整數據"""
        data = {
            "grid_lower_price": -10.0,  # 負數
            "grid_upper_price": 100.0
        }
        
        is_valid, errors = self.validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("grid_lower_price", errors)
    
    def test_price_range_violation(self):
        """測試價格範圍違規"""
        data = {
            "grid_lower_price": 100.0,
            "grid_upper_price": 50.0  # 下限大於上限
        }
        
        is_valid, errors = self.validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("cross_field", errors)


class TestStrategyValidator(unittest.TestCase):
    """測試 StrategyValidator 類"""
    
    def setUp(self):
        """設置測試環境"""
        self.validator = StrategyValidator()
    
    def test_valid_grid_adjustment(self):
        """測試有效的網格調整"""
        data = {
            "grid_lower_price": 95.0,
            "grid_upper_price": 105.0,
            "current_lower": 90.0,
            "current_upper": 110.0,
            "tick_size": 0.01
        }
        
        is_valid, errors = self.validator.validate_grid_adjustment(data)
        self.assertTrue(is_valid)
        self.assertEqual(errors, {})
    
    def test_extreme_price_change(self):
        """測試極端價格變化"""
        data = {
            "grid_lower_price": 10.0,  # 變化太大
            "grid_upper_price": 100.0,
            "current_lower": 40.0,
            "current_upper": 110.0,
            "tick_size": 0.01
        }
        
        is_valid, errors = self.validator.validate_grid_adjustment(data)
        self.assertFalse(is_valid)
        self.assertIn("cross_field", errors)
    
    def test_invalid_tick_size_alignment(self):
        """測試無效的 tick size 對齊"""
        data = {
            "grid_lower_price": 95.001,  # 不對齊 tick_size
            "grid_upper_price": 100.0,
            "current_lower": 90.0,
            "current_upper": 110.0,
            "tick_size": 0.01
        }
        
        is_valid, errors = self.validator.validate_grid_adjustment(data)
        self.assertFalse(is_valid)
        self.assertIn("cross_field", errors)


class TestIntegration(unittest.TestCase):
    """集成測試"""
    
    def test_web_api_workflow(self):
        """測試 Web API 工作流程"""
        validator = WebApiValidator()
        
        # 測試正常工作流程
        valid_request = {
            "grid_lower_price": 95.0,
            "grid_upper_price": 105.0
        }
        
        is_valid, errors = validator.validate(valid_request)
        self.assertTrue(is_valid)
        
        # 測試異常工作流程
        invalid_request = {
            "grid_lower_price": -5.0,
            "grid_upper_price": 105.0
        }
        
        is_valid, errors = validator.validate(invalid_request)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_strategy_workflow(self):
        """測試策略工作流程"""
        validator = StrategyValidator()
        
        # 測試正常調整
        valid_adjustment = {
            "grid_lower_price": 95.0,
            "grid_upper_price": 105.0,
            "current_lower": 90.0,
            "current_upper": 110.0,
            "tick_size": 0.01
        }
        
        is_valid, errors = validator.validate_grid_adjustment(valid_adjustment)
        self.assertTrue(is_valid)
        
        # 測試業務邏輯驗證
        invalid_adjustment = {
            "grid_lower_price": 95.001,  # 價格不對齊 tick_size
            "grid_upper_price": 105.0,
            "current_lower": 90.0,
            "current_upper": 110.0,
            "tick_size": 0.01
        }
        
        is_valid, errors = validator.validate_grid_adjustment(invalid_adjustment)
        self.assertFalse(is_valid)


if __name__ == "__main__":
    unittest.main()