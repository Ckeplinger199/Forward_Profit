"""
Gradio interface for the Forward Profit Trading Bot.
Provides real-time monitoring, configuration management, and manual control.
"""

import os
import sys
import json
import time
import pandas as pd
import numpy as np
import gradio as gr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import threading
import logging
from concurrent.futures import ThreadPoolExecutor

# Import trading bot modules
from config import (
    SYMBOLS, USE_SANDBOX, ACCOUNT_ID, POSITION_SIZE, STOP_LOSS_PERCENT, 
    TAKE_PROFIT_PERCENT, MAX_OPTION_DTE, MIN_OPTION_DTE, MAX_DAILY_TRADES,
    CONFIDENCE_THRESHOLD, ENABLE_OPPORTUNITY_FINDER, 
    TRADIER_API_KEY, TRADIER_SANDBOX_KEY, DEEPSEEK_API_KEY
)
from trade_tracker import TradeTracker
from execution import TradierClient
import market_data
from strategy import compute_technicals, decide_trade, select_option_contract
from ai_analysis import fetch_news_summary, analyze_with_deepseek
from opportunity_finder import identify_opportunities
import main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gradio_interface.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("gradio_interface")

# Global variables
bot_running = False
bot_thread = None
tradier_client = None
trade_tracker = None
executor = ThreadPoolExecutor(max_workers=3)  # For non-blocking operations

# Theme for Gradio interface
THEME = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="indigo",
)

def load_trading_log():
    """Load the trading log JSON file into a pandas DataFrame."""
    try:
        if os.path.exists("trading_log.json"):
            with open("trading_log.json", "r") as f:
                data = json.load(f)
            # Convert to DataFrame
            df = pd.DataFrame(data)
            # Convert timestamps to datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        else:
            return pd.DataFrame(columns=["timestamp", "symbol", "action", "quantity", "price", "reasoning"])
    except Exception as e:
        logger.error(f"Error loading trading log: {e}")
        return pd.DataFrame(columns=["timestamp", "symbol", "action", "quantity", "price", "reasoning"])

def get_account_summary():
    """Get account summary from Tradier API."""
    try:
        if tradier_client is None:
            return {"error": "Trading bot not initialized. Please start the bot first."}
        
        account_data = tradier_client.get_account_balances()
        
        if not account_data or 'balances' not in account_data:
            return {"error": "Failed to retrieve account data"}
        
        balances = account_data['balances']
        
        # Extract relevant information
        summary = {
            "Account Type": balances.get('account_type', 'N/A'),
            "Total Equity": f"${balances.get('total_equity', 0):,.2f}",
            "Option Buying Power": f"${balances.get('margin', {}).get('option_buying_power', 0):,.2f}",
            "Stock Buying Power": f"${balances.get('margin', {}).get('stock_buying_power', 0):,.2f}",
            "Cash Balance": f"${balances.get('total_cash', 0):,.2f}",
            "Open P&L": f"${balances.get('open_pl', 0):,.2f}",
            "Closed P&L": f"${balances.get('close_pl', 0):,.2f}"
        }
        
        return summary
    except Exception as e:
        logger.error(f"Error getting account summary: {e}")
        return {"error": f"Error: {e}"}

