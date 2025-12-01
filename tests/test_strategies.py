"""
Comprehensive unit tests for strategy modules
Tests grid_strategy.py, perp_grid_strategy.py, and market_maker.py
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# Import strategies under test
from strategies.grid_strategy import GridStrategy
from strategies.perp_grid_strategy import PerpGridStrategy
from strategies.market_maker import MarketMaker


class TestGridStrategy(unittest.TestCase):
    """Test GridStrategy class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.get_ticker.return_value = {
            'lastPrice': '100.0',
            'bid': '99.5',
            'ask': '100.5'
        }
        self.mock_client.get_market_limits.return_value = {
            'base_asset': 'SOL',
            'quote_asset': 'USDC',
            'min_order_size': '0.01',
            'max_order_size': '1000.0',
            'tick_size': '0.01',
            'step_size': '0.01'
        }
        
        self.strategy = GridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            quantity=1.0
        )
    
    def test_init_with_default_params(self):
        """Test initialization with default parameters"""
        strategy = GridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10
        )
        
        self.assertEqual(strategy.symbol, 'SOL_USDC')
        self.assertEqual(strategy.grid_lower_price, 90.0)
        self.assertEqual(strategy.grid_upper_price, 110.0)
        self.assertEqual(strategy.grid_num, 10)
        self.assertEqual(strategy.grid_mode, 'arithmetic')
    
    def test_init_with_geometric_mode(self):
        """Test initialization with geometric grid mode"""
        strategy = GridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            grid_mode='geometric'
        )
        
        self.assertEqual(strategy.grid_mode, 'geometric')
    
    def test_calculate_grid_levels_arithmetic(self):
        """Test arithmetic grid level calculation"""
        levels = self.strategy.calculate_grid_levels()
        
        # Should have 11 levels (including bounds)
        self.assertEqual(len(levels), 11)
        # First level should be lower bound
        self.assertEqual(levels[0], 90.0)
        # Last level should be upper bound
        self.assertEqual(levels[-1], 110.0)
        # Check spacing is arithmetic
        spacing = levels[1] - levels[0]
        for i in range(1, len(levels) - 1):
            self.assertAlmostEqual(levels[i+1] - levels[i], spacing, places=2)
    
    def test_calculate_grid_levels_geometric(self):
        """Test geometric grid level calculation"""
        strategy = GridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            grid_mode='geometric'
        )
        
        levels = strategy.calculate_grid_levels()
        
        # Should have 11 levels
        self.assertEqual(len(levels), 11)
        # First and last should match bounds
        self.assertEqual(levels[0], 90.0)
        self.assertEqual(levels[-1], 110.0)
        # Check spacing is geometric
        ratio = levels[1] / levels[0]
        for i in range(1, len(levels) - 1):
            self.assertAlmostEqual(levels[i+1] / levels[i], ratio, places=2)
    
    def test_invalid_price_range(self):
        """Test error handling for invalid price range"""
        with self.assertRaises(ValueError):
            GridStrategy(
                client=self.mock_client,
                symbol='SOL_USDC',
                grid_lower_price=110.0,  # Higher than upper
                grid_upper_price=90.0,
                grid_num=10
            )
    
    def test_invalid_grid_num(self):
        """Test error handling for invalid grid number"""
        with self.assertRaises(ValueError):
            GridStrategy(
                client=self.mock_client,
                symbol='SOL_USDC',
                grid_lower_price=90.0,
                grid_upper_price=110.0,
                grid_num=1  # Too few grids
            )
    
    def test_place_grid_orders(self):
        """Test placing grid orders"""
        self.mock_client.place_order.return_value = {
            'orderId': '123',
            'status': 'FILLED'
        }
        
        with patch.object(self.strategy, 'calculate_grid_levels', return_value=[95.0, 100.0, 105.0]):
            self.strategy.place_grid_orders()
        
        # Should place orders at calculated levels
        self.assertTrue(self.mock_client.place_order.called)
    
    def test_adjust_grid_range(self):
        """Test adjusting grid price range"""
        old_lower = self.strategy.grid_lower_price
        old_upper = self.strategy.grid_upper_price
        
        self.strategy.adjust_grid_range(new_lower=85.0, new_upper=115.0)
        
        self.assertEqual(self.strategy.grid_lower_price, 85.0)
        self.assertEqual(self.strategy.grid_upper_price, 115.0)
        self.assertNotEqual(self.strategy.grid_lower_price, old_lower)
        self.assertNotEqual(self.strategy.grid_upper_price, old_upper)
    
    def test_grid_level_count(self):
        """Test that grid levels count matches grid_num"""
        for grid_num in [5, 10, 20, 50]:
            strategy = GridStrategy(
                client=self.mock_client,
                symbol='SOL_USDC',
                grid_lower_price=90.0,
                grid_upper_price=110.0,
                grid_num=grid_num
            )
            
            levels = strategy.calculate_grid_levels()
            # Should have grid_num + 1 levels (including both bounds)
            self.assertEqual(len(levels), grid_num + 1)


