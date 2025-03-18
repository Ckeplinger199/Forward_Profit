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
        return {"calls": [], "puts": [], "expiration": expiration}
    
    # Set up the API endpoint
    url = f"{TRADIER_BASE_URL}/markets/options/chains"
    
    # Set up the request headers and parameters
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "symbol": symbol
    }
    
    # Greeks are not available in sandbox mode according to documentation
    if not USE_SANDBOX:
        params["greeks"] = "true"
    
    if expiration:
        params["expiration"] = expiration
    
    # Make the request with retry logic
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if DEBUG_API_RESPONSES:
                logger.info(f"API Response for {symbol} option chain: {json.dumps(data, indent=2)}")
            
            if 'options' in data and data['options'] is not None:
                if 'option' in data['options']:
                    options = data['options']['option']
                    
                    # Extract expiration date
                    if options and len(options) > 0:
                        expiration = options[0]['expiration_date']
                    
                    # Separate calls and puts
                    calls = [option for option in options if option['option_type'] == 'call']
                    puts = [option for option in options if option['option_type'] == 'put']
                    
                    logger.info(f"Retrieved option chain for {symbol}: {len(calls)} calls, {len(puts)} puts")
                    
                    return {
                        "calls": calls,
                        "puts": puts,
                        "expiration": expiration
                    }
                else:
                    logger.warning(f"No options found for {symbol} with expiration {expiration}")
                    return {"calls": [], "puts": [], "expiration": expiration}
            else:
                logger.warning(f"No options data found for {symbol} with expiration {expiration}")
                return {"calls": [], "puts": [], "expiration": expiration}
                
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Request failed for {symbol} option chain, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to retrieve option chain for {symbol} after {MAX_RETRIES} attempts: {e}")
                return {"calls": [], "puts": [], "expiration": expiration}
    
    return {"calls": [], "puts": [], "expiration": expiration}

