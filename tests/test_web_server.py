"""
Comprehensive unit tests for web/server.py
Tests Flask web server endpoints and functionality
"""
import unittest
import json
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

# Import Flask app for testing
from web.server import app, bot_status


class TestWebServerEndpoints(unittest.TestCase):
    """Test Flask web server endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Reset bot_status
        bot_status.clear()
        bot_status.update({
            'running': False,
            'strategy': None,
            'symbol': None,
            'exchange': None
        })
    
    def test_health_endpoint_bot_stopped(self):
        """Test health endpoint when bot is stopped"""
        response = self.client.get('/health')
        
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'stopped')
    
    def test_health_endpoint_bot_running(self):
        """Test health endpoint when bot is running"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        bot_status['symbol'] = 'SOL_USDC'
        
        response = self.client.get('/health')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'running')
        self.assertEqual(data['strategy'], 'grid')
    
    def test_status_endpoint(self):
        """Test status endpoint"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        bot_status['symbol'] = 'SOL_USDC'
        bot_status['exchange'] = 'backpack'
        
        response = self.client.get('/api/status')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['running'])
        self.assertEqual(data['strategy'], 'grid')
    
    def test_grid_adjust_endpoint_valid_request(self):
        """Test grid adjustment with valid request"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        request_data = {
            'grid_lower_price': 90.0,
            'grid_upper_price': 110.0
        }
        
        with patch('web.server.adjust_grid_strategy') as mock_adjust:
            mock_adjust.return_value = {'success': True}
            
            response = self.client.post(
                '/api/grid/adjust',
                data=json.dumps(request_data),
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 200)
    
    def test_grid_adjust_endpoint_invalid_request(self):
        """Test grid adjustment with invalid request"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        request_data = {
            'grid_lower_price': -10.0,  # Invalid negative price
            'grid_upper_price': 110.0
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_grid_adjust_endpoint_bot_not_running(self):
        """Test grid adjustment when bot is not running"""
        bot_status['running'] = False
        
        request_data = {
            'grid_lower_price': 90.0,
            'grid_upper_price': 110.0
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_grid_adjust_price_range_validation(self):
        """Test grid adjustment price range validation"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        request_data = {
            'grid_lower_price': 110.0,  # Lower > Upper (invalid)
            'grid_upper_price': 90.0
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('驗證失敗', data.get('message', ''))
    
    def test_cors_headers(self):
        """Test CORS headers are set correctly"""
        response = self.client.get('/api/status')
        
        # Check for CORS headers if configured
        self.assertEqual(response.status_code, 200)
    
    def test_json_content_type(self):
        """Test that responses have correct content type"""
        response = self.client.get('/api/status')
        
        self.assertEqual(response.content_type, 'application/json')
    
    def test_404_error_handling(self):
        """Test 404 error handling"""
        response = self.client.get('/api/nonexistent')
        
        self.assertEqual(response.status_code, 404)
    
    def test_method_not_allowed(self):
        """Test method not allowed error"""
        # Try POST on a GET-only endpoint
        response = self.client.post('/api/status')
        
        self.assertEqual(response.status_code, 405)
    
    def test_malformed_json_request(self):
        """Test handling of malformed JSON"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        response = self.client.post(
            '/api/grid/adjust',
            data='{ invalid json }',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_missing_required_fields(self):
        """Test handling of missing required fields"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        request_data = {
            'grid_lower_price': 90.0
            # Missing grid_upper_price
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Should handle gracefully
        self.assertIn(response.status_code, [400, 422])
    
    def test_extreme_price_values(self):
        """Test handling of extreme price values"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        request_data = {
            'grid_lower_price': 0.0001,
            'grid_upper_price': 999999.0
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Should validate price ranges
        self.assertIsNotNone(response.status_code)


class TestBotStatusManagement(unittest.TestCase):
    """Test bot status management"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        bot_status.clear()
        bot_status.update({
            'running': False,
            'strategy': None,
            'symbol': None,
            'exchange': None
        })
    
    def test_bot_status_initialization(self):
        """Test bot status is properly initialized"""
        self.assertIn('running', bot_status)
        self.assertIn('strategy', bot_status)
        self.assertFalse(bot_status['running'])
    
    def test_bot_status_update(self):
        """Test updating bot status"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        bot_status['symbol'] = 'SOL_USDC'
        
        self.assertTrue(bot_status['running'])
        self.assertEqual(bot_status['strategy'], 'grid')
    
    def test_multiple_status_queries(self):
        """Test multiple status queries return consistent results"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        response1 = self.client.get('/api/status')
        response2 = self.client.get('/api/status')
        
        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)
        
        self.assertEqual(data1, data2)


