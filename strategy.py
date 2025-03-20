# strategy.py – Determine trading signals based on AI insights and technicals
import numpy as np
import pandas as pd
import logging
from config import MIN_PRICE_DATA_DAYS, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD, MIN_OPTION_DTE, MAX_OPTION_DTE

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

def select_option_contract(symbol, signal, price_data=None, expiration_days=None, option_chain=None):
    """
    Select an appropriate option contract based on the trading signal.
    
    Args:
        symbol (str): The stock ticker symbol
        signal (str): Trading signal - 'BUY_CALL' or 'BUY_PUT'
        price_data (pandas.DataFrame, optional): DataFrame with price history
        expiration_days (int, optional): Target days until expiration. If None, uses MIN_OPTION_DTE from config
        option_chain (dict, optional): Pre-fetched option chain data
        
    Returns:
        str: Option symbol in Tradier's expected format
    """
    import datetime
    
    # If expiration_days is not specified, use the MIN_OPTION_DTE from config
    if expiration_days is None:
        expiration_days = MIN_OPTION_DTE
        logger.info(f"Using default expiration days from config: {expiration_days}")
    
    # Ensure expiration_days is within the configured range
    expiration_days = max(expiration_days, MIN_OPTION_DTE)
    expiration_days = min(expiration_days, MAX_OPTION_DTE)
    
    # Get current date and target expiration
    today = datetime.datetime.now()
    expiry = today + datetime.timedelta(days=expiration_days)
    
    # Format expiry date for Tradier API (YYYY-MM-DD)
    tradier_expiry = expiry.strftime("%Y-%m-%d")
    logger.info(f"Target expiration date: {tradier_expiry} ({expiration_days} days from now)")
    
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

