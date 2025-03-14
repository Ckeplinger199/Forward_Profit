# strategy.py – Determine trading signals based on AI insights and technicals
import numpy as np
import pandas as pd

def compute_technicals(price_data):
    """
    Compute technical indicators from recent price data.
    
    Args:
        price_data (pandas.DataFrame): DataFrame with price history containing 'close' column
        
    Returns:
        dict: Technical indicators including RSI, moving averages, etc.
    """
    # Check if we have enough data
    if len(price_data) < 30:
        print("Warning: Not enough price data for reliable technical indicators")
        return {'rsi': None, 'ma50': None, 'ma20': None}
    
    # Calculate RSI (Relative Strength Index) using pandas
    # This is a simplified version of RSI calculation
    delta = price_data['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Calculate moving averages
    ma20 = price_data['close'].rolling(window=20).mean()
    ma50 = price_data['close'].rolling(window=min(50, len(price_data)-1)).mean()
    
    # Get the latest values
    latest_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None
    latest_ma20 = ma20.iloc[-1] if not pd.isna(ma20.iloc[-1]) else None
    latest_ma50 = ma50.iloc[-1] if not pd.isna(ma50.iloc[-1]) else None
    
    return {
        'rsi': latest_rsi, 
        'ma20': latest_ma20, 
        'ma50': latest_ma50
    }

def decide_trade(ai_sentiment, ai_reasoning, technicals, symbol, price_data):
    """
    Decide whether to buy call, buy put, or do nothing for the given symbol.
    
    Args:
        ai_sentiment (str): 'bullish'/'bearish' from DeepSeek analysis
        ai_reasoning (str): text explanation from AI (for logging/reporting)
        technicals (dict): dict of technical indicator values
        symbol (str): The stock ticker symbol
        price_data (pandas.DataFrame): DataFrame with price history
        
    Returns:
        str or None: Trading signal - 'BUY_CALL', 'BUY_PUT', or None for no action
    """
    signal = None
    
    # Safety check - ensure we have price data
    if price_data.empty or len(price_data) < 2:
        print(f"Warning: Insufficient price data for {symbol}")
        return signal
    
    current_price = price_data['close'].iloc[-1]
    
    if ai_sentiment == 'bullish':
        # Example rule: bullish sentiment and price above MA50 -> buy call
        if technicals.get('ma50') and current_price > technicals['ma50']:
            # Additional condition: RSI not overbought
            if technicals.get('rsi') and technicals['rsi'] < 70:
                signal = 'BUY_CALL'
    elif ai_sentiment == 'bearish':
        # Example rule: bearish sentiment and RSI overbought -> buy put
        if technicals.get('rsi') and technicals['rsi'] > 70:
            # Additional condition: price below short-term MA
            if technicals.get('ma20') and current_price < technicals['ma20']:
                signal = 'BUY_PUT'
    
    # Add trade reasoning
    trade_reasoning = f"Decision for {symbol}: {signal if signal else 'NO_ACTION'}\n"
    trade_reasoning += f"AI Sentiment: {ai_sentiment}\n"
    trade_reasoning += f"Technical Indicators: RSI={technicals.get('rsi')}, MA50={technicals.get('ma50')}\n"
    trade_reasoning += f"AI Reasoning: {ai_reasoning}"
    
    print(trade_reasoning)
    
    return signal

def select_option_contract(symbol, signal, price_data=None, expiration_days=30, option_chain=None):
    """
    Select an appropriate option contract based on the trading signal.
    
    Args:
        symbol (str): The stock ticker symbol
        signal (str): Trading signal - 'BUY_CALL' or 'BUY_PUT'
        price_data (pandas.DataFrame, optional): DataFrame with price history
        expiration_days (int): Target days until expiration
        option_chain (dict, optional): Pre-fetched option chain data
        
    Returns:
        str: Option symbol in Tradier's expected format
    """
    import datetime
    
    # Get current date and target expiration
    today = datetime.datetime.now()
    expiry = today + datetime.timedelta(days=expiration_days)
    
    # Format expiry date for Tradier API (YYYY-MM-DD)
    tradier_expiry = expiry.strftime("%Y-%m-%d")
    
    # Assume we're using a strike price 5% higher for calls, 5% lower for puts
    if price_data is not None and not price_data.empty:
        current_price = price_data['close'].iloc[-1]
    else:
        # Placeholder price if real data not available
        current_price = 100
    
    if signal == 'BUY_CALL':
        strike = round(current_price * 1.05)
        option_type = 'call'
    else:  # BUY_PUT
        strike = round(current_price * 0.95)
        option_type = 'put'
    
    # Construct Tradier-compatible option symbol
    # Format: symbol + YYMMDD + C/P + Strike (padded)
    expiry_code = expiry.strftime("%y%m%d")
    option_code = "C" if option_type == "call" else "P"
    strike_padded = f"{strike:.2f}".replace(".", "")
    
    # Tradier format: e.g., SPY220617C00400000
    option_symbol = f"{symbol}{expiry_code}{option_code}{strike_padded.zfill(8)}"
    
    return option_symbol