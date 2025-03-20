import os
import sys
import time
import json
import random
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# main.py – Orchestrate scheduling and run the trading bot
__version__ = "2.1.4"  # Match your actual version  
import time
import schedule
from datetime import datetime, time as dt_time
import pytz
import calendar
import os
import logging

# Add a try-except block to handle NumPy compatibility issues
try:
    # Try to import pandas and numpy-dependent modules
    from ai_analysis import fetch_news_summary, spot_check_news, analyze_with_deepseek
    from strategy import decide_trade, compute_technicals, select_option_contract, evaluate_position
    from market_data import get_latest_price_data, get_option_quote
    from opportunity_finder import identify_opportunities, process_opportunities
except ImportError as e:
    # Log the error but continue with reduced functionality
    print(f"Warning: Some modules could not be imported due to NumPy compatibility issues: {e}")
    print("The bot will run with reduced functionality.")
    # Define empty placeholder functions for the ones that couldn't be imported
    def fetch_news_summary(*args, **kwargs): return "News summary unavailable due to import error"
    def spot_check_news(*args, **kwargs): return "News check unavailable due to import error"
    def analyze_with_deepseek(*args, **kwargs): return "AI analysis unavailable due to import error"
    def decide_trade(*args, **kwargs): return "HOLD", "Trading decisions unavailable due to import error"
    def compute_technicals(*args, **kwargs): return {}
    def select_option_contract(*args, **kwargs): return None
    def evaluate_position(*args, **kwargs): return "HOLD", "Position evaluation unavailable due to import error"
    def get_latest_price_data(*args, **kwargs): return None
    def get_option_quote(*args, **kwargs): return {}
    def identify_opportunities(*args, **kwargs): return []
    def process_opportunities(*args, **kwargs): return []

from execution import TradierClient
# from report import compose_report, send_email_report, log_trade  # Temporarily disabled
from config import ACCOUNT_ID, SYMBOLS, MIN_OPTION_DTE, MAX_OPTION_DTE, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, TRADIER_BASE_URL, USE_SANDBOX, MAX_DAILY_TRADES
from bot_logger import clear_logs as bot_clear_logs
from trade_tracker import TradeTracker
from report import log_trade

# Initialize clients
tradier = TradierClient()

# Market hours constants (Eastern Time)
MARKET_OPEN_TIME = dt_time(9, 30)  # 9:30 AM ET
MARKET_CLOSE_TIME = dt_time(16, 0)  # 4:00 PM ET
EASTERN_TZ = pytz.timezone('US/Eastern')

# Log file paths
TRADING_BOT_LOG = 'trading_bot.log'
TEST_ORDER_LOG = 'test_order.log'
LOG_MAX_SIZE_MB = 10  # Maximum log size in MB before archiving

def setup_logging():
    """
    Set up logging configuration and clear old logs
    """
    # Clear logs at the start of each run
    bot_clear_logs()
    
    # Configure logging
    logging.basicConfig(
        filename=TRADING_BOT_LOG,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='a'  # Append mode
    )
    
    # Add console handler to show logs in console as well
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    
    logging.info("=== Trading Bot Started ===")
    logging.info(f"Monitoring symbols: {', '.join(SYMBOLS)}")

def clear_logs(max_size_mb=LOG_MAX_SIZE_MB):
    """
    Clear or archive logs if they exceed the maximum size
    
    Args:
        max_size_mb (int): Maximum log size in MB before archiving
    """
    log_files = [TRADING_BOT_LOG, TEST_ORDER_LOG]
    
    for log_file in log_files:
        if not os.path.exists(log_file):
            continue
            
        # Get file size in MB
        file_size_mb = os.path.getsize(log_file) / (1024 * 1024)
        
        if file_size_mb > max_size_mb:
            # Create archive directory if it doesn't exist
            archive_dir = 'log_archives'
            if not os.path.exists(archive_dir):
                os.makedirs(archive_dir)
                
            # Archive the log file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_path = os.path.join(archive_dir, f"{os.path.splitext(log_file)[0]}_{timestamp}.log")
            
            try:
                # Copy to archive
                with open(log_file, 'r') as src, open(archive_path, 'w') as dst:
                    dst.write(src.read())
                    
                # Clear the original log file
                with open(log_file, 'w') as f:
                    f.write(f"Log cleared and archived to {archive_path} at {datetime.now()}\n")
                    
                logging.info(f"Log file {log_file} archived to {archive_path}")
                print(f"Log file {log_file} archived to {archive_path}")
            except Exception as e:
                logging.error(f"Error archiving log file {log_file}: {e}")
                print(f"Error archiving log file {log_file}: {e}")