def get_positions():
    """Get current positions from Tradier API."""
    try:
        if tradier_client is None:
            return pd.DataFrame(columns=["Symbol", "Quantity", "Cost Basis", "Current Price", 
                                         "Current Value", "P&L", "P&L %", "Date Acquired"])
        
        positions_data = tradier_client.get_positions()
        
        if not positions_data or 'positions' not in positions_data:
            return pd.DataFrame(columns=["Symbol", "Quantity", "Cost Basis", "Current Price", 
                                         "Current Value", "P&L", "P&L %", "Date Acquired"])
        
        # Handle case where there are no positions
        if 'position' not in positions_data['positions']:
            return pd.DataFrame(columns=["Symbol", "Quantity", "Cost Basis", "Current Price", 
                                         "Current Value", "P&L", "P&L %", "Date Acquired"])
        
        positions = positions_data['positions']['position']
        
        # Convert to list if it's a single position
        if not isinstance(positions, list):
            positions = [positions]
        
        # Create DataFrame
        df = pd.DataFrame(positions)
        
        if df.empty:
            return pd.DataFrame(columns=["Symbol", "Quantity", "Cost Basis", "Current Price", 
                                         "Current Value", "P&L", "P&L %", "Date Acquired"])
        
        # Get current quotes for each position
        for i, row in df.iterrows():
            symbol = row['symbol']
            try:
                if 'C' in symbol or 'P' in symbol:  # It's an option
                    quote = market_data.get_option_quote(symbol)
                    if quote:
                        current_price = quote.get('last', 0)
                else:  # It's a stock
                    current_price = market_data.get_current_price(symbol)
                
                # Calculate P&L
                if current_price:
                    cost = float(row['cost_basis'])
                    qty = float(row['quantity'])
                    current_value = current_price * qty
                    pnl = current_value - cost
                    pnl_percent = (pnl / cost) * 100 if cost else 0
                    
                    df.at[i, 'current_price'] = current_price
                    df.at[i, 'current_value'] = current_value
                    df.at[i, 'pnl'] = pnl
                    df.at[i, 'pnl_percent'] = pnl_percent
            except Exception as e:
                logger.error(f"Error getting quote for {symbol}: {e}")
                df.at[i, 'current_price'] = 0
                df.at[i, 'current_value'] = 0
                df.at[i, 'pnl'] = 0
                df.at[i, 'pnl_percent'] = 0
        
        # Ensure numeric columns are numeric before formatting
        numeric_cols = ['cost_basis', 'current_price', 'current_value', 'pnl', 'pnl_percent']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Rename columns for better display
        df = df.rename(columns={
            'symbol': 'Symbol',
            'quantity': 'Quantity',
            'cost_basis': 'Cost Basis',
            'current_price': 'Current Price',
            'current_value': 'Current Value',
            'pnl': 'P&L',
            'pnl_percent': 'P&L %',
            'date_acquired': 'Date Acquired'
        })
        
        # Format after renaming
        if 'Cost Basis' in df.columns:
            df['Cost Basis'] = df['Cost Basis'].map('${:,.2f}'.format)
        if 'Current Price' in df.columns:
            df['Current Price'] = df['Current Price'].map('${:,.2f}'.format)
        if 'Current Value' in df.columns:
            df['Current Value'] = df['Current Value'].map('${:,.2f}'.format)
        if 'P&L' in df.columns:
            df['P&L'] = df['P&L'].map('${:,.2f}'.format)
        if 'P&L %' in df.columns:
            df['P&L %'] = df['P&L %'].map('{:,.2f}%'.format)
        
        # Select columns to display
        display_columns = ['Symbol', 'Quantity', 'Cost Basis', 'Current Price', 
                          'Current Value', 'P&L', 'P&L %', 'Date Acquired']
        
        # Ensure all required columns exist
        for col in display_columns:
            if col not in df.columns:
                df[col] = "N/A"
                
        return df[display_columns]
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return pd.DataFrame(columns=["Symbol", "Quantity", "Cost Basis", "Current Price", 
                                    "Current Value", "P&L", "P&L %", "Date Acquired"])

def get_day_trade_status():
    """Get day trade status from TradeTracker."""
    try:
        status = trade_tracker.get_status()
        
        return {
            "Day Trades Used": f"{status['current_day_trades']}/{status['max_day_trades']}",
            "Day Trades Remaining": status['day_trades_remaining'],
            "Can Day Trade": "Yes" if status['day_trades_remaining'] > 0 else "No",
            "Recent Day Trades": status['recent_day_trades']
        }
    except Exception as e:
        logger.error(f"Error getting day trade status: {e}")
        return {
            "Day Trades Used": "Error",
            "Day Trades Remaining": "Error",
            "Can Day Trade": "Error",
            "Recent Day Trades": []
        }

def reset_day_trades():
    """Reset day trade counter."""
    try:
        status = trade_tracker.reset_day_trades()
        return {
            "Day Trades Used": f"{status['current_day_trades']}/{status['max_day_trades']}",
            "Day Trades Remaining": status['max_day_trades'],
            "Can Day Trade": "Yes",
            "Recent Day Trades": [],
            "Message": "Day trades successfully reset!"
        }
    except Exception as e:
        logger.error(f"Error resetting day trades: {e}")
        return {
            "Day Trades Used": "Error",
            "Day Trades Remaining": "Error",
            "Can Day Trade": "Error",
            "Recent Day Trades": [],
            "Message": f"Error: {str(e)}"
        }

def get_market_indicators():
    """Get current market indicators for monitored symbols."""
    try:
        # Initialize with empty DataFrame
        indicators_data = []
        
        # Add symbols but with placeholder data
        for symbol in SYMBOLS:
            indicators_data.append({
                "Symbol": symbol,
                "Price": "Click Refresh",
                "RSI": "N/A",
                "MACD": "N/A",
                "Signal": "N/A",
                "MA20": "N/A",
                "MA50": "N/A",
                "Trend": "N/A"
            })
            
        return pd.DataFrame(indicators_data)
    except Exception as e:
        logger.error(f"Error initializing market indicators: {e}")
        return pd.DataFrame(columns=["Symbol", "Price", "RSI", "MACD", "Signal", "MA20", "MA50", "Trend"])

