"""
Comprehensive unit tests for core/exceptions.py
Tests custom exception classes
"""
import unittest

from core.exceptions import (
    ConfigError, ConfigValidationError, ConfigLoadError,
    ConfigSaveError, ConfigBackupError, ConfigRestoreError,
    EnvironmentVariableError
)


class TestConfigExceptions(unittest.TestCase):
    """Test configuration-related exceptions"""
    
    def test_config_error_basic(self):
        """Test basic ConfigError"""
        error = ConfigError("Test error message")
        
        self.assertEqual(str(error), "Test error message")
        self.assertIsInstance(error, Exception)
    
    def test_config_error_with_config_path(self):
        """Test ConfigError with config_path parameter"""
        error = ConfigError("Test error", config_path="/path/to/config.json")
        
        self.assertIn("Test error", str(error))
        self.assertTrue(hasattr(error, 'config_path'))
    
    def test_config_validation_error(self):
        """Test ConfigValidationError"""
        error = ConfigValidationError(
            "Validation failed",
            config_path="/path/to/config.json",
            errors=["Missing required field", "Invalid value"]
        )
        
        self.assertIsInstance(error, ConfigError)
        self.assertTrue(hasattr(error, 'errors'))
    
    def test_config_load_error(self):
        """Test ConfigLoadError"""
        error = ConfigLoadError(
            "Failed to load config",
            config_path="/path/to/config.json"
        )
        
        self.assertIsInstance(error, ConfigError)
        self.assertIn("Failed to load", str(error))
    
    def test_config_save_error(self):
        """Test ConfigSaveError"""
        error = ConfigSaveError(
            "Failed to save config",
            config_path="/path/to/config.json"
        )
        
        self.assertIsInstance(error, ConfigError)
        self.assertIn("Failed to save", str(error))
    
    def test_config_backup_error(self):
        """Test ConfigBackupError"""
        error = ConfigBackupError(
            "Failed to backup config",
            config_path="/path/to/config.json"
        )
        
        self.assertIsInstance(error, ConfigError)
        self.assertIn("Failed to backup", str(error))
    
    def test_config_restore_error(self):
        """Test ConfigRestoreError"""
        error = ConfigRestoreError(
            "Failed to restore config",
            config_path="/path/to/backup.json",
            expected="abc123",
            actual="def456"
        )
        
        self.assertIsInstance(error, ConfigError)
        self.assertTrue(hasattr(error, 'expected'))
        self.assertTrue(hasattr(error, 'actual'))
    
    def test_environment_variable_error(self):
        """Test EnvironmentVariableError"""
        error = EnvironmentVariableError(
            "Environment variable not set",
            var_name="API_KEY"
        )
        
        self.assertIsInstance(error, Exception)
        self.assertTrue(hasattr(error, 'var_name'))
        self.assertEqual(error.var_name, "API_KEY")
    
    def test_exception_inheritance(self):
        """Test that all config exceptions inherit from ConfigError"""
        exceptions = [
            ConfigValidationError("test"),
            ConfigLoadError("test"),
            ConfigSaveError("test"),
            ConfigBackupError("test"),
            ConfigRestoreError("test")
        ]
        
        for exc in exceptions:
            self.assertIsInstance(exc, ConfigError)
            self.assertIsInstance(exc, Exception)
    
    def test_exception_with_multiple_errors(self):
        """Test ConfigValidationError with multiple error messages"""
        errors = [
            "Missing required field: name",
            "Invalid value for: exchange",
            "Value out of range: grid_num"
        ]
        
        error = ConfigValidationError(
            "Config validation failed",
            errors=errors
        )
        
        self.assertEqual(len(error.errors), 3)
        self.assertIn("Missing required field", error.errors[0])
    
    def test_exception_repr(self):
        """Test exception string representation"""
        error = ConfigLoadError(
            "Cannot load file",
            config_path="/test/path.json"
        )
        
        error_str = str(error)
        self.assertIsInstance(error_str, str)
        self.assertTrue(len(error_str) > 0)
    
    def test_exception_with_none_values(self):
        """Test exceptions with None values for optional parameters"""
        error1 = ConfigError("Test", config_path=None)
        error2 = ConfigValidationError("Test", errors=None)
        error3 = EnvironmentVariableError("Test", var_name=None)
        
        # Should not raise errors
        self.assertIsInstance(error1, ConfigError)
        self.assertIsInstance(error2, ConfigValidationError)
        self.assertIsInstance(error3, EnvironmentVariableError)
    
    def test_exception_raise_and_catch(self):
        """Test raising and catching exceptions"""
        with self.assertRaises(ConfigLoadError) as context:
            raise ConfigLoadError("Test error", config_path="/test.json")
        
        self.assertIn("Test error", str(context.exception))
    
    def test_exception_attributes_accessible(self):
        """Test that exception attributes are accessible"""
        error = ConfigRestoreError(
            "Checksum mismatch",
            config_path="/backup.json",
            expected="abc123",
            actual="def456"
        )
        
        self.assertEqual(error.config_path, "/backup.json")
        self.assertEqual(error.expected, "abc123")
        self.assertEqual(error.actual, "def456")


