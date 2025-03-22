"""
Test script for the Forward Profit Trading Bot Gradio interface.
This script tests all components and functionality of the interface.
"""

import os
import unittest
import pandas as pd
import numpy as np
import json
from unittest.mock import patch, MagicMock, mock_open
import logging
import sys
import gradio as gr

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_interface.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_gradio_interface")

# Add path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module to test
import gradio_interface

class TestGradioInterface(unittest.TestCase):
    """Test cases for the Gradio interface functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock config values
        self.config_patcher = patch('gradio_interface.SYMBOLS', ['AAPL', 'MSFT', 'GOOGL'])
        self.mock_symbols = self.config_patcher.start()
        
        # Mock TradierClient
        self.tradier_patcher = patch('gradio_interface.TradierClient')
        self.mock_tradier = self.tradier_patcher.start()
        
        # Mock TradeTracker
        self.tracker_patcher = patch('gradio_interface.TradeTracker')
        self.mock_tracker = self.tracker_patcher.start()
        
        # Set up mock return values
        self.mock_tradier_instance = MagicMock()
        self.mock_tradier.return_value = self.mock_tradier_instance
        
        self.mock_tracker_instance = MagicMock()
        self.mock_tracker.return_value = self.mock_tracker_instance
        
        # Initialize module variables
        gradio_interface.tradier_client = self.mock_tradier_instance
        gradio_interface.trade_tracker = self.mock_tracker_instance
    
    def tearDown(self):
        """Clean up after tests."""
        self.config_patcher.stop()
        self.tradier_patcher.stop()
        self.tracker_patcher.stop()
    
    def test_initialize_bot(self):
        """Test the initialize_bot function."""
        result = gradio_interface.initialize_bot()
        self.assertIn("successfully", result)
        self.mock_tradier.assert_called_once()
        self.mock_tracker.assert_called_once()
    
    def test_load_trading_log_existing_file(self):
        """Test loading trading log when file exists."""
        mock_data = [
            {"timestamp": "2025-03-20T14:30:00", "symbol": "AAPL", "action": "buy", "quantity": 100, "price": 175.50, "reasoning": "Test"}
        ]
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
             patch('json.load', return_value=mock_data), \
             patch('pandas.to_datetime'):
            
            result = gradio_interface.load_trading_log()
            self.assertIsInstance(result, pd.DataFrame)
            self.assertEqual(len(result), 1)
    
    def test_load_trading_log_missing_file(self):
        """Test loading trading log when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            result = gradio_interface.load_trading_log()
            self.assertIsInstance(result, pd.DataFrame)
            self.assertTrue(result.empty)
    
    def test_get_account_summary_bot_not_initialized(self):
        """Test getting account summary when bot is not initialized."""
        gradio_interface.tradier_client = None
        result = gradio_interface.get_account_summary()
        self.assertIn("error", result)
        self.assertIn("not initialized", result["error"])
    
    def test_get_account_summary_success(self):
        """Test getting account summary successfully."""
        mock_account_data = {
            "account_number": "TEST123",
            "balance": 10000.0,
            "buying_power": 20000.0,
            "day_trades_remaining": 3
        }
        
        gradio_interface.tradier_client = self.mock_tradier_instance
        self.mock_tradier_instance.get_account_balances.return_value = mock_account_data
        
        result = gradio_interface.get_account_summary()
        self.assertEqual(result, mock_account_data)
        self.mock_tradier_instance.get_account_balances.assert_called_once()
    
    def test_get_day_trade_status(self):
        """Test getting day trade status."""
        mock_status = {
            "current_day_trades": 1,
            "max_day_trades": 3,
            "day_trades_remaining": 2
        }
        
        self.mock_tracker_instance.get_status.return_value = mock_status
        
        result = gradio_interface.get_day_trade_status()
        self.assertIn("Day Trades Used", result)
        self.assertEqual(result["Day Trades Used"], "1/3")
        self.assertEqual(result["Can Day Trade"], "Yes")
    
    def test_reset_day_trades(self):
        """Test resetting day trades."""
        mock_status = {
            "current_day_trades": 0,
            "max_day_trades": 3,
            "day_trades_remaining": 3
        }
        
        self.mock_tracker_instance.reset_day_trades.return_value = mock_status
        
        result = gradio_interface.reset_day_trades()
        self.mock_tracker_instance.reset_day_trades.assert_called_once()
        self.assertEqual(result[0]["message"], "Day trades reset successfully")
        self.assertEqual(result[1]["Day Trades Used"], "0/3")
    
    @patch('gradio_interface.market_data.get_latest_price_data')
    @patch('gradio_interface.compute_technicals')
    def test_refresh_market_indicators(self, mock_compute_technicals, mock_get_price_data):
        """Test refreshing market indicators."""
        # Set up mock price data
        mock_price_df = pd.DataFrame({
            'close': [150.0, 151.0, 152.0]
        })
        mock_get_price_data.return_value = mock_price_df
        
        # Set up mock technicals
        mock_technicals = {
            'rsi': 60.5,
            'macd': 2.3,
            'macd_signal': 1.8,
            'ma_20': 148.5,
            'ma_50': 145.0,
            'trend': 'Bullish'
        }
        mock_compute_technicals.return_value = mock_technicals
        
        result = gradio_interface.refresh_market_indicators()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreaterEqual(len(result), 1)
        mock_get_price_data.assert_called()
        mock_compute_technicals.assert_called()
    
    @patch('gradio_interface.load_trading_log')
    def test_get_recent_trading_activity(self, mock_load_trading_log):
        """Test getting recent trading activity."""
        # Create mock trading log DataFrame
        mock_df = pd.DataFrame({
            'timestamp': pd.date_range(start='2025-03-15', periods=5),
            'symbol': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'],
            'action': ['buy', 'sell', 'buy', 'buy', 'sell'],
            'quantity': [100, 50, 75, 30, 20],
            'price': [150.0, 300.0, 2500.0, 3200.0, 180.0],
            'pnl': [0.0, 500.0, 0.0, 0.0, 200.0]
        })
        mock_load_trading_log.return_value = mock_df
        
        result = gradio_interface.get_recent_trading_activity(3)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)  # Should return only 3 most recent trades
        self.assertIn("Date", result.columns)
        self.assertIn("Symbol", result.columns)
    
    def test_start_bot(self):
        """Test starting the trading bot."""
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            result = gradio_interface.start_bot()
            self.assertIn("successfully", result)
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()
            self.assertTrue(gradio_interface.bot_running)
    
    def test_stop_bot(self):
        """Test stopping the trading bot."""
        gradio_interface.bot_running = True
        gradio_interface.bot_thread = MagicMock()
        
        result = gradio_interface.stop_bot()
        self.assertIn("stopped", result)
        self.assertFalse(gradio_interface.bot_running)
    
    @patch('gradio_interface.market_data.get_option_chain')
    def test_get_option_chain(self, mock_get_option_chain):
        """Test getting option chain."""
        # Mock option chain data
        mock_options = {
            'calls': [
                {'strike': 150, 'expiration': '2025-04-18', 'bid': 5.0, 'ask': 5.2, 'symbol': 'AAPL250418C00150000'}
            ],
            'puts': [
                {'strike': 150, 'expiration': '2025-04-18', 'bid': 4.8, 'ask': 5.0, 'symbol': 'AAPL250418P00150000'}
            ]
        }
        mock_get_option_chain.return_value = mock_options
        
        # Call the function
        gradio_interface.tradier_client = self.mock_tradier_instance
        with patch('gradio_interface.format_option_chain', return_value=pd.DataFrame()):
            result = gradio_interface.get_option_chain('AAPL', '2025-04-18')
            self.assertIsInstance(result, pd.DataFrame)
            mock_get_option_chain.assert_called_once()
    
    @patch('gradio_interface.analyze_with_deepseek')
    @patch('gradio_interface.fetch_news_summary')
    def test_analyze_symbol_sentiment(self, mock_fetch_news, mock_analyze):
        """Test analyzing symbol sentiment."""
        mock_news = "Apple reports strong quarterly earnings."
        mock_sentiment = "Bullish sentiment due to strong financial performance."
        
        mock_fetch_news.return_value = mock_news
        mock_analyze.return_value = mock_sentiment
        
        result = gradio_interface.analyze_symbol_sentiment('AAPL')
        self.assertIn('AAPL', result)
        self.assertIn(mock_news, result)
        self.assertIn(mock_sentiment, result)
        mock_fetch_news.assert_called_once_with('AAPL')
        mock_analyze.assert_called_once_with('AAPL', mock_news)
    
    def test_get_performance_chart(self):
        """Test generating performance chart."""
        # Mock trading log with performance data
        mock_df = pd.DataFrame({
            'timestamp': pd.date_range(start='2025-03-01', periods=10),
            'pnl': [100, 150, -50, 200, 300, -100, 50, 75, 125, 225]
        })
        
        with patch('gradio_interface.load_trading_log', return_value=mock_df), \
             patch('plotly.graph_objects.Figure') as mock_figure:
            
            mock_fig_instance = MagicMock()
            mock_figure.return_value = mock_fig_instance
            
            result = gradio_interface.get_performance_chart()
            self.assertEqual(result, mock_fig_instance)
    
    def test_refresh_dashboard(self):
        """Test refreshing dashboard components."""
        # Set up mocks for all dashboard functions
        with patch('gradio_interface.get_account_summary', return_value={}), \
             patch('gradio_interface.get_positions', return_value=pd.DataFrame()), \
             patch('gradio_interface.get_day_trade_status', return_value={}), \
             patch('gradio_interface.refresh_market_indicators', return_value=pd.DataFrame()), \
             patch('gradio_interface.get_recent_trading_activity', return_value=pd.DataFrame()), \
             patch('gradio_interface.get_latest_bot_logs', return_value=""), \
             patch('gradio_interface.get_performance_chart', return_value=None):
            
            result = gradio_interface.refresh_dashboard()
            self.assertEqual(len(result), 8)  # Should return 8 components

if __name__ == '__main__':
    unittest.main()
