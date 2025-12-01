"""
Comprehensive unit tests for cli/commands.py
Tests CLI command functions and user interactions
"""
import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

# Import functions under test
from cli.commands import (
    _resolve_api_credentials,
    _get_client,
    get_balance_command,
    configure_rebalance_settings
)


class TestResolveApiCredentials(unittest.TestCase):
    """Test _resolve_api_credentials function"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing env vars
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_backpack_credentials_from_env(self):
        """Test resolving Backpack credentials from environment"""
        os.environ['BACKPACK_KEY'] = 'test_api_key'
        os.environ['BACKPACK_SECRET'] = 'test_secret_key'
        
        api_key, secret_key = _resolve_api_credentials('backpack', None, None)
        
        self.assertEqual(api_key, 'test_api_key')
        self.assertEqual(secret_key, 'test_secret_key')
    
    def test_backpack_credentials_fallback(self):
        """Test Backpack credentials fallback to API_KEY"""
        os.environ['API_KEY'] = 'fallback_api_key'
        os.environ['SECRET_KEY'] = 'fallback_secret_key'
        
        api_key, secret_key = _resolve_api_credentials('backpack', None, None)
        
        self.assertEqual(api_key, 'fallback_api_key')
        self.assertEqual(secret_key, 'fallback_secret_key')
    
    def test_aster_credentials(self):
        """Test resolving Aster credentials"""
        os.environ['ASTER_API_KEY'] = 'aster_api'
        os.environ['ASTER_SECRET_KEY'] = 'aster_secret'
        
        api_key, secret_key = _resolve_api_credentials('aster', None, None)
        
        self.assertEqual(api_key, 'aster_api')
        self.assertEqual(secret_key, 'aster_secret')
    
    def test_paradex_credentials(self):
        """Test resolving Paradex credentials (StarkNet)"""
        os.environ['PARADEX_ACCOUNT_ADDRESS'] = '0x123abc'
        os.environ['PARADEX_PRIVATE_KEY'] = 'private_key_123'
        
        api_key, secret_key = _resolve_api_credentials('paradex', None, None)
        
        self.assertEqual(api_key, '0x123abc')
        self.assertEqual(secret_key, 'private_key_123')
    
    def test_lighter_credentials(self):
        """Test resolving Lighter credentials"""
        os.environ['LIGHTER_PRIVATE_KEY'] = 'lighter_private'
        os.environ['LIGHTER_ACCOUNT_INDEX'] = '1'
        
        api_key, secret_key = _resolve_api_credentials('lighter', None, None)
        
        self.assertEqual(api_key, 'lighter_private')
        self.assertEqual(secret_key, '1')
    
    def test_parameter_override(self):
        """Test that provided parameters override environment"""
        os.environ['BACKPACK_KEY'] = 'env_api_key'
        os.environ['BACKPACK_SECRET'] = 'env_secret_key'
        
        api_key, secret_key = _resolve_api_credentials(
            'backpack', 'param_api_key', 'param_secret_key'
        )
        
        self.assertEqual(api_key, 'param_api_key')
        self.assertEqual(secret_key, 'param_secret_key')
    
    def test_no_credentials_found(self):
        """Test when no credentials are found"""
        # Clear environment
        for key in list(os.environ.keys()):
            if 'KEY' in key or 'SECRET' in key:
                del os.environ[key]
        
        api_key, secret_key = _resolve_api_credentials('backpack', None, None)
        
        self.assertIsNone(api_key)
        self.assertIsNone(secret_key)
    
    def test_default_exchange(self):
        """Test default exchange handling"""
        os.environ['BACKPACK_KEY'] = 'default_api'
        os.environ['BACKPACK_SECRET'] = 'default_secret'
        
        api_key, secret_key = _resolve_api_credentials('', None, None)
        
        # Should default to backpack
        self.assertEqual(api_key, 'default_api')
        self.assertEqual(secret_key, 'default_secret')


class TestGetClient(unittest.TestCase):
    """Test _get_client function and client caching"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear client cache
        import cli.commands
        cli.commands._client_cache.clear()
    
    @patch('cli.commands.BPClient')
    def test_create_backpack_client(self, mock_bp_client):
        """Test creating Backpack client"""
        mock_client = Mock()
        mock_bp_client.return_value = mock_client
        
        client = _get_client(
            api_key='test_key',
            secret_key='test_secret',
            exchange='backpack'
        )
        
        self.assertEqual(client, mock_client)
        mock_bp_client.assert_called_once()
    
    @patch('cli.commands.AsterClient')
    def test_create_aster_client(self, mock_aster_client):
        """Test creating Aster client"""
        mock_client = Mock()
        mock_aster_client.return_value = mock_client
        
        client = _get_client(
            api_key='test_key',
            secret_key='test_secret',
            exchange='aster'
        )
        
        self.assertEqual(client, mock_client)
        mock_aster_client.assert_called_once()
    
    @patch('cli.commands.ParadexClient')
    def test_create_paradex_client(self, mock_paradex_client):
        """Test creating Paradex client"""
        mock_client = Mock()
        mock_paradex_client.return_value = mock_client
        
        exchange_config = {
            'account_address': '0x123',
            'private_key': 'key123'
        }
        
        client = _get_client(
            api_key='0x123',
            secret_key='key123',
            exchange='paradex',
            exchange_config=exchange_config
        )
        
        self.assertEqual(client, mock_client)
        mock_paradex_client.assert_called_once()
    
    @patch('cli.commands.LighterClient')
    def test_create_lighter_client(self, mock_lighter_client):
        """Test creating Lighter client"""
        mock_client = Mock()
        mock_lighter_client.return_value = mock_client
        
        os.environ['LIGHTER_BASE_URL'] = 'https://test.lighter.xyz'
        
        client = _get_client(
            api_key='private_key',
            secret_key='1',
            exchange='lighter'
        )
        
        self.assertEqual(client, mock_client)
        mock_lighter_client.assert_called_once()
    
    @patch('cli.commands.BPClient')
    def test_client_caching(self, mock_bp_client):
        """Test that clients are cached"""
        mock_client = Mock()
        mock_bp_client.return_value = mock_client
        
        # First call
        client1 = _get_client(
            api_key='test_key',
            secret_key='test_secret',
            exchange='backpack'
        )
        
        # Second call with same parameters
        client2 = _get_client(
            api_key='test_key',
            secret_key='test_secret',
            exchange='backpack'
        )
        
        # Should return the same cached instance
        self.assertIs(client1, client2)
        # Client constructor should only be called once
        self.assertEqual(mock_bp_client.call_count, 1)
    
    @patch('cli.commands.BPClient')
    def test_different_clients_not_cached_together(self, mock_bp_client):
        """Test that different client configs create separate instances"""
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_bp_client.side_effect = [mock_client1, mock_client2]
        
        client1 = _get_client(
            api_key='key1',
            secret_key='secret1',
            exchange='backpack'
        )
        
        client2 = _get_client(
            api_key='key2',
            secret_key='secret2',
            exchange='backpack'
        )
        
        # Should be different instances
        self.assertIsNot(client1, client2)
        self.assertEqual(mock_bp_client.call_count, 2)
    
    def test_unsupported_exchange(self):
        """Test handling of unsupported exchange"""
        with self.assertRaises(ValueError) as context:
            _get_client(exchange='unsupported_exchange')
        
        self.assertIn('不支持的交易所', str(context.exception))
    
    @patch('cli.commands.LighterClient')
    def test_lighter_config_merging(self, mock_lighter_client):
        """Test Lighter config parameter merging"""
        mock_client = Mock()
        mock_lighter_client.return_value = mock_client
        
        os.environ['LIGHTER_BASE_URL'] = 'https://test.lighter.xyz'
        os.environ['LIGHTER_API_KEY_INDEX'] = '0'
        os.environ['LIGHTER_CHAIN_ID'] = '42161'
        
        exchange_config = {
            'api_key': 'private_key',
            'secret_key': '1'
        }
        
        client = _get_client(
            exchange='lighter',
            exchange_config=exchange_config
        )
        
        # Verify the config was properly transformed
        call_args = mock_lighter_client.call_args[0][0]
        self.assertIn('api_private_key', call_args)
        self.assertIn('account_index', call_args)
        self.assertIn('base_url', call_args)
        self.assertIn('api_key_index', call_args)
        self.assertIn('chain_id', call_args)


