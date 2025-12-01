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