def refresh_market_indicators():
    """Refresh market indicators for monitored symbols."""
    try:
        indicators_data = []
        
        for symbol in SYMBOLS:
            price_data = market_data.get_latest_price_data(symbol)
            if price_data is not None and not isinstance(price_data, pd.DataFrame):
                price_data = pd.DataFrame(price_data)
                
            if price_data is not None and not price_data.empty:
                technicals = compute_technicals(price_data)
                current_price = price_data['close'].iloc[-1] if 'close' in price_data.columns else "N/A"
                
                indicators_data.append({
                    "Symbol": symbol,
                    "Price": f"${current_price:.2f}" if isinstance(current_price, (int, float)) else current_price,
                    "RSI": f"{technicals.get('rsi', 'N/A'):.2f}" if isinstance(technicals.get('rsi'), (int, float)) else technicals.get('rsi', 'N/A'),
                    "MACD": f"{technicals.get('macd', 'N/A'):.2f}" if isinstance(technicals.get('macd'), (int, float)) else technicals.get('macd', 'N/A'),
                    "Signal": f"{technicals.get('macd_signal', 'N/A'):.2f}" if isinstance(technicals.get('macd_signal'), (int, float)) else technicals.get('macd_signal', 'N/A'),
                    "MA20": f"${technicals.get('ma_20', 'N/A'):.2f}" if isinstance(technicals.get('ma_20'), (int, float)) else technicals.get('ma_20', 'N/A'),
                    "MA50": f"${technicals.get('ma_50', 'N/A'):.2f}" if isinstance(technicals.get('ma_50'), (int, float)) else technicals.get('ma_50', 'N/A'),
                    "Trend": technicals.get('trend', 'N/A')
                })
        
        return pd.DataFrame(indicators_data)
    except Exception as e:
        logger.error(f"Error getting market indicators: {e}")
        return pd.DataFrame(columns=["Symbol", "Price", "RSI", "MACD", "Signal", "MA20", "MA50", "Trend"])

def get_recent_trading_activity(num_trades=10):
    """Get recent trading activity from trading log."""
    try:
        trading_log = load_trading_log()
        
        if trading_log.empty:
            return pd.DataFrame(columns=["Date", "Symbol", "Action", "Quantity", "Price", "P&L"])
        
        # Sort by timestamp descending
        trading_log = trading_log.sort_values(by='timestamp', ascending=False)
        
        # Take the most recent trades
        recent_trades = trading_log.head(num_trades)
        
        # Format for display
        display_df = pd.DataFrame({
            "Date": recent_trades['timestamp'],
            "Symbol": recent_trades['symbol'],
            "Action": recent_trades['action'],
            "Quantity": recent_trades['quantity'],
            "Price": recent_trades['price'].map('${:,.2f}'.format),
            "P&L": recent_trades['pnl'].map('${:,.2f}'.format) if 'pnl' in recent_trades.columns else "N/A"
        })
        
        return display_df
    except Exception as e:
        logger.error(f"Error getting recent trading activity: {e}")
        return pd.DataFrame(columns=["Date", "Symbol", "Action", "Quantity", "Price", "P&L"])

def get_latest_bot_logs(num_lines=20):
    """Get the latest logs from the trading bot log file."""
    try:
        if os.path.exists("trading_bot.log"):
            with open("trading_bot.log", "r") as f:
                lines = f.readlines()
            return "".join(lines[-num_lines:])
        else:
            return "Log file not found"
    except Exception as e:
        logger.error(f"Error getting bot logs: {e}")
        return f"Error reading log file: {e}"

def get_config_values():
    """Get current configuration values."""
    return {
        "Symbols": ", ".join(SYMBOLS),
        "Sandbox Mode": "Enabled" if USE_SANDBOX else "Disabled",
        "Position Size": f"{POSITION_SIZE * 100:.1f}%",
        "Stop Loss": f"{STOP_LOSS_PERCENT * 100:.1f}%",
        "Take Profit": f"{TAKE_PROFIT_PERCENT * 100:.1f}%",
        "Min Option DTE": MIN_OPTION_DTE,
        "Max Option DTE": MAX_OPTION_DTE,
        "Max Daily Trades": MAX_DAILY_TRADES,
        "Confidence Threshold": f"{CONFIDENCE_THRESHOLD:.2f}",
        "Opportunity Finder": "Enabled" if ENABLE_OPPORTUNITY_FINDER else "Disabled"
    }