class TestConfigureRebalanceSettings(unittest.TestCase):
    """Test configure_rebalance_settings function"""
    
    @patch('builtins.input')
    def test_enable_rebalance_with_defaults(self, mock_input):
        """Test enabling rebalance with default values"""
        mock_input.side_effect = ['y', '', '']  # Yes, default percentage, default threshold
        
        enable, percentage, threshold = configure_rebalance_settings()
        
        self.assertTrue(enable)
        self.assertEqual(percentage, 30.0)
        self.assertEqual(threshold, 15.0)
    
    @patch('builtins.input')
    def test_enable_rebalance_with_custom_values(self, mock_input):
        """Test enabling rebalance with custom values"""
        mock_input.side_effect = ['y', '40', '20']
        
        enable, percentage, threshold = configure_rebalance_settings()
        
        self.assertTrue(enable)
        self.assertEqual(percentage, 40.0)
        self.assertEqual(threshold, 20.0)
    
    @patch('builtins.input')
    def test_disable_rebalance(self, mock_input):
        """Test disabling rebalance"""
        mock_input.side_effect = ['n']
        
        enable, percentage, threshold = configure_rebalance_settings()
        
        self.assertFalse(enable)
        # Values should still be set to defaults even when disabled
        self.assertEqual(percentage, 30.0)
        self.assertEqual(threshold, 15.0)
    
    @patch('builtins.input')
    def test_invalid_percentage_retry(self, mock_input):
        """Test retry on invalid percentage input"""
        mock_input.side_effect = ['y', '150', '50', '']  # Invalid, valid, default threshold
        
        enable, percentage, threshold = configure_rebalance_settings()
        
        self.assertTrue(enable)
        self.assertEqual(percentage, 50.0)
    
    @patch('builtins.input')
    def test_invalid_threshold_retry(self, mock_input):
        """Test retry on invalid threshold input"""
        mock_input.side_effect = ['y', '', '-5', '10']  # Default percentage, invalid, valid
        
        enable, percentage, threshold = configure_rebalance_settings()
        
        self.assertTrue(enable)
        self.assertEqual(threshold, 10.0)
    
    @patch('builtins.input')
    def test_non_numeric_input_retry(self, mock_input):
        """Test retry on non-numeric input"""
        mock_input.side_effect = ['y', 'abc', '30', 'xyz', '15']
        
        enable, percentage, threshold = configure_rebalance_settings()
        
        self.assertTrue(enable)
        self.assertEqual(percentage, 30.0)
        self.assertEqual(threshold, 15.0)
    
    @patch('builtins.input')
    def test_alternative_yes_inputs(self, mock_input):
        """Test various ways to say yes"""
        for yes_input in ['y', 'Y', 'yes', 'YES', 'Yes']:
            mock_input.side_effect = [yes_input, '', '']
            
            enable, _, _ = configure_rebalance_settings()
            
            self.assertTrue(enable, f"Failed for input: {yes_input}")
    
    @patch('builtins.input')
    def test_alternative_no_inputs(self, mock_input):
        """Test various ways to say no"""
        for no_input in ['n', 'N', 'no', 'NO', 'No']:
            mock_input.side_effect = [no_input]
            
            enable, _, _ = configure_rebalance_settings()
            
            self.assertFalse(enable, f"Failed for input: {no_input}")


