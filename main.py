# main.py – Orchestrate scheduling and run the trading bot
import time
import schedule
from datetime import datetime, time as dt_time
import pytz
import calendar
import os
import logging
from ai_analysis import fetch_news_summary, spot_check_news, analyze_with_deepseek
from strategy import decide_trade, compute_technicals, select_option_contract
from execution import TradierClient
# from report import compose_report, send_email_report, log_trade  # Temporarily disabled
from market_data import get_latest_price_data
from config import ACCOUNT_ID, SYMBOLS
from opportunity_finder import identify_opportunities, process_opportunities
from bot_logger import clear_logs as bot_clear_logs

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

# Define scheduled tasks
def morning_analysis():
    """Run pre-market analysis and make trade decisions"""
    # Morning analysis runs regardless of market hours (pre-market)
    if not is_trading_day():
        print(f"\n=== Skipping Morning Analysis: Not a trading day ===")
        return
        
    print(f"\n=== Morning Analysis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    # Fetch news and analyze
    news = fetch_news_summary(time_of_day='pre_market')
    sentiment, reasoning, conclusion = analyze_with_deepseek(news)
    
    print(f"Market sentiment: {sentiment}")
    print(f"AI conclusion: {conclusion[:200]}...\n")  # Print first 200 chars of conclusion
    
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
            contract = select_option_contract(symbol, signal, prices)
            
            if contract:
                try:
                    # Execute the trade
                    order_result = tradier.place_option_order(
                        option_symbol=contract,
                        side='buy',
                        quantity=1,
                        order_type='market',
                        duration='day'
                    )
                    
                    # Log the trade
                    log_trade((symbol, contract, signal, 1, datetime.now()))
                    
                    print(f"Order placed for {contract}: {order_result}")
                except Exception as e:
                    print(f"Error placing order: {e}")
            else:
                print(f"Could not find suitable option contract for {symbol}")
    
    # Find additional opportunities outside watchlist
    print("\nSearching for additional trading opportunities...")
    opportunities = identify_opportunities(market_news=news, max_opportunities=3)
    
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
            contract = select_option_contract(symbol, signal, prices)
            
            if contract:
                try:
                    # Execute the trade
                    order_result = tradier.place_option_order(
                        option_symbol=contract,
                        side='buy',
                        quantity=1,
                        order_type='market',
                        duration='day'
                    )
                    
                    # Log the trade
                    log_trade((symbol, contract, signal, 1, datetime.now()))
                    
                    print(f"Midday order placed for {contract}: {order_result}")
                except Exception as e:
                    print(f"Error placing midday order: {e}")
            else:
                print(f"Could not find suitable option contract for {symbol}")
    
    # Find additional opportunities outside watchlist
    print("\nSearching for additional midday trading opportunities...")
    opportunities = identify_opportunities(market_news=news, max_opportunities=2)
    
    if opportunities:
        print(f"Found {len(opportunities)} additional midday trading opportunities")
        executed_trades = process_opportunities(opportunities, tradier)
        print(f"Executed {len(executed_trades)} trades for opportunities outside watchlist")
    else:
        print("No additional midday trading opportunities identified")

def end_of_day_report():
    """Generate and send end-of-day report"""
    print(f"\n=== End of Day Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    report = compose_report()
    print("\nDaily Report:")
    print(report)
    
    try:
        send_email_report(report)
        print("Email report sent successfully")
    except Exception as e:
        print(f"Error sending email report: {e}")

def random_check():
    """Perform a spot check for major market updates"""
    if not is_market_open():
        print(f"\n=== Skipping Random Check: Market closed ===")
        return
        
    print(f"\n=== Random Check ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    # Check for major news that might impact our positions
    query = f"Breaking financial news and market updates for {datetime.now().strftime('%Y-%m-%d')}"
    news_update = spot_check_news(query)
    
    # If significant news is found, analyze for potential trades
    if "SIGNIFICANT" in news_update.upper():
        print("Significant market news detected, analyzing for opportunities...")
        opportunities = identify_opportunities(market_news=news_update, max_opportunities=1)
        
        if opportunities:
            print(f"Found {len(opportunities)} urgent trading opportunities")
            executed_trades = process_opportunities(opportunities, tradier)
            print(f"Executed {len(executed_trades)} trades based on breaking news")
    else:
        print("No significant market updates requiring immediate action")

# Placeholder for report functionality
def log_trade(trade_data):
    if isinstance(trade_data, tuple):
        symbol, signal, option_symbol, details = trade_data
        trade_data = {
            'symbol': symbol,
            'signal': signal,
            'option_symbol': option_symbol,
            'details': details
        }
    print(f"Trade executed: {trade_data}")

def send_email_report(recipient):
    print("Report feature temporarily disabled")

def compose_report():
    return "Report feature temporarily disabled"

# Schedule the tasks
schedule.every().day.at("09:00").do(morning_analysis)
schedule.every().day.at("12:00").do(midday_analysis)
# schedule.every().day.at("16:00").do(end_of_day_report)  # Temporarily disabled
schedule.every(2).hours.do(random_check)

# For testing/development - run each function once at startup
def run_test():
    """Run test functions to verify everything is working"""
    print("\n=== RUNNING TEST MODE ===")
    morning_analysis()
    midday_analysis()
    # end_of_day_report()  # Temporarily disabled
    random_check()
    print("=== TEST MODE COMPLETE ===\n")
    
    # Clear logs after test run
    bot_clear_logs()

if __name__ == "__main__":
    print(f"Options Trading Bot starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Monitoring symbols: {', '.join(SYMBOLS)}")
    
    # Set up logging
    setup_logging()
    
    # Uncomment to run test mode first
    run_test()
    
    # Main scheduling loop
    print("\nBot running. Press Ctrl+C to exit.")
    try:
        while True:
            # Only run scheduled tasks during market hours, except for morning analysis
            if is_market_open() or schedule.jobs[0].next_run.time() == dt_time(9, 0):
                schedule.run_pending()
            time.sleep(30)  # Check for scheduled tasks every 30 seconds
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
        # Clear logs on exit
        bot_clear_logs()
    except Exception as e:
        print(f"\nError in main loop: {e}")
        raise
