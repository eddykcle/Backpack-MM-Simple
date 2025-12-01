"""
Comprehensive unit tests for core/daemon_manager.py
Tests the TradingBotDaemon class and related functionality
"""
import unittest
import tempfile
import json
import os
import time
import signal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess

# Import the module under test
from core.daemon_manager import TradingBotDaemon


class TestTradingBotDaemon(unittest.TestCase):
    """Test TradingBotDaemon class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        
        # Create a test config file with multi-config format
        self.config_data = {
            "metadata": {
                "name": "test_bot",
                "instance_id": "test_instance",
                "exchange": "backpack",
                "symbol": "SOL_USDC",
                "market_type": "spot",
                "strategy": "grid"
            },
            "daemon_config": {
                "python_path": "/usr/bin/python3",
                "script_path": "run.py",
                "working_dir": ".",
                "log_dir": "logs",
                "max_restart_attempts": 3,
                "restart_delay": 60,
                "health_check_interval": 30,
                "memory_limit_mb": 2048,
                "cpu_limit_percent": 80,
                "auto_restart": True
            },
            "exchange_config": {
                "api_key": "${TEST_API_KEY}",
                "secret_key": "${TEST_SECRET_KEY}"
            },
            "strategy_config": {
                "grid_upper_price": 160,
                "grid_lower_price": 140,
                "grid_num": 20
            }
        }
        
        self.config_file = Path(self.test_dir) / "test_config.json"
        with open(self.config_file, 'w') as f:
            json.dump(self.config_data, f)
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_init_multi_config_format(self):
        """Test initialization with multi-config format"""
        daemon = TradingBotDaemon(str(self.config_file))
        
        self.assertEqual(daemon.instance_id, "test_instance")
        self.assertTrue(daemon.is_multi_config)
        self.assertTrue(daemon.log_dir.exists())
    
    def test_init_instance_id_override(self):
        """Test instance_id parameter override"""
        daemon = TradingBotDaemon(str(self.config_file), instance_id="custom_id")
        
        self.assertEqual(daemon.instance_id, "custom_id")
    
    def test_load_config_multi_format(self):
        """Test loading multi-config format"""
        daemon = TradingBotDaemon(str(self.config_file))
        config = daemon.load_config()
        
        self.assertIn("metadata", config)
        self.assertIn("daemon_config", config)
        self.assertEqual(config["metadata"]["name"], "test_bot")
    
    def test_load_config_legacy_format(self):
        """Test loading legacy config format"""
        # Create legacy format config
        legacy_config = {
            "python_path": "/usr/bin/python3",
            "script_path": "run.py",
            "max_restart_attempts": 3
        }
        
        legacy_file = Path(self.test_dir) / "legacy_config.json"
        with open(legacy_file, 'w') as f:
            json.dump(legacy_config, f)
        
        daemon = TradingBotDaemon(str(legacy_file))
        config = daemon.load_config()
        
        self.assertFalse(daemon.is_multi_config)
        self.assertEqual(config["python_path"], "/usr/bin/python3")
    
    @patch('core.daemon_manager.subprocess.Popen')
    @patch('core.daemon_manager.psutil.Process')
    def test_start_bot_success(self, mock_process, mock_popen):
        """Test successful bot start"""
        # Mock subprocess
        mock_proc = Mock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        
        # Mock psutil.Process
        mock_ps_proc = Mock()
        mock_ps_proc.is_running.return_value = True
        mock_ps_proc.status.return_value = 'running'
        mock_process.return_value = mock_ps_proc
        
        daemon = TradingBotDaemon(str(self.config_file))
        
        with patch.object(daemon.registry, 'register') as mock_register:
            result = daemon.start()
            
            self.assertTrue(result)
            mock_popen.assert_called_once()
            mock_register.assert_called_once()
    
    @patch('core.daemon_manager.psutil.pid_exists')
    def test_status_running(self, mock_pid_exists):
        """Test status check when bot is running"""
        mock_pid_exists.return_value = True
        
        daemon = TradingBotDaemon(str(self.config_file))
        
        # Create fake PID file
        daemon._bot_pid_file.write_text("12345")
        
        with patch.object(daemon.registry, 'get') as mock_get:
            mock_get.return_value = {
                "pid": 12345,
                "status": "running",
                "start_time": "2024-01-01T00:00:00"
            }
            
            status = daemon.status()
            
            self.assertEqual(status["status"], "running")
            self.assertEqual(status["pid"], 12345)
    
    @patch('core.daemon_manager.psutil.pid_exists')
    def test_status_stopped(self, mock_pid_exists):
        """Test status check when bot is stopped"""
        mock_pid_exists.return_value = False
        
        daemon = TradingBotDaemon(str(self.config_file))
        status = daemon.status()
        
        self.assertEqual(status["status"], "stopped")
        self.assertIsNone(status.get("pid"))
    
    @patch('core.daemon_manager.psutil.Process')
    @patch('core.daemon_manager.os.kill')
    def test_stop_graceful(self, mock_kill, mock_process):
        """Test graceful bot stop"""
        # Mock process
        mock_proc = Mock()
        mock_proc.is_running.side_effect = [True, False]  # Running then stopped
        mock_process.return_value = mock_proc
        
        daemon = TradingBotDaemon(str(self.config_file))
        daemon._bot_pid_file.write_text("12345")
        
        with patch.object(daemon.registry, 'unregister') as mock_unregister:
            result = daemon.stop()
            
            self.assertTrue(result)
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)
            mock_unregister.assert_called_once()
    
    @patch('core.daemon_manager.psutil.Process')
    @patch('core.daemon_manager.os.kill')
    def test_stop_force(self, mock_kill, mock_process):
        """Test forced bot stop"""
        # Mock process that doesn't respond to SIGTERM
        mock_proc = Mock()
        mock_proc.is_running.return_value = True
        mock_process.return_value = mock_proc
        
        daemon = TradingBotDaemon(str(self.config_file))
        daemon._bot_pid_file.write_text("12345")
        
        with patch('time.sleep'):  # Skip sleep delays
            result = daemon.stop()
            
            # Should call SIGTERM then SIGKILL
            self.assertEqual(mock_kill.call_count, 2)
            calls = mock_kill.call_args_list
            self.assertEqual(calls[0][0][1], signal.SIGTERM)
            self.assertEqual(calls[1][0][1], signal.SIGKILL)
    
    @patch('core.daemon_manager.subprocess.Popen')
    def test_restart(self, mock_popen):
        """Test bot restart"""
        mock_proc = Mock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        
        daemon = TradingBotDaemon(str(self.config_file))
        
        with patch.object(daemon, 'stop') as mock_stop, \
             patch.object(daemon, 'start') as mock_start:
            mock_stop.return_value = True
            mock_start.return_value = True
            
            result = daemon.restart()
            
            self.assertTrue(result)
            mock_stop.assert_called_once()
            mock_start.assert_called_once()
    
    def test_signal_handler(self):
        """Test signal handler"""
        daemon = TradingBotDaemon(str(self.config_file))
        
        self.assertTrue(daemon.running)
        daemon._signal_handler(signal.SIGTERM, None)
        self.assertFalse(daemon.running)
    
    def test_cleanup_bot_process(self):
        """Test cleanup of bot process"""
        daemon = TradingBotDaemon(str(self.config_file))
        
        # Create fake process
        mock_proc = Mock()
        daemon._bot_process = mock_proc
        
        with patch.object(daemon, 'stop') as mock_stop:
            daemon._cleanup_bot_process()
            mock_stop.assert_called_once()
    
    def test_config_validation_errors(self):
        """Test handling of invalid config"""
        invalid_config = {
            "metadata": {
                "name": "test"
                # Missing required fields
            }
        }
        
        invalid_file = Path(self.test_dir) / "invalid_config.json"
        with open(invalid_file, 'w') as f:
            json.dump(invalid_config, f)
        
        daemon = TradingBotDaemon(str(invalid_file))
        config = daemon.load_config()
        
        # Should load but with defaults
        self.assertIsNotNone(config)
    
    @patch('core.daemon_manager.psutil.Process')
    def test_health_check_healthy(self, mock_process):
        """Test health check for healthy process"""
        mock_proc = Mock()
        mock_proc.is_running.return_value = True
        mock_proc.cpu_percent.return_value = 50.0
        mock_proc.memory_info.return_value = Mock(rss=1024*1024*512)  # 512 MB
        mock_process.return_value = mock_proc
        
        daemon = TradingBotDaemon(str(self.config_file))
        daemon._bot_pid_file.write_text("12345")
        
        result = daemon._check_health()
        
        self.assertTrue(result)
    
    @patch('core.daemon_manager.psutil.Process')
    def test_health_check_high_memory(self, mock_process):
        """Test health check with high memory usage"""
        mock_proc = Mock()
        mock_proc.is_running.return_value = True
        mock_proc.cpu_percent.return_value = 50.0
        mock_proc.memory_info.return_value = Mock(rss=1024*1024*3000)  # 3 GB
        mock_process.return_value = mock_proc
        
        daemon = TradingBotDaemon(str(self.config_file))
        daemon._bot_pid_file.write_text("12345")
        
        result = daemon._check_health()
        
        # Should fail due to high memory
        self.assertFalse(result)
    
    def test_instance_id_from_filename(self):
        """Test instance_id derived from filename"""
        config_file = Path(self.test_dir) / "my_instance.json"
        
        # Create config without instance_id in metadata
        config_without_id = self.config_data.copy()
        config_without_id["metadata"] = config_without_id["metadata"].copy()
        del config_without_id["metadata"]["instance_id"]
        
        with open(config_file, 'w') as f:
            json.dump(config_without_id, f)
        
        daemon = TradingBotDaemon(str(config_file))
        
        # Should use filename as instance_id
        self.assertEqual(daemon.instance_id, "my_instance")
    
    def test_log_directory_creation(self):
        """Test that instance-specific log directory is created"""
        daemon = TradingBotDaemon(str(self.config_file))
        
        expected_log_dir = Path(f"logs/{daemon.instance_id}")
        self.assertTrue(daemon.log_dir.exists())
        self.assertEqual(daemon.log_dir, expected_log_dir)


class TestDaemonManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_nonexistent_config_file(self):
        """Test handling of non-existent config file"""
        fake_path = Path(self.test_dir) / "nonexistent.json"
        
        with self.assertRaises(FileNotFoundError):
            daemon = TradingBotDaemon(str(fake_path))
            daemon.load_config()
    
    def test_malformed_json_config(self):
        """Test handling of malformed JSON"""
        bad_file = Path(self.test_dir) / "bad.json"
        bad_file.write_text("{ invalid json }")
        
        with self.assertRaises(json.JSONDecodeError):
            daemon = TradingBotDaemon(str(bad_file))
            daemon.load_config()
    
    def test_stop_when_not_running(self):
        """Test stop when process is not running"""
        config_file = Path(self.test_dir) / "config.json"
        config_file.write_text(json.dumps({"python_path": "/usr/bin/python3"}))
        
        daemon = TradingBotDaemon(str(config_file))
        
        result = daemon.stop()
        
        # Should return False or handle gracefully
        self.assertIsInstance(result, bool)
    
    @patch('core.daemon_manager.subprocess.Popen')
    def test_start_when_already_running(self, mock_popen):
        """Test start when process is already running"""
        config_file = Path(self.test_dir) / "config.json"
        config_data = {
            "metadata": {"name": "test", "instance_id": "test"},
            "daemon_config": {
                "python_path": "/usr/bin/python3",
                "script_path": "run.py"
            }
        }
        config_file.write_text(json.dumps(config_data))
        
        daemon = TradingBotDaemon(str(config_file))
        daemon._bot_pid_file.write_text("12345")
        
        with patch('core.daemon_manager.psutil.pid_exists', return_value=True):
            result = daemon.start()
            
            # Should not start again
            mock_popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()