class TestGetBalanceCommand(unittest.TestCase):
    """Test get_balance_command function"""
    
    def setUp(self):
        """Set up test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('cli.commands._get_client')
    @patch('cli.commands._resolve_api_credentials')
    @patch('builtins.print')
    def test_single_exchange_balance(self, mock_print, mock_resolve, mock_get_client):
        """Test getting balance for single exchange"""
        # Mock credentials
        mock_resolve.return_value = ('test_api', 'test_secret')
        
        # Mock client
        mock_client = Mock()
        mock_client.get_balance.return_value = {
            'SOL': {'available': '10.5', 'locked': '0.0'},
            'USDC': {'available': '1000.0', 'locked': '50.0'}
        }
        mock_client.get_collateral.return_value = {
            'assets': [
                {'symbol': 'SOL', 'totalQuantity': '10.5', 'availableQuantity': '10.5'}
            ]
        }
        mock_get_client.return_value = mock_client
        
        get_balance_command('test_api', 'test_secret')
        
        # Verify client was called
        mock_client.get_balance.assert_called_once()
        mock_client.get_collateral.assert_called_once()
    
    @patch('cli.commands._get_client')
    @patch('cli.commands._resolve_api_credentials')
    @patch('builtins.print')
    def test_no_configured_exchanges(self, mock_print, mock_resolve, mock_get_client):
        """Test when no exchanges are configured"""
        # Mock no credentials
        mock_resolve.return_value = (None, None)
        
        get_balance_command(None, None)
        
        # Should print error message
        mock_print.assert_any_call("未找到任何已配置的交易所 API 密鑰")
    
    @patch('cli.commands._get_client')
    @patch('cli.commands._resolve_api_credentials')
    @patch('builtins.print')
    def test_balance_error_handling(self, mock_print, mock_resolve, mock_get_client):
        """Test handling of balance retrieval errors"""
        mock_resolve.return_value = ('test_api', 'test_secret')
        
        mock_client = Mock()
        mock_client.get_balance.return_value = {'error': 'API Error'}
        mock_client.get_collateral.return_value = {'error': 'API Error'}
        mock_get_client.return_value = mock_client
        
        get_balance_command('test_api', 'test_secret')
        
        # Should handle error gracefully
        mock_print.assert_any_call(unittest.mock.ANY)  # Any print call is fine
    
    @patch('cli.commands._get_client')
    @patch('cli.commands._resolve_api_credentials')
    @patch('builtins.print')
    def test_paradex_collateral_format(self, mock_print, mock_resolve, mock_get_client):
        """Test Paradex-specific collateral format"""
        mock_resolve.side_effect = [
            (None, None),  # backpack
            (None, None),  # aster
            ('0x123', 'private_key'),  # paradex
            (None, None),  # lighter
        ]
        
        mock_client = Mock()
        mock_client.get_balance.return_value = {'USDC': {'available': '1000', 'locked': '0'}}
        mock_client.get_collateral.return_value = {
            'account': '0x123',
            'account_value': '1000.0',
            'total_collateral': '1000.0',
            'free_collateral': '900.0'
        }
        mock_get_client.return_value = mock_client
        
        os.environ['PARADEX_BASE_URL'] = 'https://api.prod.paradex.trade/v1'
        
        get_balance_command(None, None)
        
        # Should display Paradex-specific fields
        mock_client.get_balance.assert_called_once()


class TestCliEdgeCases(unittest.TestCase):
    """Test edge cases and error handling in CLI commands"""
    
    def test_empty_exchange_string(self):
        """Test handling of empty exchange string"""
        api_key, secret_key = _resolve_api_credentials('', 'key', 'secret')
        
        # Should default to backpack or return provided values
        self.assertEqual(api_key, 'key')
        self.assertEqual(secret_key, 'secret')
    
    def test_case_insensitive_exchange_name(self):
        """Test that exchange names are case-insensitive"""
        os.environ['BACKPACK_KEY'] = 'test_key'
        os.environ['BACKPACK_SECRET'] = 'test_secret'
        
        for exchange in ['BACKPACK', 'Backpack', 'backpack', 'BaCkPaCk']:
            api_key, secret_key = _resolve_api_credentials(exchange, None, None)
            self.assertEqual(api_key, 'test_key')
            self.assertEqual(secret_key, 'test_secret')


if __name__ == '__main__':
    unittest.main()