def update_config(
    symbols, sandbox_mode, position_size, stop_loss, take_profit, 
    min_option_dte, max_option_dte, max_daily_trades, 
    confidence_threshold, enable_opportunity_finder
):
    """Update configuration values in config.py."""
    try:
        # Read current config file
        with open("config.py", "r") as f:
            config_lines = f.readlines()
            
        # Update values
        new_config_lines = []
        for line in config_lines:
            if line.strip().startswith("SYMBOLS ="):
                # Parse symbols from comma-separated string
                symbol_list = [s.strip() for s in symbols.split(",")]
                new_config_lines.append(f'SYMBOLS = {symbol_list}  \n')
            elif line.strip().startswith("USE_SANDBOX ="):
                new_config_lines.append(f'USE_SANDBOX = {sandbox_mode == "Enabled"}\n')
            elif line.strip().startswith("POSITION_SIZE ="):
                new_config_lines.append(f'POSITION_SIZE = {float(position_size) / 100}  # Percentage of account value per position\n')
            elif line.strip().startswith("STOP_LOSS_PERCENT ="):
                new_config_lines.append(f'STOP_LOSS_PERCENT = {float(stop_loss) / 100}  # Exit position if it loses this percentage\n')
            elif line.strip().startswith("TAKE_PROFIT_PERCENT ="):
                new_config_lines.append(f'TAKE_PROFIT_PERCENT = {float(take_profit) / 100}  # Exit position if it gains this percentage\n')
            elif line.strip().startswith("MIN_OPTION_DTE ="):
                new_config_lines.append(f'MIN_OPTION_DTE = {int(min_option_dte)}  # Minimum days to expiration\n')
            elif line.strip().startswith("MAX_OPTION_DTE ="):
                new_config_lines.append(f'MAX_OPTION_DTE = {int(max_option_dte)}  # Maximum days to expiration\n')
            elif line.strip().startswith("MAX_DAILY_TRADES ="):
                new_config_lines.append(f'MAX_DAILY_TRADES = {int(max_daily_trades)}  # Maximum number of trades per day\n')
            elif line.strip().startswith("CONFIDENCE_THRESHOLD ="):
                new_config_lines.append(f'CONFIDENCE_THRESHOLD = {float(confidence_threshold)}  # Minimum confidence to execute a trade\n')
            elif line.strip().startswith("ENABLE_OPPORTUNITY_FINDER ="):
                new_config_lines.append(f'ENABLE_OPPORTUNITY_FINDER = {enable_opportunity_finder == "Enabled"}  # Enable finding opportunities outside watchlist\n')
            else:
                new_config_lines.append(line)
                
        # Write updated config
        with open("config.py", "w") as f:
            f.writelines(new_config_lines)
            
        # Update global variables (ideally the bot would be restarted to pick these up)
        return "Configuration updated successfully. Please restart the bot to apply changes."
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return f"Error updating configuration: {e}"

