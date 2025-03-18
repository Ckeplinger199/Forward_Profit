# strategy.py – Determine trading signals based on AI insights and technicals
import numpy as np
import pandas as pd
import logging
from config import MIN_PRICE_DATA_DAYS, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD

# Create a logger
logger = logging.getLogger(__name__)

def compute_technicals(price_data):
    """
    Compute technical indicators from recent price data.
    
    Args:
        price_data (pandas.DataFrame): DataFrame with price history containing 'close' column
        
    Returns:
        dict: Technical indicators including RSI, moving averages, etc.
    """
    # Define minimum required data points
    min_data_points = getattr(MIN_PRICE_DATA_DAYS, 'value', 30)
    
    # Check if we have enough data
    if price_data is None or price_data.empty:
        logger.warning("No price data provided for technical analysis")
        return {'rsi': None, 'ma50': None, 'ma20': None, 'error': 'No price data available'}
        
    if len(price_data) < min_data_points:
        logger.warning(f"Insufficient price data for reliable technical indicators: {len(price_data)} days available, need at least {min_data_points}")
        
        # We can still calculate some indicators with limited data
        available_days = len(price_data)
        
        # Return partial data with warning
        result = {
            'rsi': None, 
            'ma20': None, 
            'ma50': None,
            'warning': f'Limited data ({available_days} days)',
            'data_sufficient': False
        }
        
        # Calculate what we can with available data
        if available_days >= 14:  # Minimum for RSI
            result.update(calculate_rsi(price_data))
            
        if available_days >= 20:  # Minimum for 20-day MA
            result.update(calculate_ma(price_data, 20))
            
        return result
    
    # We have sufficient data, calculate all indicators
    result = {
        'data_sufficient': True
    }
    
    # Calculate RSI
    result.update(calculate_rsi(price_data))
    
    # Calculate moving averages
    result.update(calculate_ma(price_data, 20))
    result.update(calculate_ma(price_data, 50))
    
    return result

def calculate_rsi(price_data, period=14):
    """
    Calculate RSI (Relative Strength Index)
    
    Args:
        price_data (pandas.DataFrame): DataFrame with price history
        period (int): RSI period
        
    Returns:
        dict: RSI value
    """
    try:
        # Calculate RSI using pandas
        delta = price_data['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Get the latest value
        latest_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None
        
        return {'rsi': latest_rsi}
    except Exception as e:
        logger.error(f"Error calculating RSI: {str(e)}")
        return {'rsi': None}

def calculate_ma(price_data, period):
    """
    Calculate Moving Average
    
    Args:
        price_data (pandas.DataFrame): DataFrame with price history
        period (int): MA period
        
    Returns:
        dict: MA value
    """
    try:
        # Calculate moving average
        ma = price_data['close'].rolling(window=min(period, len(price_data)-1)).mean()
        
        # Get the latest value
        latest_ma = ma.iloc[-1] if not pd.isna(ma.iloc[-1]) else None
        
        return {f'ma{period}': latest_ma}
    except Exception as e:
        logger.error(f"Error calculating MA{period}: {str(e)}")
        return {f'ma{period}': None}

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
    if price_data is None or price_data.empty:
        logger.warning(f"No price data available for {symbol}")
        return signal
    
    if len(price_data) < 2:
        logger.warning(f"Insufficient price data for {symbol}: only {len(price_data)} days available")
        return signal
    
    # Check if technical data is sufficient
    if not technicals.get('data_sufficient', True):
        logger.warning(f"Limited technical data for {symbol}: {technicals.get('warning', 'unknown issue')}")
        # We can still proceed with limited data, but log the warning
    
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
    
    logger.info(trade_reasoning)
    
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
    
    # Format: symbol + YYMMDD + C/P + Strike (padded)
    expiry_code = expiry.strftime("%y%m%d")
    option_code = "C" if option_type == "call" else "P"
    
    # Convert strike to a string with two decimal places, then remove decimal point
    # Strike needs to be properly padded to 8 characters with leading zeros
    strike_price = float(strike)
    strike_dollars = int(strike_price)
    strike_cents = int((strike_price - strike_dollars) * 1000)
    strike_padded = f"{strike_dollars:05d}{strike_cents:03d}"
    
    # Tradier format: e.g., SPY220617C00400000
    option_symbol = f"{symbol}{expiry_code}{option_code}{strike_padded}"
    
    logger.info(f"Generated option symbol: {option_symbol} for {symbol} {expiry_code} {option_code} strike {strike}")
    
    return option_symbol