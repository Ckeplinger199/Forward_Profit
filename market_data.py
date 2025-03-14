# market_data.py - Fetch market data for analysis and trading
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from config import TRADIER_API_KEY, TRADIER_SANDBOX_KEY, USE_SANDBOX

def get_latest_price_data(symbol, interval="daily", lookback_days=120):
    """
    Fetch historical price data for a symbol from Tradier API.
    
    Args:
        symbol (str): The stock ticker symbol
        interval (str): Data interval - 'daily', 'weekly', or 'monthly'
        lookback_days (int): Number of days to look back (increased to 120 for reliable indicators)
        
    Returns:
        pandas.DataFrame: Historical price data with columns [date, open, high, low, close, volume]
    """
    # Calculate the start date
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    
    # Check for API key
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    if not api_key or api_key == "your_tradier_api_key":
        print(f"No valid Tradier API key found in config.py")
        return pd.DataFrame()
    
    # Set up the API endpoint
    base_url = "https://sandbox.tradier.com/v1" if USE_SANDBOX else "https://api.tradier.com/v1"
    url = f"{base_url}/markets/history"
    
    # Set up the request headers and parameters
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "symbol": symbol,
        "interval": interval,
        "start": start_date,
        "end": end_date
    }
    
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Make the request
            print(f"Fetching price data for {symbol} from {start_date} to {end_date}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            # Check for rate limiting or authorization issues
            if response.status_code == 429:  # Too many requests
                print(f"Rate limited by Tradier API. Waiting before retry...")
                time.sleep(retry_delay * (attempt + 1))
                continue
                
            if response.status_code == 401:  # Unauthorized
                print(f"Authentication error with Tradier API. Check your API key.")
                return pd.DataFrame()
                
            response.raise_for_status()  # Raise an exception for other HTTP errors
            
            # Parse the response
            data = response.json()
            
            # Debug output to understand the structure
            print(f"API response structure: {list(data.keys()) if data else 'Empty response'}")
            
            # Check if data is None or doesn't contain expected keys
            if data is None:
                print(f"No data returned for {symbol}")
                return pd.DataFrame()
                
            if 'history' not in data:
                print(f"No history data in response for {symbol}")
                return pd.DataFrame()
            
            # Some valid responses may not have 'day' data if market is closed or no data available
            if 'day' not in data['history'] or data['history']['day'] is None:
                print(f"No daily data in history for {symbol}")
                return pd.DataFrame()
                
            # Convert to DataFrame
            if isinstance(data['history']['day'], list):
                price_data = pd.DataFrame(data['history']['day'])
            else:
                # Handle case where only a single day is returned (not in a list)
                price_data = pd.DataFrame([data['history']['day']])
            
            # Convert date column to datetime
            price_data['date'] = pd.to_datetime(price_data['date'])
            
            # Sort by date
            price_data = price_data.sort_values('date')
            
            print(f"Successfully fetched {len(price_data)} days of price data for {symbol}")
            return price_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for {symbol} (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return pd.DataFrame()  # Return empty DataFrame after all retries
        except ValueError as e:
            print(f"Error parsing JSON data for {symbol}: {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"Unexpected error processing data for {symbol}: {e}")
            return pd.DataFrame()

def get_option_chain(symbol, expiration=None):
    """
    Fetch option chain data for a symbol from Tradier API.
    
    Args:
        symbol (str): The stock ticker symbol
        expiration (str, optional): Specific expiration date in format YYYY-MM-DD
                                   If None, fetches the nearest expiration
    
    Returns:
        dict: Option chain data containing calls and puts
    """
    # Check for API key
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    if not api_key or api_key == "your_tradier_api_key":
        print(f"No valid Tradier API key found in config.py")
        return {}
    
    # Set up the API endpoint
    base_url = "https://sandbox.tradier.com/v1" if USE_SANDBOX else "https://api.tradier.com/v1"
    
    # First, get available expirations if not specified
    if expiration is None:
        exp_url = f"{base_url}/markets/options/expirations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        params = {"symbol": symbol, "includeAllRoots": "true"}
        
        try:
            print(f"Fetching option expiration dates for {symbol}")
            exp_response = requests.get(exp_url, headers=headers, params=params, timeout=10)
            exp_response.raise_for_status()
            
            exp_data = exp_response.json()
            print(f"Expiration response structure: {list(exp_data.keys()) if exp_data else 'Empty response'}")
            
            if 'expirations' not in exp_data:
                print(f"No expirations data found for {symbol}")
                return {}
                
            if 'expiration' not in exp_data['expirations'] or not exp_data['expirations']['expiration']:
                print(f"No expiration dates available for {symbol}")
                return {}
                
            # Get the nearest expiration
            expiration = exp_data['expirations']['expiration'][0]
            print(f"Using nearest expiration date: {expiration} for {symbol}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching expiration dates for {symbol}: {e}")
            return {}
    
    # Now get the option chain
    chain_url = f"{base_url}/markets/options/chains"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "symbol": symbol,
        "expiration": expiration
    }
    
    try:
        print(f"Fetching option chain for {symbol} with expiration {expiration}")
        chain_response = requests.get(chain_url, headers=headers, params=params, timeout=10)
        chain_response.raise_for_status()
        
        chain_data = chain_response.json()
        print(f"Chain response structure: {list(chain_data.keys()) if chain_data else 'Empty response'}")
        
        if 'options' not in chain_data:
            print(f"No options data found in response for {symbol}")
            return {}
            
        if 'option' not in chain_data['options'] or not chain_data['options']['option']:
            print(f"No option contracts found for {symbol} with expiration {expiration}")
            return {}
            
        # Separate into calls and puts
        options = chain_data['options']['option']
        calls = [opt for opt in options if opt['option_type'] == 'call']
        puts = [opt for opt in options if opt['option_type'] == 'put']
        
        print(f"Found {len(calls)} call and {len(puts)} put options for {symbol}")
        return {"calls": calls, "puts": puts, "expiration": expiration}
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching option chain for {symbol}: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error processing option data for {symbol}: {e}")
        return {}

def get_latest_quote(symbol):
    """
    Fetch the latest quote for a symbol from Tradier API.
    
    Args:
        symbol (str): The stock ticker symbol
        
    Returns:
        dict: Latest quote data
    """
    # Check for API key
    api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
    if not api_key or api_key == "your_tradier_api_key":
        print(f"No valid Tradier API key found in config.py")
        return {}
    
    # Set up the API endpoint
    base_url = "https://sandbox.tradier.com/v1" if USE_SANDBOX else "https://api.tradier.com/v1"
    url = f"{base_url}/markets/quotes"
    
    # Set up the request headers and parameters
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "symbols": symbol
    }
    
    try:
        # Make the request
        print(f"Fetching latest quote for {symbol}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        print(f"Quote response structure: {list(data.keys()) if data else 'Empty response'}")
        
        if 'quotes' not in data:
            print(f"No quotes data found in response for {symbol}")
            return {}
            
        if 'quote' not in data['quotes']:
            print(f"No quote found for {symbol}")
            return {}
            
        return data['quotes']['quote']
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching quote for {symbol}: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error processing quote for {symbol}: {e}")
        return {}
