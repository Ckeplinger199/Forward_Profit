# market_data.py - Fetch market data for analysis and trading
import requests
import pandas as pd
import numpy as np
import datetime
import time
import logging
import json
from config import (TRADIER_API_KEY, TRADIER_SANDBOX_KEY, USE_SANDBOX, 
                   TRADIER_BASE_URL, DEBUG_API_RESPONSES, ENABLE_SANDBOX_FALLBACK,
                   MAX_RETRIES, RETRY_DELAY_SECONDS)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("market_data")

def get_latest_price_data(symbol, lookback_days=120):
    """
    Fetch historical price data for a given symbol.
    
    Args:
        symbol (str): Stock symbol to fetch data for
        lookback_days (int): Number of days to look back
        
    Returns:
        pandas.DataFrame: DataFrame with historical price data
    """
    if not symbol:
        logger.error("No symbol provided for price data retrieval")
        return pd.DataFrame()
    
    # Set up the API endpoint
    url = f"{TRADIER_BASE_URL}/markets/history"
    
    # Set up the request headers and parameters
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    # Calculate the start date (lookback_days ago)
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    
    params = {
        "symbol": symbol,
        "interval": "daily",
        "start": start_date,
        "end": end_date
    }
    
    # Make the request with retry logic
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses
            
            data = response.json()
            
            if DEBUG_API_RESPONSES:
                logger.info(f"API Response for {symbol} price data: {json.dumps(data, indent=2)}")
            
            # Check if we have history data
            if 'history' in data and 'day' in data['history']:
                # Convert to DataFrame
                history = data['history']['day']
                if not history:
                    logger.warning(f"No price history found for {symbol}")
                    return pd.DataFrame()
                
                df = pd.DataFrame(history)
                
                # Convert date to datetime
                df['date'] = pd.to_datetime(df['date'])
                
                # Sort by date
                df = df.sort_values('date')
                
                logger.info(f"Successfully retrieved {len(df)} days of price data for {symbol}")
                return df
            else:
                logger.warning(f"Unexpected response format for {symbol}: {data}")
                return pd.DataFrame()
                
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Request failed for {symbol}, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to retrieve price data for {symbol} after {MAX_RETRIES} attempts: {e}")
                return pd.DataFrame()
    
    return pd.DataFrame()