def is_market_open():
    """
    Check if the market is currently open
    
    Returns:
        bool: True if market is open, False otherwise
    """
    # Get current time in Eastern timezone
    now = datetime.now(EASTERN_TZ)
    current_time = now.time()
    
    # Check if it's a weekday (Monday = 0, Sunday = 6)
    is_weekday = now.weekday() < 5  # Monday-Friday
    
    # Check if current time is within market hours
    is_market_hours = MARKET_OPEN_TIME <= current_time <= MARKET_CLOSE_TIME
    
    return is_weekday and is_market_hours

def is_trading_day():
    """
    Check if today is a trading day (weekday)
    
    Returns:
        bool: True if today is a trading day, False otherwise
    """
    now = datetime.now(EASTERN_TZ)
    return now.weekday() < 5  # Monday-Friday

def manage_positions(tradier_client, market_sentiment=None, market_reasoning=None):
    """
    Check all open positions and make intelligent selling decisions
    
    Args:
        tradier_client: TradierClient instance for API access
        market_sentiment (str, optional): Overall market sentiment (bullish/bearish/neutral)
        market_reasoning (str, optional): Reasoning behind market sentiment
        
    Returns:
        list: List of positions that were closed
    """
    logger = logging.getLogger()
    logger.info("Checking open positions...")
    
    # Get trade tracker
    trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
    
    # Get current positions from Tradier
    positions = tradier_client.get_account_positions()
    
    # If no positions, return empty list
    if not positions:
        logger.info("No open positions to manage")
        return []
    
    # Make sure positions is a list
    if not isinstance(positions, list):
        positions = [positions]
    
    # Track positions that were closed
    closed_positions = []
    
    # Process each position
    for position in positions:
        symbol = position.get('symbol', '')
        quantity = float(position.get('quantity', 0))
        cost_basis = float(position.get('cost_basis', 0))
        
        # Skip if not an option position
        # Tradier option symbols follow format like: XLI250321P00064000
        # They contain a date (25MMDD) followed by P or C and then strike price
        if not (len(symbol) >= 15 and ('P' in symbol[-9:] or 'C' in symbol[-9:]) and any(c.isdigit() for c in symbol)):
            logger.info(f"Skipping non-option position: {symbol}")
            continue
        
        # If position is not in trade tracker, add it
        if symbol not in trade_tracker.trades:
            logger.warning(f"Position {symbol} found in account but not in trade tracker. Adding it now.")
            # Extract option data from the symbol
            try:
                # Parse the option symbol to get underlying, expiration, etc.
                # Format is typically: AAPL250321C00150000 (AAPL 2025-03-21 Call $150.00)
                underlying_symbol = symbol[:symbol.find('2')]  # Extract underlying symbol
                year = int('20' + symbol[symbol.find('2')+1:symbol.find('2')+3])
                month = int(symbol[symbol.find('2')+3:symbol.find('2')+5])
                day = int(symbol[symbol.find('2')+5:symbol.find('2')+7])
                is_call = 'C' in symbol[-9:]
                strike_price = float(symbol[-8:]) / 1000.0
                
                option_data = {
                    'underlying_symbol': underlying_symbol,
                    'expiration': f"{year}-{month:02d}-{day:02d}",
                    'is_call': is_call,
                    'strike_price': strike_price,
                    'option_symbol': symbol
                }
                
                # Add to trade tracker with option data
                trade_tracker.add_position(symbol, quantity, option_data=option_data)
            except Exception as e:
                logger.error(f"Error parsing option symbol {symbol}: {e}")
                # Add to trade tracker without option data
                trade_tracker.add_position(symbol, quantity)
        
        logger.info(f"Evaluating position: {symbol}, Quantity: {quantity}, Cost basis: ${cost_basis}")
        
        # Get current option quote
        try:
            option_quote = get_option_quote(symbol)
            
            if not option_quote:
                logger.warning(f"Could not get quote for {symbol}, skipping position evaluation")
                continue
            
            # Get current price - use bid price if last price is not available
            current_price = option_quote.get('last')
            if current_price is None:
                # If last price is not available, use the midpoint of bid and ask
                bid = option_quote.get('bid', 0)
                ask = option_quote.get('ask', 0)
                if ask > 0 and bid > 0:
                    current_price = (bid + ask) / 2
                    logger.info(f"Using bid-ask midpoint for {symbol}: ${current_price} (bid: ${bid}, ask: ${ask})")
                else:
                    # If bid and ask are not available or zero, use bid as fallback
                    current_price = bid
                    logger.info(f"Using bid price for {symbol}: ${current_price}")
            
            # Calculate profit/loss
            if cost_basis > 0 and current_price is not None:
                pnl_percent = (current_price - cost_basis) / cost_basis
            else:
                pnl_percent = 0
                
            logger.info(f"Current price: ${current_price}, P&L: {pnl_percent:.2%}")
        except Exception as e:
            logger.error(f"Error getting option quote for {symbol}: {e}")
            continue
        
        # Extract underlying symbol from option symbol
        underlying_symbol = ""
        for char in symbol:
            if not char.isdigit():
                underlying_symbol += char
            else:
                break
        
        # Get price data for the underlying
        try:
            price_data = get_latest_price_data(underlying_symbol)
            
            # Check if price_data is None or empty
            if price_data is None or (hasattr(price_data, 'empty') and price_data.empty):
                logger.warning(f"No price data available for {underlying_symbol}, using basic exit rules")
                
                # Basic exit rules if no price data is available
                if pnl_percent <= -STOP_LOSS_PERCENT:
                    logger.info(f"Stop loss triggered for {symbol}: {pnl_percent:.2%} loss")
                    sell_decision = "SELL"
                    reasoning = f"Stop loss triggered at {pnl_percent:.2%} loss"
                elif pnl_percent >= TAKE_PROFIT_PERCENT:
                    logger.info(f"Take profit triggered for {symbol}: {pnl_percent:.2%} gain")
                    sell_decision = "SELL"
                    reasoning = f"Take profit triggered at {pnl_percent:.2%} gain"
                else:
                    sell_decision = "HOLD"
                    reasoning = "Holding position, no technical data available"
            else:
                # Calculate technical indicators
                try:
                    technicals = compute_technicals(price_data)
                    
                    # Determine if this is a call or put option
                    is_call = 'C' in symbol
                    
                    # Make intelligent selling decision using the evaluate_position function
                    sell_decision, reasoning = evaluate_position(
                        symbol=symbol,
                        underlying_symbol=underlying_symbol,
                        is_call=is_call,
                        price_data=price_data,
                        technicals=technicals,
                        pnl_percent=pnl_percent,
                        market_sentiment=market_sentiment,
                        days_held=position.get('days_held', 0)
                    )
                except Exception as e:
                    logger.error(f"Error calculating technicals for {underlying_symbol}: {e}")
                    # Fall back to basic exit rules
                    if pnl_percent <= -STOP_LOSS_PERCENT:
                        sell_decision = "SELL"
                        reasoning = f"Stop loss triggered at {pnl_percent:.2%} loss (error calculating technicals)"
                    elif pnl_percent >= TAKE_PROFIT_PERCENT:
                        sell_decision = "SELL"
                        reasoning = f"Take profit triggered at {pnl_percent:.2%} gain (error calculating technicals)"
                    else:
                        sell_decision = "HOLD"
                        reasoning = "Holding position, error calculating technicals"
            
            logger.info(f"Position evaluation for {symbol}: {sell_decision} - {reasoning}")
        except Exception as e:
            logger.error(f"Error evaluating position for {symbol}: {e}")
            # Skip this position if there's an error
            continue
        
        # Execute sell order if decision is to sell
        if sell_decision == "SELL":
            logger.info(f"Executing sell order for {symbol}")
            
            # Get option data from trade tracker if available
            option_data = None
            if symbol in trade_tracker.trades and 'option_data' in trade_tracker.trades[symbol]:
                option_data = trade_tracker.trades[symbol]['option_data']
                logger.info(f"Using stored option data for {symbol}: {option_data}")
            
            try:
                # Place the sell order
                order_result = tradier_client.place_option_order(
                    symbol=symbol,
                    side='sell_to_close',
                    quantity=quantity,
                    price=None,  # Market order
                    duration='day'
                )
                
                # Log the trade
                try:
                    log_trade({
                        'symbol': symbol,
                        'action': "SELL",
                        'quantity': quantity,
                        'price': None,  # We don't know the price yet
                        'reasoning': reasoning,
                        'order_id': order_result.get('id') if order_result else None
                    })
                except Exception as e:
                    logger.error(f"Error logging trade: {e}")
                
                # Record the closed position
                trade_tracker.close_position(symbol, quantity)
                
                closed_positions.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'pnl_percent': pnl_percent,
                    'reasoning': reasoning
                })
            except Exception as e:
                logger.error(f"Error executing sell order for {symbol}: {e}")
    
    # Return the list of closed positions
    return closed_positions

