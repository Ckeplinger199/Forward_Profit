"""
Visual test script for the Forward Profit Trading Bot Gradio interface.
This script launches the Gradio interface with mock data for visual inspection.
"""

import os
import sys
import pandas as pd
import numpy as np
import json
from unittest.mock import patch, MagicMock
import logging
import gradio as gr

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_interface_visual.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_interface_visual")

# Import the module to test
import gradio_interface
from config import SYMBOLS

# Create mock data
def create_mock_data():
    """Create mock data for testing the interface."""
    # Mock account data
    account_data = {
        "account_number": "DEMO12345",
        "account_type": "margin",
        "balance": 50000.00,
        "buying_power": 100000.00,
        "cash": 25000.00,
        "day_trades_remaining": 3,
        "option_level": 2,
        "status": "active"
    }
    
    # Mock positions
    positions_data = pd.DataFrame({
        "Symbol": ["AAPL", "MSFT", "SPY"],
        "Quantity": [100, 50, 20],
        "Cost Basis": [150.00, 280.00, 420.00],
        "Current Price": [165.75, 298.50, 432.40],
        "Current Value": [16575.00, 14925.00, 8648.00],
        "P&L": [1575.00, 925.00, 248.00],
        "P&L %": [10.50, 6.60, 2.95],
        "Date Acquired": ["2025-02-15", "2025-03-01", "2025-03-10"]
    })
    
    # Mock day trade status
    day_trade_status = {
        "Day Trades Used": "1/3",
        "Can Day Trade": "Yes"
    }
    
    # Mock market indicators
    market_indicators = pd.DataFrame([
        {"Symbol": "AAPL", "Price": "$165.75", "RSI": "62.30", "MACD": "2.50", "Signal": "1.80", "MA20": "$160.20", "MA50": "$155.40", "Trend": "Bullish"},
        {"Symbol": "MSFT", "Price": "$298.50", "RSI": "58.70", "MACD": "1.20", "Signal": "0.90", "MA20": "$290.10", "MA50": "$285.30", "Trend": "Neutral"},
        {"Symbol": "GOOGL", "Price": "$2450.25", "RSI": "65.40", "MACD": "3.10", "Signal": "2.20", "MA20": "$2400.60", "MA50": "$2380.20", "Trend": "Bullish"}
    ])
    
    # Mock recent trading activity
    recent_activity = pd.DataFrame({
        "Date": pd.date_range(start="2025-03-15", periods=5),
        "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        "Action": ["buy", "sell", "buy", "buy", "sell"],
        "Quantity": [100, 50, 10, 5, 20],
        "Price": ["$150.00", "$290.00", "$2400.00", "$3150.00", "$190.00"],
        "P&L": ["$0.00", "$500.00", "$0.00", "$0.00", "$200.00"]
    })
    
    # Mock bot logs
    bot_logs = """
2025-03-20 09:31:05 - trading_bot - INFO - Market open, starting trading operations
2025-03-20 09:32:10 - trading_bot - INFO - Running morning analysis for AAPL
2025-03-20 09:35:22 - trading_bot - INFO - Sentiment analysis for AAPL: Bullish
2025-03-20 10:15:40 - trading_bot - INFO - Found buying opportunity for AAPL
2025-03-20 10:15:45 - trading_bot - INFO - Placing buy order for AAPL options
2025-03-20 10:16:02 - trading_bot - INFO - Order executed successfully: AAPL250418C00170000
2025-03-20 12:00:05 - trading_bot - INFO - Running midday analysis
2025-03-20 13:45:10 - trading_bot - INFO - Managing positions, checking stop loss and take profit levels
2025-03-20 15:30:22 - trading_bot - INFO - Market closing soon, preparing end of day summary
    """
    
    return {
        "account_summary": account_data,
        "positions": positions_data,
        "day_trade_status": day_trade_status,
        "market_indicators": market_indicators,
        "recent_activity": recent_activity,
        "bot_logs": bot_logs
    }

# Patch module functions
def patch_module_functions():
    """Patch module functions with mock data."""
    mock_data = create_mock_data()
    
    # Patch functions
    gradio_interface.get_account_summary = MagicMock(return_value=mock_data["account_summary"])
    gradio_interface.get_positions = MagicMock(return_value=mock_data["positions"])
    gradio_interface.get_day_trade_status = MagicMock(return_value=mock_data["day_trade_status"])
    gradio_interface.reset_day_trades = MagicMock(return_value=[
        {"message": "Day trades reset successfully", "count": 0},
        {"Day Trades Used": "0/3", "Can Day Trade": "Yes"}
    ])
    gradio_interface.refresh_market_indicators = MagicMock(return_value=mock_data["market_indicators"])
    gradio_interface.get_recent_trading_activity = MagicMock(return_value=mock_data["recent_activity"])
    gradio_interface.get_latest_bot_logs = MagicMock(return_value=mock_data["bot_logs"])
    
    # Performance chart mock
    import plotly.graph_objects as go
    import plotly.express as px
    
    def mock_performance_chart():
        dates = pd.date_range(start="2025-03-01", periods=20)
        pnl = np.cumsum(np.random.normal(100, 200, 20))
        df = pd.DataFrame({"Date": dates, "P&L": pnl})
        fig = px.line(df, x="Date", y="P&L", title="Cumulative P&L")
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Profit/Loss ($)",
            template="plotly_white"
        )
        return fig
    
    gradio_interface.get_performance_chart = MagicMock(side_effect=mock_performance_chart)
    
    # Initialize bot functions
    gradio_interface.initialize_bot = MagicMock(return_value="Trading bot components initialized successfully.")
    gradio_interface.start_bot = MagicMock(return_value="Trading bot started successfully. Scheduled tasks will run during market hours.")
    gradio_interface.stop_bot = MagicMock(return_value="Trading bot stopped successfully.")
    
    # Mock refresh dashboard to use our mocked functions
    original_refresh_dashboard = gradio_interface.refresh_dashboard
    
    def mock_refresh_dashboard():
        return [
            mock_data["account_summary"],
            mock_data["positions"],
            mock_data["day_trade_status"],
            None,
            mock_data["market_indicators"],
            mock_data["recent_activity"],
            mock_data["bot_logs"],
            mock_performance_chart()
        ]
    
    gradio_interface.refresh_dashboard = MagicMock(side_effect=mock_refresh_dashboard)

def run_visual_test():
    """Run the visual test of the Gradio interface."""
    logger.info("Starting visual test of Gradio interface")
    
    # Patch module functions
    patch_module_functions()
    
    # Create and launch interface
    app = gradio_interface.create_gradio_interface()
    app.launch(server_name="127.0.0.1", server_port=7861, share=False)

if __name__ == "__main__":
    run_visual_test()
