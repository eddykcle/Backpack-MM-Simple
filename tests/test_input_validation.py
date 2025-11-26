"""
輸入驗證模塊的單元測試
"""
import unittest
from utils.input_validation import (
    ValidationRule, InputValidator, CommonRules,
    WebApiValidator, CliValidator, StrategyValidator
)


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
    
    def test_add_rule(self):
        """測試添加規則"""
        rule = ValidationRule("test", lambda x: True, "測試規則")
        self.validator.add_rule("test_field", rule)
        
        self.assertIn("test_field", self.validator.rules)
        self.assertEqual(len(self.validator.rules["test_field"]), 1)
    
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
    
    def test_cross_field_validation(self):
        """測試跨字段驗證"""
        self.validator.add_rule("lower_price", CommonRules.positive_number())
        self.validator.add_rule("upper_price", CommonRules.positive_number())
        self.validator.add_cross_field_rule(
            ValidationRule(
                "price_range",
                lambda data: data.get("lower_price", 0) < data.get("upper_price", 0),
                "下限價格必須小於上限價格"
            )
        )
        
        # 測試成功情況
        valid_data = {"lower_price": 50.0, "upper_price": 100.0}
        is_valid, errors = self.validator.validate(valid_data)
        self.assertTrue(is_valid)
        
        # 測試失敗情況
        invalid_data = {"lower_price": 100.0, "upper_price": 50.0}
        is_valid, errors = self.validator.validate(invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("cross_field", errors)


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
        
        # 測試非數字
        is_valid, _ = rule.validate("abc")
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
    
    def test_url_whitelist(self):
        """測試 URL 白名單規則"""
        rule = CommonRules.url_whitelist()
        
        # 測試本地地址
        is_valid, _ = rule.validate("http://127.0.0.1:5000")
        self.assertTrue(is_valid)
        
        is_valid, _ = rule.validate("https://localhost:8080")
        self.assertTrue(is_valid)
        
        # 測試內網地址
        is_valid, _ = rule.validate("http://192.168.1.100:5000")
        self.assertTrue(is_valid)
        
        # 測試外部地址
        is_valid, _ = rule.validate("https://example.com")
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


class TestCliValidator(unittest.TestCase):
    """測試 CliValidator 類"""
    
    def setUp(self):
        """設置測試環境"""
        self.validator = CliValidator()
    
    def test_valid_url(self):
        """測試有效的 URL"""
        data = {
            "base_url": "http://127.0.0.1:5000",
            "grid_lower_price": "50.0",
            "grid_upper_price": "100.0"
        }
        
        is_valid, errors = self.validator.validate(data)
        self.assertTrue(is_valid)
        self.assertEqual(errors, {})
    
    def test_invalid_url(self):
        """測試無效的 URL"""
        data = {
            "base_url": "https://malicious-site.com",
            "grid_lower_price": "50.0",
            "grid_upper_price": "100.0"
        }
        
        is_valid, errors = self.validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("base_url", errors)
    
    def test_invalid_price_format(self):
        """測試無效的價格格式"""
        data = {
            "base_url": "http://127.0.0.1:5000",
            "grid_lower_price": "invalid_price",
            "grid_upper_price": "100.0"
        }
        
        is_valid, errors = self.validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("grid_lower_price", errors)


class TestStrategyValidator(unittest.TestCase):
    """測試 StrategyValidator 類"""
    
    def setUp(self):
        """設置測試環境"""
        self.validator = StrategyValidator()
    
    def test_valid_grid_adjustment(self):
        """測試有效的網格調整"""
        data = {
            "grid_lower_price": 50.0,
            "grid_upper_price": 100.0,
            "current_lower": 40.0,
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
        self.assertIn("grid_lower_price", errors)
    
    def test_invalid_tick_size_alignment(self):
        """測試無效的 tick_size 對齊"""
        data = {
            "grid_lower_price": 50.001,  # 不對齊 tick_size
            "grid_upper_price": 100.0,
            "current_lower": 40.0,
            "current_upper": 110.0,
            "tick_size": 0.01
        }
        
        is_valid, errors = self.validator.validate_grid_adjustment(data)
        self.assertFalse(is_valid)
        self.assertIn("grid_lower_price", errors)


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
    
    def test_cli_workflow(self):
        """測試 CLI 工作流程"""
        validator = CliValidator()
        
        # 測試正常工作流程
        valid_input = {
            "base_url": "http://127.0.0.1:5000",
            "grid_lower_price": "95.0",
            "grid_upper_price": "105.0"
        }
        
        is_valid, errors = validator.validate(valid_input)
        self.assertTrue(is_valid)
        
        # 測試 SSRF 防護
        malicious_input = {
            "base_url": "https://evil-site.com/api/grid/adjust",
            "grid_lower_price": "95.0",
            "grid_upper_price": "105.0"
        }
        
        is_valid, errors = validator.validate(malicious_input)
        self.assertFalse(is_valid)
        self.assertIn("base_url", errors)
    
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
            "grid_lower_price": 95.0,
            "grid_upper_price": 105.0,
            "current_lower": 90.0,
            "current_upper": 110.0,
            "tick_size": 0.001  # 價格不對齊
        }
        
        is_valid, errors = validator.validate_grid_adjustment(invalid_adjustment)
        self.assertFalse(is_valid)


if __name__ == "__main__":
    unittest.main()