def evaluate_position(symbol, underlying_symbol, is_call, price_data, technicals, pnl_percent, market_sentiment=None, days_held=0):
    """
    Evaluate an existing position and determine whether to hold or sell
    
    Args:
        symbol (str): The option symbol
        underlying_symbol (str): The underlying stock symbol
        is_call (bool): True if this is a call option, False if put
        price_data (pandas.DataFrame): DataFrame with price history for the underlying
        technicals (dict): Technical indicators for the underlying
        pnl_percent (float): Current profit/loss percentage
        market_sentiment (str, optional): Overall market sentiment (bullish/bearish/neutral)
        days_held (int, optional): Number of days the position has been held
        
    Returns:
        tuple: (decision, reasoning) where decision is one of "SELL", "PARTIAL_SELL", or "HOLD"
    """
    from config import STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT
    
    # Default decision is to hold
    decision = "HOLD"
    reasoning = "Default position is to hold"
    
    # Basic stop loss and take profit checks
    if pnl_percent <= -STOP_LOSS_PERCENT:
        return "SELL", f"Stop loss triggered: {pnl_percent:.2%} loss exceeds {STOP_LOSS_PERCENT:.2%} threshold"
        
    if pnl_percent >= TAKE_PROFIT_PERCENT:
        return "SELL", f"Take profit triggered: {pnl_percent:.2%} gain exceeds {TAKE_PROFIT_PERCENT:.2%} threshold"
    
    # Check if we have sufficient technical data
    if not technicals or 'error' in technicals:
        return decision, "Insufficient technical data for advanced analysis, holding position"
    
    # Get current price and calculate recent price movement
    if len(price_data) < 2:
        return decision, "Insufficient price data for analysis, holding position"
        
    current_price = price_data['close'].iloc[-1]
    prev_price = price_data['close'].iloc[-2]
    price_change = (current_price - prev_price) / prev_price
    
    # Extract key technical indicators
    rsi = technicals.get('rsi')
    ma20 = technicals.get('ma20')
    ma50 = technicals.get('ma50')
    
    # Initialize reasoning components
    reasons = []
    
    # Analyze technical indicators for call options
    if is_call:
        # For call options, we want to sell if the underlying is showing bearish signals
        
        # Check for overbought conditions (RSI > 70)
        if rsi and rsi > 70:
            reasons.append(f"RSI is overbought at {rsi:.2f}")
            decision = "SELL" if pnl_percent > 0.10 else "PARTIAL_SELL"
        
        # Check if price is below short-term moving average (bearish signal)
        if ma20 and current_price < ma20:
            reasons.append(f"Price {current_price:.2f} below MA20 {ma20:.2f}")
            decision = "SELL" if pnl_percent > 0 else "PARTIAL_SELL"
            
        # Check for bearish market sentiment
        if market_sentiment == 'bearish':
            reasons.append("Overall market sentiment is bearish")
            decision = "SELL" if pnl_percent > 0 else "PARTIAL_SELL"
            
        # Check for recent price decline
        if price_change < -0.02:  # 2% drop
            reasons.append(f"Recent price decline of {price_change:.2%}")
            decision = "SELL" if pnl_percent > 0 else "PARTIAL_SELL"
            
        # Positive signals that might override sell decision
        positive_signals = 0
        
        # Check for strong uptrend (price above both moving averages)
        if ma20 and ma50 and current_price > ma20 and current_price > ma50 and ma20 > ma50:
            reasons.append(f"Strong uptrend: price above both MA20 and MA50")
            positive_signals += 1
            
        # Check for bullish market sentiment
        if market_sentiment == 'bullish':
            reasons.append("Overall market sentiment is bullish")
            positive_signals += 1
            
        # Check for recent price increase
        if price_change > 0.02:  # 2% gain
            reasons.append(f"Recent price increase of {price_change:.2%}")
            positive_signals += 1
            
        # If we have multiple positive signals, consider holding even if there are some sell signals
        if positive_signals >= 2 and decision != "SELL":
            decision = "HOLD"
            reasons.append("Multiple positive signals suggest continued upside potential")
            
    else:  # Put options
        # For put options, we want to sell if the underlying is showing bullish signals
        
        # Check for oversold conditions (RSI < 30)
        if rsi and rsi < 30:
            reasons.append(f"RSI is oversold at {rsi:.2f}")
            decision = "SELL" if pnl_percent > 0.10 else "PARTIAL_SELL"
        
        # Check if price is above short-term moving average (bullish signal)
        if ma20 and current_price > ma20:
            reasons.append(f"Price {current_price:.2f} above MA20 {ma20:.2f}")
            decision = "SELL" if pnl_percent > 0 else "PARTIAL_SELL"
            
        # Check for bullish market sentiment
        if market_sentiment == 'bullish':
            reasons.append("Overall market sentiment is bullish")
            decision = "SELL" if pnl_percent > 0 else "PARTIAL_SELL"
            
        # Check for recent price increase
        if price_change > 0.02:  # 2% gain
            reasons.append(f"Recent price increase of {price_change:.2%}")
            decision = "SELL" if pnl_percent > 0 else "PARTIAL_SELL"
            
        # Positive signals for puts (bearish signals) that might override sell decision
        positive_signals = 0
        
        # Check for strong downtrend (price below both moving averages)
        if ma20 and ma50 and current_price < ma20 and current_price < ma50 and ma20 < ma50:
            reasons.append(f"Strong downtrend: price below both MA20 and MA50")
            positive_signals += 1
            
        # Check for bearish market sentiment
        if market_sentiment == 'bearish':
            reasons.append("Overall market sentiment is bearish")
            positive_signals += 1
            
        # Check for recent price decrease
        if price_change < -0.02:  # 2% loss
            reasons.append(f"Recent price decrease of {price_change:.2%}")
            positive_signals += 1
            
        # If we have multiple positive signals, consider holding even if there are some sell signals
        if positive_signals >= 2 and decision != "SELL":
            decision = "HOLD"
            reasons.append("Multiple negative signals suggest continued downside potential")
    
    # Special case: If we're profitable but have held for a while, consider taking partial profits
    if pnl_percent > 0.25 and days_held > 5 and decision == "HOLD":
        decision = "PARTIAL_SELL"
        reasons.append(f"Taking partial profits after {days_held} days with {pnl_percent:.2%} gain")
    
    # Compile the reasoning
    reasoning = "; ".join(reasons) if reasons else "No strong signals, maintaining position"
    
    return decision, reasoning