def morning_analysis():
    """Run morning analysis and execute trades"""
    if not is_market_open():
        print(f"\n=== Skipping Morning Analysis: Market closed ===")
        return
        
    print(f"\n=== Morning Analysis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    # Get morning news
    news = fetch_news_summary(time_of_day='morning')
    sentiment, reasoning, conclusion = analyze_with_deepseek(news)
    
    print(f"Morning market sentiment: {sentiment}")
    print(f"AI conclusion: {conclusion[:200]}...\n")
    
    # First, manage existing positions with the morning sentiment
    closed_positions = manage_positions(tradier, sentiment, reasoning)
    if closed_positions:
        print(f"Closed {len(closed_positions)} positions during morning position check")
    
    # Process each symbol in our watchlist
    for symbol in SYMBOLS:
        print(f"\nAnalyzing {symbol}...")
        # Get price data
        prices = get_latest_price_data(symbol)
        if prices.empty:
            print(f"No price data available for {symbol}, skipping")
            continue
            
        # Compute technical indicators
        technicals = compute_technicals(prices)
        
        # Make trading decision
        signal = decide_trade(sentiment, reasoning, technicals, symbol, prices)
        
        # If we have a trading signal, select an option contract and execute
        if signal:
            print(f"Signal for {symbol}: {signal}")
            
            # Vary the expiration days for different trades
            # Use a range between MIN_OPTION_DTE and MAX_OPTION_DTE from config
            import random
            
            # Generate a random expiration days value within the configured range
            expiration_days = random.randint(MIN_OPTION_DTE, MAX_OPTION_DTE)
            print(f"Selected expiration days: {expiration_days}")
            
            contract = select_option_contract(symbol, signal, prices, expiration_days=expiration_days)
            
            if contract:
                try:
                    # Execute the trade
                    order_result = tradier.place_option_order(
                        symbol=contract,
                        side='buy_to_open',
                        quantity=1,
                        price=None,
                        duration='day'
                    )
                    
                    # Add position to trade tracker with option data
                    if order_result and 'id' in order_result:
                        try:
                            # Parse the option symbol to get underlying, expiration, etc.
                            # Format is typically: AAPL250321C00150000 (AAPL 2025-03-21 Call $150.00)
                            underlying_symbol = symbol  # We already know the underlying
                            option_symbol = contract
                            is_call = 'C' in option_symbol[-9:]
                            year = int('20' + option_symbol[option_symbol.find('2')+1:option_symbol.find('2')+3])
                            month = int(option_symbol[option_symbol.find('2')+3:option_symbol.find('2')+5])
                            day = int(option_symbol[option_symbol.find('2')+5:option_symbol.find('2')+7])
                            strike_price = float(option_symbol[-8:]) / 1000.0
                            
                            option_data = {
                                'underlying_symbol': underlying_symbol,
                                'expiration': f"{year}-{month:02d}-{day:02d}",
                                'is_call': is_call,
                                'strike_price': strike_price,
                                'option_symbol': option_symbol,
                                'order_id': order_result.get('id')
                            }
                            
                            # Add to trade tracker with option data
                            trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
                            trade_tracker.add_position(option_symbol, 1, option_data=option_data)
                            print(f"Added position to trade tracker: {option_symbol}")
                        except Exception as e:
                            print(f"Error adding position to trade tracker: {e}")
                    
                    # Log the trade
                    try:
                        log_trade({
                            'symbol': symbol,
                            'action': "BUY",
                            'quantity': 1,
                            'price': None,  # We don't know the price yet
                            'reasoning': signal,
                            'order_id': order_result.get('id') if order_result else None
                        })
                    except Exception as e:
                        # If log_trade fails, just log the error but don't let it stop the process
                        print(f"Error logging trade: {e}")
                    
                    print(f"Order placed for {contract}: {order_result}")
                except Exception as e:
                    print(f"Error placing order: {e}")
            else:
                print(f"Could not find suitable option contract for {symbol}")
    
    # Find additional opportunities outside watchlist
    print("\nSearching for additional trading opportunities...")
    opportunities = identify_opportunities(market_news=news)
    
    if opportunities:
        print(f"Found {len(opportunities)} additional trading opportunities")
        executed_trades = process_opportunities(opportunities, tradier)
        print(f"Executed {len(executed_trades)} trades for opportunities outside watchlist")
    else:
        print("No additional trading opportunities identified")

def midday_analysis():
    """Run midday analysis to check for changing market conditions"""
    if not is_market_open():
        print(f"\n=== Skipping Midday Analysis: Market closed ===")
        return
        
    print(f"\n=== Midday Analysis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    # Get updated news
    news = fetch_news_summary(time_of_day='midday')
    sentiment, reasoning, conclusion = analyze_with_deepseek(news)
    
    print(f"Midday market sentiment: {sentiment}")
    print(f"AI conclusion: {conclusion[:200]}...\n")
    
    # First, manage existing positions with the midday sentiment
    closed_positions = manage_positions(tradier, sentiment, reasoning)
    if closed_positions:
        print(f"Closed {len(closed_positions)} positions during midday position check")
    
    # Process each symbol in our watchlist
    for symbol in SYMBOLS:
        print(f"\nMidday check for {symbol}...")
        # Get price data
        prices = get_latest_price_data(symbol)
        if prices.empty:
            print(f"No price data available for {symbol}, skipping")
            continue
            
        # Compute technical indicators
        technicals = compute_technicals(prices)
        
        # Make trading decision
        signal = decide_trade(sentiment, reasoning, technicals, symbol, prices)
        
        # If we have a trading signal, select an option contract and execute
        if signal:
            print(f"Midday signal for {symbol}: {signal}")
            
            # Vary the expiration days for different trades
            # Use a range between MIN_OPTION_DTE and MAX_OPTION_DTE from config
            import random
            
            # Generate a random expiration days value within the configured range
            expiration_days = random.randint(MIN_OPTION_DTE, MAX_OPTION_DTE)
            print(f"Selected expiration days: {expiration_days}")
            
            contract = select_option_contract(symbol, signal, prices, expiration_days=expiration_days)
            
            if contract:
                try:
                    # Execute the trade
                    order_result = tradier.place_option_order(
                        symbol=contract,
                        side='buy_to_open',
                        quantity=1,
                        price=None,
                        duration='day'
                    )
                    
                    # Add position to trade tracker with option data
                    if order_result and 'id' in order_result:
                        try:
                            # Parse the option symbol to get underlying, expiration, etc.
                            # Format is typically: AAPL250321C00150000 (AAPL 2025-03-21 Call $150.00)
                            underlying_symbol = symbol  # We already know the underlying
                            option_symbol = contract
                            is_call = 'C' in option_symbol[-9:]
                            year = int('20' + option_symbol[option_symbol.find('2')+1:option_symbol.find('2')+3])
                            month = int(option_symbol[option_symbol.find('2')+3:option_symbol.find('2')+5])
                            day = int(option_symbol[option_symbol.find('2')+5:option_symbol.find('2')+7])
                            strike_price = float(option_symbol[-8:]) / 1000.0
                            
                            option_data = {
                                'underlying_symbol': underlying_symbol,
                                'expiration': f"{year}-{month:02d}-{day:02d}",
                                'is_call': is_call,
                                'strike_price': strike_price,
                                'option_symbol': option_symbol,
                                'order_id': order_result.get('id')
                            }
                            
                            # Add to trade tracker with option data
                            trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
                            trade_tracker.add_position(option_symbol, 1, option_data=option_data)
                            print(f"Added position to trade tracker: {option_symbol}")
                        except Exception as e:
                            print(f"Error adding position to trade tracker: {e}")
                    
                    # Log the trade
                    try:
                        log_trade({
                            'symbol': symbol,
                            'action': "BUY",
                            'quantity': 1,
                            'price': None,  # We don't know the price yet
                            'reasoning': signal,
                            'order_id': order_result.get('id') if order_result else None
                        })
                    except Exception as e:
                        # If log_trade fails, just log the error but don't let it stop the process
                        print(f"Error logging trade: {e}")
                    
                    print(f"Midday order placed for {contract}: {order_result}")
                except Exception as e:
                    print(f"Error placing midday order: {e}")
            else:
                print(f"Could not find suitable option contract for {symbol}")
    
    # Find additional opportunities outside watchlist
    print("\nSearching for additional midday trading opportunities...")
    opportunities = identify_opportunities(market_news=news)
    
    if opportunities:
        print(f"Found {len(opportunities)} additional midday trading opportunities")
        executed_trades = process_opportunities(opportunities, tradier)
        print(f"Executed {len(executed_trades)} trades for opportunities outside watchlist")
    else:
        print("No additional midday trading opportunities identified")

def random_check():
    """Perform a spot check for major market updates"""
    if not is_market_open():
        print(f"\n=== Skipping Random Check: Market closed ===")
        return
        
    print(f"\n=== Random Check ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    # Check for major news that might impact our positions
    query = f"Breaking financial news and market updates for {datetime.now().strftime('%Y-%m-%d')}"
    news_update = spot_check_news(query)
    
    # Analyze the news update
    sentiment, reasoning, conclusion = analyze_with_deepseek(news_update)
    
    print(f"Spot check sentiment: {sentiment}")
    print(f"AI conclusion: {conclusion[:200]}...\n")
    
    # Check if we should manage positions based on the news
    if sentiment in ['bullish', 'bearish']:
        print(f"Significant market update detected ({sentiment}), checking positions...")
        closed_positions = manage_positions(tradier, sentiment, reasoning)
        if closed_positions:
            print(f"Closed {len(closed_positions)} positions due to significant market update")
    else:
        print("No significant market changes detected, continuing normal operations")

def find_trading_opportunities(tradier_client):
    """
    Find and evaluate potential trading opportunities
    
    Args:
        tradier_client: TradierClient instance for API access
        
    Returns:
        list: List of trading opportunities found
    """
    logger = logging.getLogger()
    logger.info("Searching for trading opportunities...")
    
    try:
        # Get trade tracker
        trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
        
        # Check if we've reached our day trade limit
        day_trade_count = trade_tracker.get_day_trade_count()
        if day_trade_count >= MAX_DAILY_TRADES:
            logger.warning(f"Day trade limit reached ({day_trade_count}/{MAX_DAILY_TRADES}), not opening new positions")
            return []
        
        # Try to identify opportunities
        try:
            opportunities = identify_opportunities(SYMBOLS)
            if not opportunities:
                logger.info("No trading opportunities found")
                return []
                
            logger.info(f"Found {len(opportunities)} potential trading opportunities")
            
            # Process opportunities
            executed_trades = process_opportunities(opportunities, tradier_client)
            
            if executed_trades:
                logger.info(f"Executed {len(executed_trades)} trades")
                return executed_trades
            else:
                logger.info("No trades executed")
                return []
                
        except NameError as e:
            # This will happen if the opportunity_finder module couldn't be imported due to NumPy issues
            logger.warning(f"Could not find trading opportunities: {e}")
            logger.warning("This feature is disabled due to NumPy compatibility issues")
            return []
        except Exception as e:
            logger.error(f"Error finding trading opportunities: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Error in find_trading_opportunities: {e}")
        return []

def end_of_day_report(tradier_client):
    """
    Generate end of day report with performance metrics
    
    Args:
        tradier_client: TradierClient instance for API access
    """
    logger = logging.getLogger()
    logger.info("Generating end of day report...")
    
    try:
        # Get account balances
        balances = tradier_client.get_account_balances()
        
        if not balances:
            logger.warning("Could not retrieve account balances for end of day report")
            return
            
        # Get current positions
        positions = tradier_client.get_account_positions()
        
        # Get trade tracker for day trade information
        trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
        
        # Log account summary
        total_equity = balances.get('total_equity', 'Unknown')
        option_buying_power = balances.get('option_buying_power', 'Unknown')
        
        logger.info("=== END OF DAY REPORT ===")
        logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        logger.info(f"Account Value: ${total_equity}")
        logger.info(f"Option Buying Power: ${option_buying_power}")
        
        # Log current positions
        logger.info(f"Open Positions: {len(positions)}")
        for position in positions:
            symbol = position.get('symbol', 'Unknown')
            quantity = position.get('quantity', 0)
            cost_basis = position.get('cost_basis', 0)
            
            logger.info(f"  {symbol}: {quantity} contracts, Cost Basis: ${cost_basis}")
        
        # Log day trades
        day_trades = trade_tracker.get_day_trade_count()
        logger.info(f"Day Trades Used: {day_trades}/{MAX_DAILY_TRADES}")
        
        # Log trading activity for the day
        # This would require tracking trades made today, which we don't have yet
        # We'll just log a placeholder for now
        logger.info("Trading Activity: Report not available")
        
        logger.info("=== END OF REPORT ===")
        
    except Exception as e:
        logger.error(f"Error generating end of day report: {e}")

def main():
    """Main entry point for the trading bot"""
    # Set up logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear log files
    bot_clear_logs()
    
    logger.info("=== Trading Bot Started ===")
    logger.info(f"Monitoring symbols: {', '.join(SYMBOLS)}")
    
    # Log bot version and mode
    mode = "SANDBOX" if USE_SANDBOX else "PRODUCTION"
    logger.info(f"Trading bot starting in {mode} MODE - Version 1.0.0")
    logger.info(f"Watchlist symbols: {', '.join(SYMBOLS)}")
    
    # Initialize Tradier client
    tradier_client = TradierClient()

    # Initialize trade tracker
    trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
    
    # Check if we have NumPy compatibility issues
    numpy_compatibility_issue = False
    try:
        import numpy as np
        import pandas as pd
        # Try a simple operation to verify numpy works
        test_array = np.array([1, 2, 3])
        test_df = pd.DataFrame({'test': test_array})
        logger.info("NumPy and pandas are working correctly")
    except Exception as e:
        numpy_compatibility_issue = True
        logger.error(f"NumPy compatibility issue detected: {e}")
        logger.warning("Bot will run with reduced functionality - some features will be disabled")
    
    # Define safe scheduling functions that handle errors
    def safe_morning_analysis():
        try:
            morning_analysis()
        except NameError as e:
            logger.warning(f"Could not run morning analysis: {e}")
            logger.warning("This feature is disabled due to NumPy compatibility issues")
        except Exception as e:
            logger.error(f"Error in morning analysis: {e}")
    
    def safe_manage_positions():
        try:
            manage_positions(tradier_client)
        except Exception as e:
            logger.error(f"Error managing positions: {e}")
    
    def safe_find_opportunities():
        try:
            find_trading_opportunities(tradier_client)
        except NameError as e:
            logger.warning(f"Could not find trading opportunities: {e}")
            logger.warning("This feature is disabled due to NumPy compatibility issues")
        except Exception as e:
            logger.error(f"Error finding trading opportunities: {e}")
    
    def safe_end_of_day():
        try:
            end_of_day_report(tradier_client)
        except Exception as e:
            logger.error(f"Error generating end of day report: {e}")
    
    # Schedule tasks with safe wrappers
    schedule.every().day.at("09:30").do(safe_morning_analysis)
    schedule.every(30).minutes.do(safe_find_opportunities)
    schedule.every(60).minutes.do(safe_manage_positions)
    schedule.every().day.at("16:00").do(safe_end_of_day)
    
    # Run initial checks
    logger.info("Running initial checks...")
    
    try:
        # Check account balances
        balances = tradier_client.get_account_balances()
        if balances:
            logger.info(f"Account balance: ${balances.get('total_equity', 'Unknown')}")
            logger.info(f"Buying power: ${balances.get('option_buying_power', 'Unknown')}")
        else:
            logger.warning("Could not retrieve account balances")
        
        # Check current positions
        positions = tradier_client.get_account_positions()
        if positions:
            logger.info(f"Current positions: {len(positions)}")
            for position in positions:
                symbol = position.get('symbol', 'Unknown')
                quantity = position.get('quantity', 0)
                cost_basis = position.get('cost_basis', 0)
                
                # Make sure position is in trade tracker
                if symbol not in trade_tracker.trades:
                    logger.warning(f"Adding missing position to trade tracker: {symbol}")
                    trade_tracker.add_position(symbol, quantity)
                
                logger.info(f"Position: {symbol}, Quantity: {quantity}, Cost Basis: ${cost_basis}")
        else:
            logger.info("No open positions")
        
        # Run initial position management check
        if not numpy_compatibility_issue:
            logger.info("Running initial position management check...")
            safe_manage_positions()
        else:
            logger.warning("Skipping initial position management due to NumPy compatibility issue")
            
        # Run initial opportunity finder
        if not numpy_compatibility_issue:
            logger.info("Looking for initial trading opportunities...")
            safe_find_opportunities()
        else:
            logger.warning("Skipping initial opportunity finding due to NumPy compatibility issue")
    
    except Exception as e:
        logger.error(f"Error during initial checks: {e}")
    
    # Main loop
    logger.info("Starting main scheduling loop...")
    
    # Add heartbeat counter
    heartbeat_counter = 0
    
    while True:
        try:
            # Run pending tasks
            schedule.run_pending()
            
            # Log heartbeat every 5 minutes (30 iterations at 10 seconds each)
            heartbeat_counter += 1
            if heartbeat_counter >= 30:
                logger.info("Trading bot heartbeat - still running")
                heartbeat_counter = 0
            
            # Sleep for a bit to avoid high CPU usage
            time.sleep(10)
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    print(f"Options Trading Bot starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Monitoring symbols: {', '.join(SYMBOLS)}")
    
    # Set up logging
    setup_logging()

    # Add version tracking
    __version__ = "1.0.0"
    
    # Log startup information
    logger = logging.getLogger()
    logger.info(f"Trading bot starting in {'SANDBOX' if 'SANDBOX' in TRADIER_BASE_URL else 'PRODUCTION'} MODE - Version {__version__}")
    logger.info(f"Watchlist symbols: {', '.join(SYMBOLS)}")
    
    # Uncomment to run test mode first
    # run_test()  # Commenting out to prevent infinite loop
    
    # Main scheduling loop
    print("\nBot running. Press Ctrl+C to exit.")
    main()