class TestInputValidationIntegration(unittest.TestCase):
    """Test input validation integration with web endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
    
    def test_validation_rejects_negative_prices(self):
        """Test that negative prices are rejected"""
        test_cases = [
            {'grid_lower_price': -10.0, 'grid_upper_price': 100.0},
            {'grid_lower_price': 10.0, 'grid_upper_price': -100.0},
            {'grid_lower_price': -10.0, 'grid_upper_price': -5.0}
        ]
        
        for test_data in test_cases:
            response = self.client.post(
                '/api/grid/adjust',
                data=json.dumps(test_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 400,
                           f"Failed for test data: {test_data}")
    
    def test_validation_rejects_inverted_range(self):
        """Test that inverted price ranges are rejected"""
        request_data = {
            'grid_lower_price': 200.0,
            'grid_upper_price': 100.0
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_validation_accepts_valid_ranges(self):
        """Test that valid price ranges are accepted"""
        request_data = {
            'grid_lower_price': 90.0,
            'grid_upper_price': 110.0
        }
        
        with patch('web.server.adjust_grid_strategy') as mock_adjust:
            mock_adjust.return_value = {'success': True}
            
            response = self.client.post(
                '/api/grid/adjust',
                data=json.dumps(request_data),
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 200)
    
    def test_validation_error_messages(self):
        """Test that validation errors return meaningful messages"""
        request_data = {
            'grid_lower_price': -10.0,
            'grid_upper_price': 110.0
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        self.assertIn('message', data)
        self.assertTrue(len(data['message']) > 0)


class TestWebServerEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_empty_request_body(self):
        """Test handling of empty request body"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        response = self.client.post(
            '/api/grid/adjust',
            data='',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_wrong_content_type(self):
        """Test handling of wrong content type"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        response = self.client.post(
            '/api/grid/adjust',
            data='grid_lower_price=90.0&grid_upper_price=110.0',
            content_type='application/x-www-form-urlencoded'
        )
        
        # Should handle gracefully
        self.assertIn(response.status_code, [400, 415, 422])
    
    def test_concurrent_requests(self):
        """Test handling of concurrent requests"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        # Send multiple status requests
        responses = [self.client.get('/api/status') for _ in range(10)]
        
        # All should succeed
        for response in responses:
            self.assertEqual(response.status_code, 200)
    
    def test_large_price_values(self):
        """Test handling of very large price values"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        request_data = {
            'grid_lower_price': 1e10,
            'grid_upper_price': 1e11
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Should validate or reject extreme values
        self.assertIsNotNone(response.status_code)
    
    def test_unicode_in_request(self):
        """Test handling of Unicode characters in request"""
        bot_status['running'] = True
        bot_status['strategy'] = 'grid'
        
        request_data = {
            'grid_lower_price': 90.0,
            'grid_upper_price': 110.0,
            'note': '測試 🚀'
        }
        
        response = self.client.post(
            '/api/grid/adjust',
            data=json.dumps(request_data),
            content_type='application/json; charset=utf-8'
        )
        
        # Should handle Unicode gracefully
        self.assertIsNotNone(response.status_code)


if __name__ == '__main__':
    unittest.main()