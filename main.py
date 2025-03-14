# main.py – Orchestrate scheduling and run the trading bot
import time
import schedule
from datetime import datetime
from ai_analysis import fetch_news_summary, spot_check_news, analyze_with_deepseek
from strategy import decide_trade, compute_technicals, select_option_contract
from execution import TradierClient
from report import compose_report, send_email_report, log_trade
from market_data import get_latest_price_data
from config import ACCOUNT_ID, SYMBOLS

# Initialize clients
tradier = TradierClient()

# Define scheduled tasks
def morning_analysis():
    """Run pre-market analysis and make trade decisions"""
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
            print(f"Could not get price data for {symbol}, skipping.")
            continue
        
        # Calculate technical indicators
        techs = compute_technicals(prices)
        
        # Make trade decision
        signal = decide_trade(sentiment, reasoning, techs, symbol, prices)
        
        if signal:
            # Select an appropriate option contract
            option_symbol = select_option_contract(symbol, signal, prices)
            print(f"Selected option: {option_symbol}")
            
            # Place the trade (buy_to_open for new positions)
            side = 'buy_to_open'
            try:
                result = tradier.place_option_order(ACCOUNT_ID, option_symbol, side)
                trade_status = f"Trade placed: {result}"
            except Exception as e:
                trade_status = f"Error placing trade: {e}"
                result = None
            
            # Log the trade for reporting with both reasoning and conclusion
            log_trade(symbol, signal, option_symbol, f"Conclusion: {conclusion}\nDetailed reasoning: {reasoning}\n{trade_status}")
            
            print(f"Trade decision for {symbol}: {signal} - {option_symbol}")
            if result:
                print(f"Trade result: {result}")
        else:
            print(f"No trade signal for {symbol}")

def midday_analysis():
    """Run midday analysis to potentially adjust positions"""
    print(f"\n=== Midday Analysis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    news = fetch_news_summary(time_of_day='midday')
    sentiment, reasoning, conclusion = analyze_with_deepseek(news)
    
    print(f"Midday market sentiment: {sentiment}")
    print(f"AI conclusion: {conclusion[:200]}...\n")  # Print first 200 chars of conclusion
    
    # Similar logic as morning_analysis
    for symbol in SYMBOLS:
        print(f"\nMidday check for {symbol}...")
        prices = get_latest_price_data(symbol)
        if prices.empty:
            continue
        
        techs = compute_technicals(prices)
        signal = decide_trade(sentiment, reasoning, techs, symbol, prices)
        
        if signal:
            option_symbol = select_option_contract(symbol, signal, prices)
            side = 'buy_to_open'  # Could be more complex based on existing positions
            try:
                result = tradier.place_option_order(ACCOUNT_ID, option_symbol, side)
                trade_status = f"Trade placed: {result}"
            except Exception as e:
                trade_status = f"Error placing trade: {e}"
                result = None
                
            log_trade(symbol, signal, option_symbol, f"Conclusion: {conclusion}\nDetailed reasoning: {reasoning}\n{trade_status}")
            
            print(f"Midday trade for {symbol}: {signal} - {option_symbol}")
            if result:
                print(f"Trade result: {result}")

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
    print(f"\n=== Spot Check ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    result = spot_check_news("Major market updates and breaking financial news")
    print(f"Spot check result: {result[:100]}...")  # Print first 100 chars

# Schedule the tasks
schedule.every().day.at("09:00").do(morning_analysis)
schedule.every().day.at("12:00").do(midday_analysis)
schedule.every().day.at("16:00").do(end_of_day_report)
schedule.every(2).hours.do(random_check)

# For testing/development - run each function once at startup
def run_test():
    """Run test functions to verify everything is working"""
    print("\n=== RUNNING TEST MODE ===")
    morning_analysis()
    midday_analysis()
    end_of_day_report()
    random_check()
    print("=== TEST MODE COMPLETE ===\n")

if __name__ == "__main__":
    print(f"Options Trading Bot starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Monitoring symbols: {', '.join(SYMBOLS)}")
    
    # Uncomment to run test mode first
    run_test()
    
    # Main scheduling loop
    print("\nBot running. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check for scheduled tasks every 30 seconds
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"\nError in main loop: {e}")
        raise
