#!/usr/bin/env python
# test_bot.py - Test the core functionality of the options trading bot

import sys
from datetime import datetime
import pandas as pd

# Import bot components
from ai_analysis import fetch_news_summary, analyze_with_deepseek
from market_data import get_latest_price_data
from strategy import compute_technicals, decide_trade, select_option_contract
from execution import TradierClient
from config import SYMBOLS, ACCOUNT_ID

# Set up logging
def log(message):
    """Print a timestamped log message"""
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    except UnicodeEncodeError:
        # Handle Unicode encoding errors by replacing problematic characters
        clean_message = message.encode('ascii', 'replace').decode('ascii')
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {clean_message}")

def test_ai_analysis():
    """Test AI analysis functionality"""
    log("Testing AI Analysis...")
    
    # Fetch market news
    log("Fetching market news...")
    news = fetch_news_summary(time_of_day='pre_market')
    
    # If news is too short, it might indicate an API error
    if len(news) < 50:
        log(f"WARNING: News summary is very short ({len(news)} chars). Possible API issue.")
    else:
        log(f"Received news summary ({len(news)} chars)")
    
    # Analyze sentiment using DeepSeek
    log("Analyzing sentiment with DeepSeek...")
    sentiment, reasoning, conclusion = analyze_with_deepseek(news)
    
    log(f"Sentiment: {sentiment}")
    
    # Sanitize conclusion and reasoning to avoid encoding issues
    safe_conclusion = conclusion[:150].encode('ascii', 'replace').decode('ascii')
    log(f"Conclusion sample: {safe_conclusion}...")
    
    reasoning_length = len(reasoning) if reasoning else 0
    log(f"Reasoning length: {reasoning_length} chars")
    
    return sentiment, reasoning, conclusion

def test_market_data(symbol):
    """Test market data acquisition for a symbol"""
    log(f"Testing market data acquisition for {symbol}...")
    
    # Get price data
    price_data = get_latest_price_data(symbol)
    
    if price_data is None or price_data.empty:
        log(f"ERROR: Could not retrieve price data for {symbol}")
        return None
    
    log(f"Retrieved {len(price_data)} price records for {symbol}")
    log(f"Latest price: ${price_data['close'].iloc[-1]:.2f}")
    
    # Calculate technical indicators
    technicals = compute_technicals(price_data)
    log(f"Technical indicators: {technicals}")
    
    return price_data, technicals

def test_strategy(sentiment, reasoning, technicals, symbol, price_data):
    """Test trading strategy logic"""
    log(f"Testing strategy logic for {symbol}...")
    
    if price_data is None or price_data.empty:
        log("ERROR: Cannot test strategy without price data")
        return None
    
    # Determine trade signal
    signal = decide_trade(sentiment, reasoning, technicals, symbol, price_data)
    log(f"Trade signal: {signal if signal else 'No signal'}")
    
    if signal:
        # Select option contract
        option_symbol = select_option_contract(symbol, signal, price_data)
        log(f"Selected option contract: {option_symbol}")
        return signal, option_symbol
    
    return signal, None

def test_execution(symbol, signal, option_symbol):
    """Test trade execution (read-only)"""
    log(f"Testing trade execution for {symbol} (READ-ONLY mode)...")
    
    if not signal or not option_symbol:
        log("No signal or option symbol to test execution")
        return
    
    # Initialize Tradier client
    client = TradierClient()
    
    # Get account balances (read-only operation)
    try:
        account_info = client.get_account_balances(ACCOUNT_ID)
        log(f"Account cash balance: ${account_info.get('cash', 'N/A')}")
        log(f"Account buying power: ${account_info.get('buying_power', 'N/A')}")
    except Exception as e:
        log(f"ERROR accessing account: {e}")
    
    # Check option chain data (read-only operation)
    try:
        option_data = client.get_option_chain(symbol)
        if option_data:
            expiration_dates = option_data.get('expirations', {}).get('date', [])
            log(f"Available expiration dates: {expiration_dates[:3]}...")
    except Exception as e:
        log(f"ERROR getting option chain: {e}")
    
    # NOTE: Not placing actual orders, just simulating
    log(f"SIMULATED ORDER: Would place a {signal} order for {option_symbol}")
    log(f"Using account: {ACCOUNT_ID}")

def run_full_test():
    """Run a complete test of the trading bot pipeline"""
    log("Starting full bot test...")
    log(f"Testing with symbols: {SYMBOLS}")
    
    # Pick first symbol for focused testing
    test_symbol = SYMBOLS[0]
    log(f"Using {test_symbol} for detailed testing")
    
    # Test AI analysis
    try:
        sentiment, reasoning, conclusion = test_ai_analysis()
        
        # Test market data
        price_data_result = test_market_data(test_symbol)
        if not price_data_result:
            log("ERROR: Market data test failed, stopping test")
            return
        
        price_data, technicals = price_data_result
        
        # Test strategy
        strategy_result = test_strategy(sentiment, reasoning, technicals, test_symbol, price_data)
        signal, option_symbol = strategy_result
        
        # Test execution (read-only)
        test_execution(test_symbol, signal, option_symbol)
        
        log("Test completed successfully!")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())

if __name__ == "__main__":
    log("Options Trading Bot Test Starting")
    log("-" * 50)
    
    try:
        run_full_test()
    except KeyboardInterrupt:
        log("Test stopped by user")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())
    
    log("-" * 50)
    log("Test complete")