def generate_price_chart(symbol, days=30):
    """Generate price chart for a symbol using Plotly."""
    try:
        if not symbol or symbol.strip() == "":
            # Return empty chart if no symbol provided
            fig = go.Figure()
            fig.update_layout(
                title="No Symbol Selected",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                template="plotly_white",
                annotations=[{
                    "text": "Please select a symbol to view price chart",
                    "showarrow": False,
                    "font": {"size": 20},
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5
                }]
            )
            return fig
            
        # Convert days to int to avoid type issues
        try:
            lookback_days = int(days)
        except (ValueError, TypeError):
            lookback_days = 30
            
        # Get price data
        price_data = market_data.get_latest_price_data(symbol, lookback_days=lookback_days)
        
        # Check if price_data is empty - Using explicit empty check to avoid ambiguity
        if isinstance(price_data, pd.DataFrame) and price_data.empty:
            # Return empty chart with message
            fig = go.Figure()
            fig.update_layout(
                title=f"No Data Available for {symbol}",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                template="plotly_white",
                annotations=[{
                    "text": f"No price data available for {symbol}",
                    "showarrow": False,
                    "font": {"size": 20},
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5
                }]
            )
            return fig
        
        # Convert to DataFrame if it's not already
        if not isinstance(price_data, pd.DataFrame):
            df = pd.DataFrame(price_data)
        else:
            df = price_data
            
        # Ensure date column exists and is properly formatted
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        
        # Create the figure
        fig = go.Figure()
        
        # Add price trace
        if 'close' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['close'], name='Price'))
            
            # Add moving averages if we have enough data
            if len(df) > 20:
                df['MA20'] = df['close'].rolling(window=20).mean()
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20-day MA', line=dict(dash='dash')))
                
            if len(df) > 50:
                df['MA50'] = df['close'].rolling(window=50).mean()
                fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], name='50-day MA', line=dict(dash='dot')))
        
        fig.update_layout(
            title=f'{symbol} Price Chart',
            xaxis_title='Date',
            yaxis_title='Price ($)',
            template='plotly_white',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        return fig
    except Exception as e:
        logger.error(f"Error generating price chart: {e}")
        # Return empty chart with error message
        fig = go.Figure()
        fig.update_layout(
            title="Error Generating Chart",
            xaxis_title="Date",
            yaxis_title="Price ($)",
            template="plotly_white",
            annotations=[{
                "text": f"Error: {str(e)}",
                "showarrow": False,
                "font": {"size": 16},
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5
            }]
        )
        return fig

def get_performance_chart():
    """Generate performance chart from trading log."""
    try:
        df = load_trading_log()
        if df.empty:
            return None
            
        # Make sure we have timestamp column
        if 'timestamp' not in df.columns:
            return None
            
        # Convert timestamp to datetime if it's not already
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sort by timestamp
        df = df.sort_values(by='timestamp')
        
        # Calculate cumulative P&L
        df['pl'] = 0.0
        
        for i, row in df.iterrows():
            if 'action' in df.columns and 'quantity' in df.columns and 'price' in df.columns:
                if row['action'] == 'buy' or row['action'] == 'buy_to_open':
                    df.at[i, 'pl'] = -float(row['quantity']) * float(row['price'])
                elif row['action'] == 'sell' or row['action'] == 'sell_to_close':
                    df.at[i, 'pl'] = float(row['quantity']) * float(row['price'])
        
        df['cumulative_pl'] = df['pl'].cumsum()
        
        # Create figure
        fig = px.line(
            df, 
            x='timestamp', 
            y='cumulative_pl',
            title='Cumulative Profit/Loss',
            labels={'timestamp': 'Date', 'cumulative_pl': 'Profit/Loss ($)'}
        )
        
        fig.update_layout(
            height=500,
            template='plotly_white'
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error generating performance chart: {e}")
        return None

def initialize_bot():
    """Initialize the trading bot components."""
    global tradier_client, trade_tracker
    
    try:
        logger.info("Initializing trading bot components...")
        tradier_client = TradierClient()
        trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
        return "Trading bot components initialized successfully."
    except Exception as e:
        logger.error(f"Error initializing trading bot: {e}")
        return f"Error initializing trading bot: {e}"

def start_bot():
    """Start the trading bot with scheduled tasks."""
    global bot_running, bot_thread
    
    if bot_running:
        return "Trading bot is already running."
    
    try:
        # Initialize components if not already done
        if tradier_client is None or trade_tracker is None:
            initialize_bot()
        
        # Define the bot thread function
        def bot_thread_func():
            logger.info("Trading bot started.")
            while bot_running:
                try:
                    # Check if market is open
                    if main.is_market_open():
                        logger.info("Market is open. Running scheduled tasks...")
                        
                        # Run morning analysis if it's morning
                        current_time = datetime.now().time()
                        if current_time.hour == 9 and current_time.minute >= 30 and current_time.minute < 45:
                            main.run_morning_analysis(tradier_client)
                        
                        # Run midday analysis around noon
                        if current_time.hour == 12 and current_time.minute >= 0 and current_time.minute < 15:
                            main.run_midday_analysis(tradier_client)
                        
                        # Run position management every 15 minutes
                        if current_time.minute % 15 == 0:
                            main.manage_positions(tradier_client)
                        
                        # Run opportunity finder hourly
                        if current_time.minute == 0:
                            main.find_trading_opportunities(tradier_client)
                    else:
                        logger.info("Market is closed. Skipping scheduled tasks.")
                    
                    # Sleep for 60 seconds before checking again
                    time.sleep(60)
                except Exception as e:
                    logger.error(f"Error in bot thread: {e}")
                    time.sleep(60)  # Sleep even on error to prevent tight loop
        
        # Start the bot thread
        bot_running = True
        bot_thread = threading.Thread(target=bot_thread_func)
        bot_thread.daemon = True
        bot_thread.start()
        
        return "Trading bot started successfully. Scheduled tasks will run during market hours."
    except Exception as e:
        bot_running = False
        logger.error(f"Error starting trading bot: {e}")
        return f"Error starting trading bot: {e}"

def stop_bot():
    """Stop the trading bot."""
    global bot_running, bot_thread
    
    if not bot_running:
        return "Trading bot is not running."
    
    try:
        bot_running = False
        if bot_thread:
            bot_thread.join(timeout=5)  # Wait for thread to terminate
        return "Trading bot stopped successfully."
    except Exception as e:
        logger.error(f"Error stopping trading bot: {e}")
        return f"Error stopping trading bot: {e}"

def run_morning_analysis():
    """Run morning analysis in a separate thread."""
    try:
        if tradier_client is None:
            return "Trading bot not initialized. Please start the bot first."
        
        # Run morning analysis in a separate thread
        future = executor.submit(main.run_morning_analysis, tradier_client)
        return "Morning analysis started. Check logs for details."
    except Exception as e:
        logger.error(f"Error running morning analysis: {e}")
        return f"Error running morning analysis: {e}"

def run_midday_analysis():
    """Run midday analysis in a separate thread."""
    try:
        if tradier_client is None:
            return "Trading bot not initialized. Please start the bot first."
        
        # Run midday analysis in a separate thread
        future = executor.submit(main.run_midday_analysis, tradier_client)
        return "Midday analysis started. Check logs for details."
    except Exception as e:
        logger.error(f"Error running midday analysis: {e}")
        return f"Error running midday analysis: {e}"

def run_manage_positions():
    """Run position management in a separate thread."""
    try:
        if tradier_client is None:
            return "Trading bot not initialized. Please start the bot first."
        
        # Run position management in a separate thread
        future = executor.submit(main.manage_positions, tradier_client)
        return "Position management started. Check logs for details."
    except Exception as e:
        logger.error(f"Error running position management: {e}")
        return f"Error running position management: {e}"

def run_opportunity_finder():
    """Run opportunity finder in a separate thread."""
    try:
        if tradier_client is None:
            return "Trading bot not initialized. Please start the bot first."
        
        # Run opportunity finder in a separate thread
        future = executor.submit(main.find_trading_opportunities, tradier_client)
        return "Opportunity finder started. Check logs for details."
    except Exception as e:
        logger.error(f"Error running opportunity finder: {e}")
        return f"Error running opportunity finder: {e}"

def analyze_symbol_sentiment(symbol):
    """Run sentiment analysis on a specific symbol."""
    try:
        # Fetch news and analyze
        news = fetch_news_summary(symbol)
        # Fix: Only pass the news parameter to analyze_with_deepseek
        # And properly unpack the tuple it returns (sentiment, reasoning, conclusion)
        sentiment, reasoning, conclusion = analyze_with_deepseek(news)
        return f"Symbol: {symbol}\nNews: {news}\nSentiment: {sentiment}\nReasoning: {reasoning}\nConclusion: {conclusion}"
    except Exception as e:
        logger.error(f"Error analyzing symbol sentiment: {e}")
        return f"Error analyzing {symbol}: {e}"

def execute_test_trade(symbol, action, quantity):
    """Execute a test trade in sandbox mode."""
    try:
        if not USE_SANDBOX:
            return "Test trades can only be executed in sandbox mode"
            
        if action not in ["buy", "sell"]:
            return "Invalid action. Must be 'buy' or 'sell'."
            
        quantity = int(quantity)
        if quantity <= 0:
            return "Quantity must be greater than 0"
            
        # For simplicity, we'll trade the underlying stock in sandbox mode
        if action == "buy":
            result = tradier_client.place_stock_order(
                symbol=symbol,
                side="buy",
                quantity=quantity,
                order_type="market",
                duration="day"
            )
        else:  # sell
            result = tradier_client.place_stock_order(
                symbol=symbol,
                side="sell",
                quantity=quantity,
                order_type="market",
                duration="day"
            )
            
        return f"Test trade submitted: {result}"
    except Exception as e:
        logger.error(f"Error executing test trade: {e}")
        return f"Error: {e}"

def refresh_dashboard():
    """Refresh all dashboard components."""
    try:
        account_summary = get_account_summary()
        positions = get_positions()
        day_trade_status = get_day_trade_status()
        reset_day_trades_result = None  # Initialize as None for refresh
        market_indicators = refresh_market_indicators()
        recent_activity = get_recent_trading_activity()
        bot_logs = get_latest_bot_logs()
        performance_chart = get_performance_chart()
        
        return [
            account_summary,
            positions,
            day_trade_status,
            reset_day_trades_result,
            market_indicators,
            recent_activity,
            bot_logs,
            performance_chart
        ]
    except Exception as e:
        logger.error(f"Error refreshing dashboard: {e}")
        return [
            {"error": "Error refreshing account summary"},
            pd.DataFrame(),
            {"error": "Error refreshing day trade status"},
            None,
            pd.DataFrame(),
            pd.DataFrame(),
            "Error refreshing logs",
            None
        ]

def create_gradio_interface():
    """Create and return the Gradio interface."""
    with gr.Blocks(title="Forward Profit Trading Bot", theme=gr.themes.Soft()) as interface:
        gr.Markdown("# Forward Profit Trading Bot Interface")
        
        with gr.Tab("Dashboard"):
            # Top row - Account info, positions, and day trade status
            with gr.Row(equal_height=False):
                # Left column - Account summary and day trade status
                with gr.Column(scale=1):
                    with gr.Box():
                        gr.Markdown("### Account Summary")
                        account_summary = gr.JSON(label="Account Information")
                    
                    with gr.Box():
                        gr.Markdown("### Day Trade Status")
                        with gr.Row():
                            with gr.Column(scale=3):
                                day_trade_status = gr.JSON(label="Day Trade Tracker")
                            with gr.Column(scale=1):
                                reset_day_trades_btn = gr.Button("Reset", variant="secondary", size="sm")
                                reset_day_trades_result = gr.JSON(label="Reset Result", visible=False)
                    
                    with gr.Box():
                        gr.Markdown("### Recent Trading Activity")
                        recent_activity = gr.DataFrame(
                            value=pd.DataFrame(columns=["Date", "Symbol", "Action", "Quantity", "Price", "P&L"]),
                            label="Recent Trades",
                            height=250
                        )
                
                # Right column - Positions table (larger)
                with gr.Column(scale=2):
                    with gr.Box():
                        gr.Markdown("### Current Positions")
                        positions_table = gr.DataFrame(
                            value=pd.DataFrame(columns=["Symbol", "Quantity", "Cost Basis", "Current Price", "Current Value", "P&L", "P&L %", "Date Acquired"]),
                            label="Open Positions",
                            height=300
                        )
                    
                    with gr.Box():
                        gr.Markdown("### Market Indicators")
                        market_indicators = gr.DataFrame(
                            value=pd.DataFrame(columns=["Symbol", "Price", "RSI", "MACD", "Signal", "MA20", "MA50", "Trend"]),
                            label="Technical Indicators",
                            height=250
                        )
            
            # Bottom row - Performance chart and logs side by side
            with gr.Row(equal_height=True):
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Performance")
                        performance_chart = gr.Plot(label="Cumulative P&L", height=300)
                
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Bot Logs")
                        bot_logs = gr.Textbox(label="Recent Log Entries", lines=10, max_lines=15)
            
            # Refresh button at the bottom
            with gr.Row():
                refresh_btn = gr.Button("Refresh Dashboard", variant="primary", size="lg")
            
            # Connect refresh button
            refresh_btn.click(
                fn=refresh_dashboard,
                inputs=[],
                outputs=[account_summary, positions_table, day_trade_status, 
                         reset_day_trades_result, market_indicators, recent_activity, bot_logs, performance_chart]
            )
            
            # Connect reset day trades button
            reset_day_trades_btn.click(
                fn=reset_day_trades,
                inputs=[],
                outputs=[reset_day_trades_result, day_trade_status]
            )
        
        with gr.Tab("Bot Control"):
            with gr.Row():
                # Bot status and control
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Bot Status and Control")
                        with gr.Row():
                            start_bot_btn = gr.Button("Start Trading Bot", variant="primary", size="lg")
                            stop_bot_btn = gr.Button("Stop Trading Bot", variant="stop", size="lg")
                        init_bot_btn = gr.Button("Initialize Bot Components", variant="secondary")
                        bot_status = gr.Textbox(label="Bot Status", lines=2)
                
                # Manual controls
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Manual Controls")
                        with gr.Row():
                            morning_analysis_btn = gr.Button("Run Morning Analysis", size="sm")
                            midday_analysis_btn = gr.Button("Run Midday Analysis", size="sm")
                        with gr.Row():
                            manage_positions_btn = gr.Button("Run Position Management", size="sm")
                            opportunity_finder_btn = gr.Button("Run Opportunity Finder", size="sm")
                        manual_result = gr.Textbox(label="Action Result", lines=2)
            
            # Connect buttons
            start_bot_btn.click(fn=start_bot, inputs=[], outputs=[bot_status])
            stop_bot_btn.click(fn=stop_bot, inputs=[], outputs=[bot_status])
            init_bot_btn.click(fn=initialize_bot, inputs=[], outputs=[bot_status])
            morning_analysis_btn.click(fn=run_morning_analysis, inputs=[], outputs=[manual_result])
            midday_analysis_btn.click(fn=run_midday_analysis, inputs=[], outputs=[manual_result])
            manage_positions_btn.click(fn=run_manage_positions, inputs=[], outputs=[manual_result])
            opportunity_finder_btn.click(fn=run_opportunity_finder, inputs=[], outputs=[manual_result])
        
        with gr.Tab("Configuration"):
            with gr.Row():
                # Trading configuration
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Trading Configuration")
                        symbols_input = gr.Textbox(label="Watchlist Symbols (comma-separated)")
                        with gr.Row():
                            with gr.Column():
                                sandbox_toggle = gr.Checkbox(label="Use Sandbox Mode")
                                opportunity_toggle = gr.Checkbox(label="Enable Opportunity Finder")
                            with gr.Column():
                                max_trades_slider = gr.Slider(minimum=1, maximum=10, step=1, label="Maximum Daily Trades")
                                confidence_slider = gr.Slider(minimum=0.5, maximum=1.0, step=0.05, label="Confidence Threshold")
                        position_size_slider = gr.Slider(minimum=100, maximum=10000, step=100, label="Position Size ($)")
                        with gr.Row():
                            with gr.Column():
                                stop_loss_slider = gr.Slider(minimum=5, maximum=50, step=1, label="Stop Loss (%)")
                            with gr.Column():
                                take_profit_slider = gr.Slider(minimum=5, maximum=100, step=1, label="Take Profit (%)")
                
                # Option parameters
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Option Parameters")
                        with gr.Row():
                            with gr.Column():
                                min_dte_slider = gr.Slider(minimum=1, maximum=60, step=1, label="Minimum Days to Expiration")
                            with gr.Column():
                                max_dte_slider = gr.Slider(minimum=7, maximum=120, step=1, label="Maximum Days to Expiration")
                        
                        # Update and results
                        update_config_btn = gr.Button("Update Configuration", variant="primary", size="lg")
                        config_result = gr.Textbox(label="Configuration Update Result", lines=2)
            
            # Load current config values
            config_values = get_config_values()
            symbols_input.value = config_values.get("Symbols", "")
            sandbox_toggle.value = config_values.get("Sandbox Mode", True) == "Enabled"
            position_size_slider.value = config_values.get("Position Size", "1000")
            position_size_slider.value = float(position_size_slider.value.replace("%", "")) * 100
            stop_loss_slider.value = config_values.get("Stop Loss", "25")
            stop_loss_slider.value = float(stop_loss_slider.value.replace("%", ""))
            take_profit_slider.value = config_values.get("Take Profit", "50")
            take_profit_slider.value = float(take_profit_slider.value.replace("%", ""))
            min_dte_slider.value = config_values.get("Min Option DTE", 7)
            max_dte_slider.value = config_values.get("Max Option DTE", 45)
            max_trades_slider.value = config_values.get("Max Daily Trades", 3)
            confidence_slider.value = config_values.get("Confidence Threshold", 0.7)
            opportunity_toggle.value = config_values.get("Opportunity Finder", True) == "Enabled"
            
            # Connect update button
            update_config_btn.click(
                fn=update_config,
                inputs=[
                    symbols_input, sandbox_toggle, position_size_slider, 
                    stop_loss_slider, take_profit_slider, min_dte_slider, 
                    max_dte_slider, max_trades_slider, confidence_slider, 
                    opportunity_toggle
                ],
                outputs=[config_result]
            )
        
        with gr.Tab("Market Analysis"):
            with gr.Row():
                # Price chart section
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Price Charts")
                        with gr.Row():
                            with gr.Column(scale=2):
                                symbol_dropdown = gr.Dropdown(choices=SYMBOLS, label="Select Symbol", value=None)
                            with gr.Column(scale=1):
                                days_slider = gr.Slider(minimum=7, maximum=180, step=1, value=30, label="Days")
                        chart_btn = gr.Button("Generate Chart", variant="primary")
                        
                        # Initialize with empty chart
                        empty_fig = go.Figure()
                        empty_fig.update_layout(
                            title="Select a Symbol and Click Generate Chart",
                            xaxis_title="Date",
                            yaxis_title="Price ($)",
                            template="plotly_white",
                            height=500,
                            annotations=[{
                                "text": "No data to display yet",
                                "showarrow": False,
                                "font": {"size": 20},
                                "xref": "paper",
                                "yref": "paper",
                                "x": 0.5,
                                "y": 0.5
                            }]
                        )
                        price_chart = gr.Plot(value=empty_fig, label="Price Chart")
                
                # Sentiment analysis section
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Sentiment Analysis")
                        sentiment_symbol = gr.Dropdown(choices=SYMBOLS, label="Select Symbol for Sentiment Analysis", value=None)
                        sentiment_btn = gr.Button("Analyze Sentiment", variant="primary")
                        sentiment_result = gr.Textbox(label="Sentiment Analysis Result", lines=15, max_lines=20)
            
            # Connect buttons
            chart_btn.click(
                fn=generate_price_chart,
                inputs=[symbol_dropdown, days_slider],
                outputs=[price_chart]
            )
            
            sentiment_btn.click(
                fn=analyze_symbol_sentiment,
                inputs=[sentiment_symbol],
                outputs=[sentiment_result]
            )
        
        with gr.Tab("Test Trading"):
            with gr.Row():
                with gr.Column():
                    with gr.Box():
                        gr.Markdown("### Execute Test Trade (Sandbox Mode Only)")
                        with gr.Row():
                            with gr.Column():
                                test_symbol = gr.Dropdown(choices=SYMBOLS, label="Select Symbol", value=None)
                                test_action = gr.Radio(choices=["buy", "sell"], label="Action", value="buy")
                            with gr.Column():
                                test_quantity = gr.Slider(minimum=1, maximum=10, step=1, value=1, label="Quantity")
                                test_trade_btn = gr.Button("Execute Test Trade", variant="primary")
                        test_result = gr.Textbox(label="Test Trade Result", lines=5)
            
            # Connect button
            test_trade_btn.click(
                fn=execute_test_trade,
                inputs=[test_symbol, test_action, test_quantity],
                outputs=[test_result]
            )
        
        # Initialize the interface with data
        interface.load(
            fn=refresh_dashboard,
            inputs=[],
            outputs=[account_summary, positions_table, day_trade_status, 
                     reset_day_trades_result, market_indicators, recent_activity, bot_logs, performance_chart]
        )
    
    return interface

if __name__ == "__main__":
    # Create and launch the interface
    app = create_gradio_interface()
    app.launch(server_name="0.0.0.0", share=True)