class TestEnvironmentVariableError(unittest.TestCase):
    """Focused tests for EnvironmentVariableError"""
    
    def test_basic_creation(self):
        """Test basic creation of EnvironmentVariableError"""
        error = EnvironmentVariableError("Variable not set")
        
        self.assertEqual(str(error), "Variable not set")
    
    def test_with_var_name(self):
        """Test EnvironmentVariableError with var_name"""
        error = EnvironmentVariableError(
            "Required variable not set",
            var_name="SECRET_KEY"
        )
        
        self.assertEqual(error.var_name, "SECRET_KEY")
        self.assertIn("Required variable", str(error))
    
    def test_multiple_variable_names(self):
        """Test EnvironmentVariableError for multiple variables"""
        var_names = ["API_KEY", "SECRET_KEY", "PRIVATE_KEY"]
        
        for var_name in var_names:
            error = EnvironmentVariableError(
                f"{var_name} not found",
                var_name=var_name
            )
            
            self.assertEqual(error.var_name, var_name)
    
    def test_sensitive_variable_handling(self):
        """Test error for sensitive variables"""
        sensitive_vars = ["API_KEY", "SECRET_KEY", "PASSWORD", "TOKEN"]
        
        for var in sensitive_vars:
            error = EnvironmentVariableError(
                f"Sensitive variable {var} not set",
                var_name=var
            )
            
            # Should store the variable name
            self.assertEqual(error.var_name, var)
            # But message should not leak sensitive info
            self.assertIn(var, str(error))


class TestExceptionChaining(unittest.TestCase):
    """Test exception chaining and context"""
    
    def test_exception_chain(self):
        """Test chaining exceptions with 'from' clause"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise ConfigLoadError(
                    "Failed to load config",
                    config_path="/test.json"
                ) from e
        except ConfigLoadError as config_error:
            # Should maintain the chain
            self.assertIsNotNone(config_error.__cause__)
            self.assertIsInstance(config_error.__cause__, ValueError)
    
    def test_exception_context_preservation(self):
        """Test that exception context is preserved"""
        try:
            try:
                1 / 0  # ZeroDivisionError
            except ZeroDivisionError:
                raise ConfigSaveError(
                    "Cannot save config",
                    config_path="/test.json"
                )
        except ConfigSaveError as error:
            # Context should be preserved
            self.assertIsNotNone(error.__context__)


class TestExceptionEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""
    
    def test_empty_error_message(self):
        """Test exceptions with empty message"""
        error = ConfigError("")
        
        self.assertEqual(str(error), "")
    
    def test_very_long_error_message(self):
        """Test exceptions with very long message"""
        long_message = "Error: " + "x" * 10000
        error = ConfigError(long_message)
        
        self.assertEqual(len(str(error)), len(long_message))
    
    def test_unicode_in_error_message(self):
        """Test exceptions with Unicode characters"""
        error = ConfigError("配置錯誤：無法載入檔案 🚫")
        
        error_str = str(error)
        self.assertIn("配置錯誤", error_str)
        self.assertIn("🚫", error_str)
    
    def test_special_characters_in_path(self):
        """Test exceptions with special characters in paths"""
        special_paths = [
            "/path/with spaces/config.json",
            "/path/with-dashes/config.json",
            "/path/with_underscores/config.json",
            "/path/with.dots/config.json"
        ]
        
        for path in special_paths:
            error = ConfigLoadError("Test", config_path=path)
            self.assertTrue(hasattr(error, 'config_path'))
            self.assertEqual(error.config_path, path)


if __name__ == '__main__':
    unittest.main()