class TestPerpGridStrategy(unittest.TestCase):
    """Test PerpGridStrategy class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.get_ticker.return_value = {
            'lastPrice': '100.0',
            'markPrice': '100.1',
            'indexPrice': '100.0'
        }
        self.mock_client.get_market_limits.return_value = {
            'base_asset': 'SOL',
            'quote_asset': 'USDC',
            'min_order_size': '0.01',
            'max_order_size': '1000.0',
            'tick_size': '0.01',
            'step_size': '0.01'
        }
        self.mock_client.get_position.return_value = {
            'size': '0.0',
            'entryPrice': '0.0',
            'unrealizedPnl': '0.0'
        }
        
        self.strategy = PerpGridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC_PERP',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            quantity=1.0,
            grid_type='neutral',
            max_position=10.0
        )
    
    def test_init_neutral_grid(self):
        """Test initialization with neutral grid type"""
        self.assertEqual(self.strategy.grid_type, 'neutral')
        self.assertEqual(self.strategy.max_position, 10.0)
    
    def test_init_long_grid(self):
        """Test initialization with long grid type"""
        strategy = PerpGridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC_PERP',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            quantity=1.0,
            grid_type='long',
            max_position=10.0
        )
        
        self.assertEqual(strategy.grid_type, 'long')
    
    def test_init_short_grid(self):
        """Test initialization with short grid type"""
        strategy = PerpGridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC_PERP',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            quantity=1.0,
            grid_type='short',
            max_position=10.0
        )
        
        self.assertEqual(strategy.grid_type, 'short')
    
    def test_check_position_limits(self):
        """Test position limit checking"""
        # Set position close to limit
        self.mock_client.get_position.return_value = {
            'size': '9.5',  # Close to max_position of 10
            'entryPrice': '100.0',
            'unrealizedPnl': '50.0'
        }
        
        # Should detect position is near limit
        result = self.strategy.check_position_limits()
        
        self.assertIsNotNone(result)
    
    def test_stop_loss_trigger(self):
        """Test stop loss triggering"""
        strategy = PerpGridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC_PERP',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            quantity=1.0,
            max_position=10.0,
            stop_loss=-50.0  # Stop loss at -50 USDC
        )
        
        # Set large negative PnL
        self.mock_client.get_position.return_value = {
            'size': '5.0',
            'entryPrice': '100.0',
            'unrealizedPnl': '-60.0'  # Exceeds stop loss
        }
        
        should_trigger = strategy.check_stop_loss()
        
        self.assertTrue(should_trigger)
    
    def test_take_profit_trigger(self):
        """Test take profit triggering"""
        strategy = PerpGridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC_PERP',
            grid_lower_price=90.0,
            grid_upper_price=110.0,
            grid_num=10,
            quantity=1.0,
            max_position=10.0,
            take_profit=100.0  # Take profit at +100 USDC
        )
        
        # Set large positive PnL
        self.mock_client.get_position.return_value = {
            'size': '5.0',
            'entryPrice': '100.0',
            'unrealizedPnl': '120.0'  # Exceeds take profit
        }
        
        should_trigger = strategy.check_take_profit()
        
        self.assertTrue(should_trigger)
    
    def test_grid_symmetry_neutral(self):
        """Test that neutral grid places symmetric orders"""
        levels = self.strategy.calculate_grid_levels()
        
        # For neutral grid, should have balanced buy/sell levels
        mid_price = (self.strategy.grid_lower_price + self.strategy.grid_upper_price) / 2
        
        buy_levels = [l for l in levels if l < mid_price]
        sell_levels = [l for l in levels if l > mid_price]
        
        # Should have roughly equal buy and sell levels
        self.assertAlmostEqual(len(buy_levels), len(sell_levels), delta=1)
    
    def test_invalid_grid_type(self):
        """Test error handling for invalid grid type"""
        with self.assertRaises(ValueError):
            PerpGridStrategy(
                client=self.mock_client,
                symbol='SOL_USDC_PERP',
                grid_lower_price=90.0,
                grid_upper_price=110.0,
                grid_num=10,
                quantity=1.0,
                grid_type='invalid',  # Invalid type
                max_position=10.0
            )
    
    def test_position_size_tracking(self):
        """Test position size tracking"""
        # Initial position
        self.mock_client.get_position.return_value = {
            'size': '5.0',
            'entryPrice': '100.0',
            'unrealizedPnl': '10.0'
        }
        
        position = self.strategy.get_current_position()
        
        self.assertEqual(float(position['size']), 5.0)
        self.assertEqual(float(position['unrealizedPnl']), 10.0)


class TestMarketMaker(unittest.TestCase):
    """Test MarketMaker class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.get_ticker.return_value = {
            'lastPrice': '100.0',
            'bid': '99.5',
            'ask': '100.5',
            'volume': '10000'
        }
        self.mock_client.get_market_limits.return_value = {
            'base_asset': 'SOL',
            'quote_asset': 'USDC',
            'min_order_size': '0.01',
            'max_order_size': '1000.0',
            'tick_size': '0.01',
            'step_size': '0.01'
        }
        self.mock_client.get_balance.return_value = {
            'SOL': {'available': '100.0', 'locked': '0.0'},
            'USDC': {'available': '10000.0', 'locked': '0.0'}
        }
        
        self.strategy = MarketMaker(
            client=self.mock_client,
            symbol='SOL_USDC',
            spread_percentage=0.5,
            quantity=1.0,
            max_orders=3
        )
    
    def test_init_with_params(self):
        """Test initialization with parameters"""
        self.assertEqual(self.strategy.symbol, 'SOL_USDC')
        self.assertEqual(self.strategy.spread_percentage, 0.5)
        self.assertEqual(self.strategy.quantity, 1.0)
        self.assertEqual(self.strategy.max_orders, 3)
    
    def test_calculate_bid_ask_prices(self):
        """Test bid/ask price calculation"""
        mid_price = 100.0
        spread = 0.5  # 0.5%
        
        bid, ask = self.strategy.calculate_bid_ask_prices(mid_price)
        
        expected_bid = mid_price * (1 - spread / 100)
        expected_ask = mid_price * (1 + spread / 100)
        
        self.assertAlmostEqual(bid, expected_bid, places=2)
        self.assertAlmostEqual(ask, expected_ask, places=2)
    
    def test_place_orders(self):
        """Test placing market making orders"""
        self.mock_client.place_order.return_value = {
            'orderId': '123',
            'status': 'NEW'
        }
        
        self.strategy.place_orders()
        
        # Should place both buy and sell orders
        self.assertTrue(self.mock_client.place_order.called)
        self.assertGreaterEqual(self.mock_client.place_order.call_count, 2)
    
    def test_cancel_all_orders(self):
        """Test canceling all orders"""
        self.mock_client.get_open_orders.return_value = [
            {'orderId': '123', 'side': 'BUY'},
            {'orderId': '456', 'side': 'SELL'}
        ]
        self.mock_client.cancel_order.return_value = {'status': 'CANCELED'}
        
        self.strategy.cancel_all_orders()
        
        # Should cancel all open orders
        self.assertEqual(self.mock_client.cancel_order.call_count, 2)
    
    def test_spread_adjustment(self):
        """Test dynamic spread adjustment"""
        old_spread = self.strategy.spread_percentage
        
        self.strategy.adjust_spread(new_spread=1.0)
        
        self.assertEqual(self.strategy.spread_percentage, 1.0)
        self.assertNotEqual(self.strategy.spread_percentage, old_spread)
    
    def test_quantity_calculation_from_balance(self):
        """Test automatic quantity calculation from balance"""
        strategy = MarketMaker(
            client=self.mock_client,
            symbol='SOL_USDC',
            spread_percentage=0.5,
            quantity=None,  # Auto-calculate
            max_orders=3
        )
        
        # Should calculate quantity based on available balance
        self.assertIsNotNone(strategy.quantity)
        self.assertGreater(strategy.quantity, 0)
    
    def test_inventory_skew(self):
        """Test inventory skew adjustment"""
        # Set imbalanced inventory
        self.mock_client.get_balance.return_value = {
            'SOL': {'available': '200.0', 'locked': '0.0'},  # Too much SOL
            'USDC': {'available': '1000.0', 'locked': '0.0'}  # Not enough USDC
        }
        
        strategy = MarketMaker(
            client=self.mock_client,
            symbol='SOL_USDC',
            spread_percentage=0.5,
            quantity=1.0,
            max_orders=3,
            inventory_skew=0.5
        )
        
        # Should adjust prices based on inventory
        skew = strategy.calculate_inventory_skew()
        
        self.assertIsNotNone(skew)


class TestStrategyEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.get_market_limits.return_value = {
            'base_asset': 'SOL',
            'quote_asset': 'USDC',
            'min_order_size': '0.01',
            'tick_size': '0.01'
        }
    
    def test_zero_grid_num(self):
        """Test handling of zero grid number"""
        with self.assertRaises(ValueError):
            GridStrategy(
                client=self.mock_client,
                symbol='SOL_USDC',
                grid_lower_price=90.0,
                grid_upper_price=110.0,
                grid_num=0
            )
    
    def test_negative_quantity(self):
        """Test handling of negative quantity"""
        with self.assertRaises(ValueError):
            GridStrategy(
                client=self.mock_client,
                symbol='SOL_USDC',
                grid_lower_price=90.0,
                grid_upper_price=110.0,
                grid_num=10,
                quantity=-1.0
            )
    
    def test_very_small_price_range(self):
        """Test handling of very small price range"""
        strategy = GridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC',
            grid_lower_price=99.99,
            grid_upper_price=100.01,
            grid_num=5
        )
        
        levels = strategy.calculate_grid_levels()
        
        # Should still calculate valid levels
        self.assertEqual(len(levels), 6)
        self.assertLess(levels[0], levels[-1])
    
    def test_very_large_price_range(self):
        """Test handling of very large price range"""
        strategy = GridStrategy(
            client=self.mock_client,
            symbol='SOL_USDC',
            grid_lower_price=1.0,
            grid_upper_price=1000.0,
            grid_num=10
        )
        
        levels = strategy.calculate_grid_levels()
        
        # Should handle large ranges
        self.assertEqual(len(levels), 11)
        self.assertEqual(levels[0], 1.0)
        self.assertEqual(levels[-1], 1000.0)


if __name__ == '__main__':
    unittest.main()