def calculate_technical_indicators(df):
    """
    Calculate technical indicators for a price DataFrame.
    
    Args:
        df (pandas.DataFrame): DataFrame with price data
        
    Returns:
        dict: Dictionary with calculated indicators
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for technical indicator calculation")
        return {
            "rsi": None,
            "ma_fast": None,
            "ma_slow": None,
            "trend": "unknown"
        }
    
    try:
        # Calculate RSI (14-day)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Calculate moving averages
        ma_fast = df['close'].rolling(window=20).mean()
        ma_slow = df['close'].rolling(window=50).mean()
        
        # Determine trend
        if ma_fast.iloc[-1] > ma_slow.iloc[-1]:
            trend = "bullish"
        else:
            trend = "bearish"
        
        # Get the latest values
        latest_rsi = rsi.iloc[-1]
        latest_ma_fast = ma_fast.iloc[-1]
        latest_ma_slow = ma_slow.iloc[-1]
        
        logger.info(f"Technical indicators calculated: RSI={latest_rsi:.2f}, MA20={latest_ma_fast:.2f}, MA50={latest_ma_slow:.2f}, Trend={trend}")
        
        return {
            "rsi": latest_rsi,
            "ma_fast": latest_ma_fast,
            "ma_slow": latest_ma_slow,
            "trend": trend
        }
    except Exception as e:
        logger.error(f"Error calculating technical indicators: {e}")
        return {
            "rsi": None,
            "ma_fast": None,
            "ma_slow": None,
            "trend": "unknown"
        }

def get_option_chain(symbol, expiration=None):
    """
    Fetch option chain data for a given symbol.
    
    Args:
        symbol (str): Stock symbol to fetch options for
        expiration (str, optional): Specific expiration date (YYYY-MM-DD)
        
    Returns:
        dict: Dictionary with calls and puts
    """
    if not symbol:
        logger.error("No symbol provided for option chain retrieval")
        return {}
    
    # Set up the API endpoint
    base_url = TRADIER_BASE_URL
    
    # First, get available expirations if not specified
    if expiration is None:
        exp_url = f"{base_url}/markets/options/expirations"
        api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        params = {
            "symbol": symbol,
            "includeAllRoots": "false"
        }
        
        try:
            exp_response = requests.get(exp_url, headers=headers, params=params)
            exp_response.raise_for_status()
            exp_data = exp_response.json()
            
            if DEBUG_API_RESPONSES:
                logger.info(f"API Response for {symbol} expirations: {json.dumps(exp_data, indent=2)}")
            
            if 'expirations' in exp_data and 'expiration' in exp_data['expirations']:
                expirations = exp_data['expirations']['expiration']
                if not expirations:
                    logger.warning(f"No option expirations found for {symbol}")
                    return {}
                
                # Choose the nearest expiration
                if isinstance(expirations, list):
                    expiration = expirations[0]
                else:
                    expiration = expirations
                
                logger.info(f"Using nearest expiration date for {symbol}: {expiration}")
            else:
                logger.warning(f"No expirations found for {symbol}")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve option expirations for {symbol}: {e}")
            return {}
    
    # Now get the option chain
    chain_url = f"{base_url}/markets/options/chains"
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "symbol": symbol,
        "expiration": expiration
    }
    
    # Make the request with retry logic
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(chain_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if DEBUG_API_RESPONSES:
                logger.info(f"API Response for {symbol} option chain: {json.dumps(data, indent=2)}")
            
            if 'options' in data and 'option' in data['options']:
                options = data['options']['option']
                
                # Separate calls and puts
                calls = [opt for opt in options if opt['option_type'] == 'call']
                puts = [opt for opt in options if opt['option_type'] == 'put']
                
                logger.info(f"Successfully retrieved option chain for {symbol}: {len(calls)} calls, {len(puts)} puts")
                
                return {
                    "calls": calls,
                    "puts": puts,
                    "expiration": expiration
                }
            else:
                if ENABLE_SANDBOX_FALLBACK and USE_SANDBOX:
                    logger.warning(f"No options data found for {symbol} in sandbox mode. Using simulated data.")
                    # Return simulated data for testing
                    return generate_simulated_options(symbol)
                else:
                    logger.warning(f"No options data found for {symbol}")
                    return {}
                
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Request failed for {symbol} option chain, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                if ENABLE_SANDBOX_FALLBACK and USE_SANDBOX:
                    logger.warning(f"Failed to retrieve option chain for {symbol} in sandbox mode. Using simulated data.")
                    # Return simulated data for testing
                    return generate_simulated_options(symbol)
                else:
                    logger.error(f"Failed to retrieve option chain for {symbol} after {MAX_RETRIES} attempts: {e}")
                    return {}
    
    return {}

def generate_simulated_options(symbol):
    """
    Generate simulated option data for testing when sandbox API fails
    
    Args:
        symbol (str): Stock symbol to generate options for
        
    Returns:
        dict: Dictionary with simulated calls and puts
    """
    # Get current stock price
    stock_price = get_current_price(symbol)
    if not stock_price:
        stock_price = 100.0  # Default price if we can't get real price
        
    # Generate expiration 30 days from now
    expiration = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Generate strikes around the current price
    strikes = [round(stock_price * (1 + i * 0.05), 2) for i in range(-5, 6)]
    
    calls = []
    puts = []
    
    for strike in strikes:
        # Generate call option
        call_price = round(max(0, stock_price - strike) + 2.0, 2)
        call = {
            "symbol": f"{symbol}{expiration.replace('-', '')}C{int(strike)}000",
            "description": f"{symbol} {expiration} Call {strike}",
            "exch": "SIMU",
            "type": "option",
            "last": call_price,
            "change": 0.0,
            "volume": 100,
            "open": call_price,
            "high": call_price * 1.05,
            "low": call_price * 0.95,
            "close": None,
            "bid": call_price - 0.10,
            "ask": call_price + 0.10,
            "underlying": symbol,
            "strike": strike,
            "greeks": {
                "delta": 0.5,
                "gamma": 0.05,
                "theta": -0.01,
                "vega": 0.1,
                "rho": 0.01,
                "phi": 0.01,
                "bid_iv": 0.3,
                "mid_iv": 0.35,
                "ask_iv": 0.4
            },
            "expiration_date": expiration,
            "expiration_type": "standard",
            "option_type": "call",
            "root_symbol": symbol
        }
        calls.append(call)
        
        # Generate put option
        put_price = round(max(0, strike - stock_price) + 2.0, 2)
        put = {
            "symbol": f"{symbol}{expiration.replace('-', '')}P{int(strike)}000",
            "description": f"{symbol} {expiration} Put {strike}",
            "exch": "SIMU",
            "type": "option",
            "last": put_price,
            "change": 0.0,
            "volume": 100,
            "open": put_price,
            "high": put_price * 1.05,
            "low": put_price * 0.95,
            "close": None,
            "bid": put_price - 0.10,
            "ask": put_price + 0.10,
            "underlying": symbol,
            "strike": strike,
            "greeks": {
                "delta": -0.5,
                "gamma": 0.05,
                "theta": -0.01,
                "vega": 0.1,
                "rho": -0.01,
                "phi": 0.01,
                "bid_iv": 0.3,
                "mid_iv": 0.35,
                "ask_iv": 0.4
            },
            "expiration_date": expiration,
            "expiration_type": "standard",
            "option_type": "put",
            "root_symbol": symbol
        }
        puts.append(put)
    
    logger.info(f"Generated simulated option chain for {symbol}: {len(calls)} calls, {len(puts)} puts")
    
    return {
        "calls": calls,
        "puts": puts,
        "expiration": expiration,
        "simulated": True  # Flag to indicate this is simulated data
    }

def get_current_price(symbol):
    """
    Get the current price for a symbol.
    
    Args:
        symbol (str): Stock symbol to get price for
        
    Returns:
        float: Current price or None if not available
    """
    if not symbol:
        logger.error("No symbol provided for current price retrieval")
        return None
    
    # Set up the API endpoint
    url = f"{TRADIER_BASE_URL}/markets/quotes"
    
    # Set up the request headers and parameters
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "symbols": symbol
    }
    
    # Make the request with retry logic
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if DEBUG_API_RESPONSES:
                logger.info(f"API Response for {symbol} current price: {json.dumps(data, indent=2)}")
            
            if 'quotes' in data and 'quote' in data['quotes']:
                quote = data['quotes']['quote']
                price = quote.get('last')
                
                if price is not None:
                    logger.info(f"Current price for {symbol}: ${price}")
                    return price
                else:
                    logger.warning(f"No price found in quote for {symbol}")
                    return None
            else:
                logger.warning(f"Unexpected response format for {symbol} quote")
                return None
                
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Request failed for {symbol} quote, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to retrieve quote for {symbol} after {MAX_RETRIES} attempts: {e}")
                return None
    
    return None