def handle_missing_option_data(symbol, reason="API failure"):
    """
    Handle cases where option data is not available
    
    Args:
        symbol (str): Stock symbol that's missing option data
        reason (str): Reason for missing data
        
    Returns:
        dict: Empty option chain structure with error information
    """
    logger.error(f"No option data available for {symbol}: {reason}")
    
    # Return a properly structured empty result
    return {
        "calls": [],
        "puts": [],
        "expiration": None,
        "error": f"No option data available: {reason}"
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

def validate_option_symbol(option_symbol, underlying_symbol=None):
    """
    Validates if an option symbol exists in the Tradier API
    
    Args:
        option_symbol (str): The option symbol to validate (e.g., 'SPY220617C00400000')
        underlying_symbol (str, optional): The underlying symbol, extracted from option_symbol if not provided
        
    Returns:
        tuple: (is_valid, valid_alternative, expiration_date)
            - is_valid (bool): True if the option symbol is valid
            - valid_alternative (str): A valid similar option if original not found (or None)
            - expiration_date (str): The expiration date of the option in YYYY-MM-DD format
    """
    # Extract underlying symbol if not provided
    if not underlying_symbol:
        underlying_symbol = ""
        for char in option_symbol:
            if not char.isdigit():
                underlying_symbol += char
            else:
                break
        # Remove trailing non-alphanumeric characters (like C or P for call/put)
        underlying_symbol = ''.join(c for c in underlying_symbol if c.isalnum())
    
    # Extract option parameters
    try:
        # Format is: Symbol + YYMMDD + C/P + StrikePrice
        date_start = len(underlying_symbol)
        date_portion = option_symbol[date_start:date_start+6]  # YYMMDD
        option_type = option_symbol[date_start+6:date_start+7]  # C or P
        strike_portion = option_symbol[date_start+7:]  # Strike price digits
        
        # Convert date to YYYY-MM-DD format for API
        year = int("20" + date_portion[0:2])
        month = int(date_portion[2:4])
        day = int(date_portion[4:6])
        expiration_date = f"{year}-{month:02d}-{day:02d}"
        
        # Convert strike price to float (divide by 1000 to get actual price)
        strike_price = float(strike_portion) / 1000
        
        logger.info(f"Validating option: {underlying_symbol}, {expiration_date}, {option_type}, {strike_price}")
    except Exception as e:
        logger.error(f"Failed to parse option symbol {option_symbol}: {e}")
        return False, None, None
    
    # In sandbox mode, we may want to allow trading even without validation
    # This helps with testing when the sandbox API doesn't return real option chains
    if USE_SANDBOX and ENABLE_SANDBOX_FALLBACK:
        logger.info(f"Sandbox mode with fallback enabled - allowing option symbol {option_symbol} without validation")
        return True, option_symbol, expiration_date
    
    # Get option chain for this expiration
    option_chain = get_option_chain(underlying_symbol, expiration_date)
    if not option_chain:
        logger.warning(f"No option chain found for {underlying_symbol} with expiration {expiration_date}")
        # In sandbox mode, be more lenient with validation
        if USE_SANDBOX:
            logger.info(f"Sandbox mode - allowing option symbol {option_symbol} despite missing chain")
            return True, option_symbol, expiration_date
        return False, None, expiration_date
    
    # Check if the chain is empty or null
    if 'calls' not in option_chain or 'puts' not in option_chain:
        logger.warning(f"Invalid option chain response for {underlying_symbol} with expiration {expiration_date}")
        # In sandbox mode, be more lenient with validation
        if USE_SANDBOX:
            logger.info(f"Sandbox mode - allowing option symbol {option_symbol} despite invalid chain")
            return True, option_symbol, expiration_date
        return False, None, expiration_date
    
    # Determine which side of the chain to check
    chain_side = "calls" if option_type.upper() == "C" else "puts"
    if chain_side not in option_chain or not option_chain[chain_side]:
        logger.warning(f"No {chain_side} found in option chain for {underlying_symbol}")
        # In sandbox mode, be more lenient with validation
        if USE_SANDBOX:
            logger.info(f"Sandbox mode - allowing option symbol {option_symbol} despite missing {chain_side}")
            return True, option_symbol, expiration_date
        return False, None, expiration_date
    
    # Check if the exact option symbol exists
    for option in option_chain[chain_side]:
        if option.get('symbol') == option_symbol:
            logger.info(f"Option symbol {option_symbol} validated successfully")
            return True, option_symbol, expiration_date
    
    # If we didn't find an exact match, find the closest strike price
    closest_option = None
    min_diff = float('inf')
    
    for option in option_chain[chain_side]:
        if abs(option.get('strike', 0) - strike_price) < min_diff:
            min_diff = abs(option.get('strike', 0) - strike_price)
            closest_option = option
    
    if closest_option:
        alternative_symbol = closest_option.get('symbol')
        logger.info(f"Option symbol {option_symbol} not found, but found similar option: {alternative_symbol}")
        return False, alternative_symbol, expiration_date
    
    # In sandbox mode, be more lenient if no alternative was found
    if USE_SANDBOX:
        logger.info(f"Sandbox mode - allowing option symbol {option_symbol} despite no match or alternative")
        return True, option_symbol, expiration_date
        
    return False, None, expiration_date

def lookup_option_symbols(underlying_symbol, expiration=None, strike=None, option_type=None):
    """
    Look up valid option symbols using Tradier's lookup endpoint
    
    Args:
        underlying_symbol (str): The underlying stock symbol
        expiration (str, optional): Option expiration date in YYYY-MM-DD format
        strike (float, optional): Strike price
        option_type (str, optional): Option type ('call' or 'put')
        
    Returns:
        list: List of matching option symbols
    """
    logger.info(f"Looking up option symbols for {underlying_symbol}")
    
    # Set up the API endpoint
    url = f"{TRADIER_BASE_URL}/markets/options/lookup"
    
    # Set up the request headers and parameters
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "underlying": underlying_symbol
    }
    
    if expiration:
        params["expiration"] = expiration
    if strike:
        params["strike"] = strike
    if option_type and option_type.lower() in ['call', 'put']:
        params["type"] = option_type.lower()
    
    # Make the request with retry logic
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if DEBUG_API_RESPONSES:
                logger.info(f"API Response for option symbol lookup: {json.dumps(data, indent=2)}")
            
            if 'options' in data and data['options'] is not None:
                if 'option' in data['options']:
                    options = data['options']['option']
                    if isinstance(options, list):
                        logger.info(f"Found {len(options)} matching option symbols for {underlying_symbol}")
                        return options
                    else:
                        # Single option returned
                        logger.info(f"Found 1 matching option symbol for {underlying_symbol}")
                        return [options]
            
            # If we reach here, no options were found
            logger.warning(f"No matching option symbols found for {underlying_symbol}")
            return []
                
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Request failed for option symbol lookup, retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to lookup option symbols after {MAX_RETRIES} attempts: {e}")
                return []
    
    return []
