"""
配置管理器測試
測試配置管理器的各項功能
"""
import unittest
import tempfile
import shutil
import json
import os
from pathlib import Path
from datetime import datetime

from core.config_manager import ConfigManager, ConfigInfo, ValidationResult
from core.exceptions import (
    ConfigError, ConfigValidationError, ConfigLoadError, 
    ConfigSaveError, ConfigBackupError, ConfigRestoreError,
    EnvironmentVariableError
)


class TestConfigManager(unittest.TestCase):
    """配置管理器測試類"""
    
    def setUp(self):
        """測試前準備"""
        self.test_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager(self.test_dir)
        
        # 創建測試配置數據
        self.test_config = {
            "metadata": {
                "name": "測試配置",
                "description": "用於測試的配置",
                "exchange": "backpack",
                "symbol": "SOL_USDC",
                "market_type": "spot",
                "strategy": "grid",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "version": "1.0.0",
                "author": "test",
                "tags": ["test"]
            },
            "daemon_config": {
                "python_path": ".venv/bin/python3",
                "script_path": "run.py",
                "working_dir": ".",
                "log_dir": "logs",
                "max_restart_attempts": 3,
                "restart_delay": 60,
                "health_check_interval": 30,
                "memory_limit_mb": 2048,
                "cpu_limit_percent": 80,
                "auto_restart": True,
                "log_cleanup_interval": 86400,
                "log_retention_days": 2
            },
            "exchange_config": {
                "api_key": "${TEST_API_KEY}",
                "secret_key": "${TEST_SECRET_KEY}",
                "base_url": "${TEST_URL:-https://api.test.com}",
                "api_version": "v1",
                "default_window": "5000"
            },
            "strategy_config": {
                "grid_upper_price": 160,
                "grid_lower_price": 140,
                "grid_num": 20,
                "grid_mode": "arithmetic",
                "auto_borrow": True,
                "auto_borrow_repay": True,
                "duration": 86400,
                "interval": 60
            }
        }
    
    def tearDown(self):
        """測試後清理"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_directory_creation(self):
        """測試目錄創建"""
        # 檢查目錄是否被創建
        self.assertTrue(Path(self.test_dir).exists())
        self.assertTrue(Path(self.test_dir, "templates").exists())
        self.assertTrue(Path(self.test_dir, "active").exists())
        self.assertTrue(Path(self.test_dir, "archived").exists())
    
    def test_save_and_load_config(self):
        """測試配置保存和加載"""
        config_path = Path(self.test_dir, "active", "test_config.json")
        
        # 保存配置
        result = self.config_manager.save_config(config_path, self.test_config)
        self.assertTrue(result)
        self.assertTrue(config_path.exists())
        
        # 加載配置
        loaded_config = self.config_manager.load_config(config_path, expand_vars=False)
        self.assertEqual(loaded_config["metadata"]["name"], "測試配置")
        self.assertEqual(loaded_config["exchange_config"]["api_key"], "${TEST_API_KEY}")
    
    def test_config_validation(self):
        """測試配置驗證"""
        # 有效配置
        result = self.config_manager.validate_config(self.test_config)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        
        # 無效配置 - 缺少必需字段
        invalid_config = self.test_config.copy()
        del invalid_config["metadata"]["exchange"]
        result = self.config_manager.validate_config(invalid_config)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        
        # 網格策略驗證 - 上限價格低於下限價格
        invalid_grid_config = self.test_config.copy()
        invalid_grid_config["strategy_config"]["grid_upper_price"] = 140
        invalid_grid_config["strategy_config"]["grid_lower_price"] = 160
        result = self.config_manager.validate_config(invalid_grid_config)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("grid_upper_price 必須大於 grid_lower_price" in error 
                          for error in result.errors))
    
    def test_environment_variable_expansion(self):
        """測試環境變量展開"""
        # 設置測試環境變量
        os.environ["TEST_API_KEY"] = "test_api_key_value"
        os.environ["TEST_SECRET_KEY"] = "test_secret_key_value"
        
        try:
            # 測試環境變量展開
            expanded = self.config_manager.expand_env_vars("${TEST_API_KEY}")
            self.assertEqual(expanded, "test_api_key_value")
            
            # 測試帶默認值的環境變量
            expanded = self.config_manager.expand_env_vars("${TEST_URL:-https://default.com}")
            self.assertEqual(expanded, "https://default.com")
            
            # 測試字典展開
            test_dict = {
                "api_key": "${TEST_API_KEY}",
                "nested": {
                    "secret_key": "${TEST_SECRET_KEY}"
                }
            }
            expanded_dict = self.config_manager.expand_env_vars(test_dict)
            self.assertEqual(expanded_dict["api_key"], "test_api_key_value")
            self.assertEqual(expanded_dict["nested"]["secret_key"], "test_secret_key_value")
            
        finally:
            # 清理環境變量
            os.environ.pop("TEST_API_KEY", None)
            os.environ.pop("TEST_SECRET_KEY", None)
    
    def test_environment_variable_security(self):
        """測試環境變量安全性"""
        # 測試敏感環境變量未設置時拋出異常
        with self.assertRaises(EnvironmentVariableError):
            self.config_manager.expand_env_vars("${API_KEY}")
        
        with self.assertRaises(EnvironmentVariableError):
            self.config_manager.expand_env_vars("${SECRET_KEY}")
        
        # 測試非敏感環境變量不拋出異常
        result = self.config_manager.expand_env_vars("${NON_SENSITIVE_VAR}")
        self.assertEqual(result, "${NON_SENSITIVE_VAR}")
    
    def test_backup_and_restore(self):
        """測試配置備份和恢復"""
        config_path = Path(self.test_dir, "active", "test_config.json")
        
        # 保存配置
        self.config_manager.save_config(config_path, self.test_config)
        
        # 備份配置
        backup_path = self.config_manager.backup_config(config_path)
        self.assertIsNotNone(backup_path)
        self.assertTrue(Path(backup_path).exists())
        
        # 檢查校驗和文件是否存在
        checksum_path = Path(backup_path).with_suffix('.json.checksum')
        self.assertTrue(checksum_path.exists())
        
        # 修改原配置
        modified_config = self.test_config.copy()
        modified_config["metadata"]["name"] = "修改後的配置"
        self.config_manager.save_config(config_path, modified_config)
        
        # 恢復配置
        success = self.config_manager.restore_config(backup_path, config_path)
        self.assertTrue(success)
        
        # 驗證恢復的配置
        restored_config = self.config_manager.load_config(config_path, expand_vars=False)
        self.assertEqual(restored_config["metadata"]["name"], "測試配置")
    
    def test_backup_integrity_check(self):
        """測試備份完整性檢查"""
        config_path = Path(self.test_dir, "active", "test_config.json")
        backup_path = Path(self.test_dir, "archived", "test_backup.json")
        
        # 保存配置
        self.config_manager.save_config(config_path, self.test_config)
        
        # 創建備份
        shutil.copy2(config_path, backup_path)
        
        # 創建校驗和文件
        checksum = self.config_manager._calculate_checksum(config_path)
        checksum_path = backup_path.with_suffix('.json.checksum')
        with open(checksum_path, 'w') as f:
            f.write(checksum)
        
        # 修改備份文件（模擬損壞）
        with open(backup_path, 'w') as f:
            f.write('{"corrupted": "data"}')
        
        # 嘗試恢復，應該失敗
        with self.assertRaises(ConfigRestoreError):
            self.config_manager.restore_config(backup_path, config_path)
    
    def test_create_from_template(self):
        """測試從模板創建配置"""
        # 創建模板
        template_path = Path(self.test_dir, "templates", "test_template.json")
        self.config_manager.save_config(template_path, self.test_config)
        
        # 從模板創建配置
        params = {
            "symbol": "ETH_USDC",
            "grid_num": 30
        }
        
        new_config = self.config_manager.create_from_template(
            "test_template", "new_config", params
        )
        
        # 驗證參數應用
        self.assertEqual(new_config["metadata"]["name"], "new_config")
        self.assertEqual(new_config["metadata"]["symbol"], "ETH_USDC")
        self.assertEqual(new_config["strategy_config"]["grid_num"], 30)
    
    def test_list_configs(self):
        """測試列出配置"""
        # 創建測試配置
        active_path = Path(self.test_dir, "active", "active_config.json")
        template_path = Path(self.test_dir, "templates", "template_config.json")
        archived_path = Path(self.test_dir, "archived", "archived_config.json")
        
        self.config_manager.save_config(active_path, self.test_config)
        self.config_manager.save_config(template_path, self.test_config)
        self.config_manager.save_config(archived_path, self.test_config)
        
        # 列出所有配置
        configs = self.config_manager.list_configs()
        self.assertEqual(len(configs), 3)
        
        # 按類型篩選
        active_configs = self.config_manager.list_configs(include_templates=False, include_archived=False)
        self.assertEqual(len(active_configs), 1)
        self.assertTrue(active_configs[0].is_active)
        
        template_configs = self.config_manager.list_configs(include_active=False, include_archived=False)
        self.assertEqual(len(template_configs), 1)
        self.assertTrue(template_configs[0].is_template)
        
        archived_configs = self.config_manager.list_configs(include_active=False, include_templates=False)
        self.assertEqual(len(archived_configs), 1)
        self.assertTrue(archived_configs[0].is_archived)
    
    def test_delete_config(self):
        """測試刪除配置"""
        config_path = Path(self.test_dir, "active", "test_config.json")
        
        # 保存配置
        self.config_manager.save_config(config_path, self.test_config)
        self.assertTrue(config_path.exists())
        
        # 刪除配置
        success = self.config_manager.delete_config(config_path)
        self.assertTrue(success)
        self.assertFalse(config_path.exists())
    
    def test_error_handling(self):
        """測試錯誤處理"""
        # 測試加載不存在的文件
        with self.assertRaises(ConfigLoadError):
            self.config_manager.load_config("nonexistent.json")
        
        # 測試保存到無效路徑（只讀目錄）
        readonly_dir = Path(self.test_dir, "readonly")
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # 只讀權限
        
        try:
            invalid_path = readonly_dir / "test.json"
            with self.assertRaises(ConfigSaveError):
                self.config_manager.save_config(invalid_path, self.test_config)
        finally:
            # 恢復權限以便清理
            readonly_dir.chmod(0o755)


if __name__ == '__main__':
    unittest.main()