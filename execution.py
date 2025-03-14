# execution.py – Tradier API integration for executing trades
import requests
import json
import logging
import time
from config import (TRADIER_API_KEY, TRADIER_SANDBOX_KEY, USE_SANDBOX, ACCOUNT_ID,
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
logger = logging.getLogger("execution")

class TradierClient:
    """Client for interacting with Tradier API for trade execution"""
    
    def __init__(self):
        """Initialize the Tradier client with API credentials"""
        self.base_url = TRADIER_BASE_URL
        self.session = requests.Session()
        self.api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
        self.account_id = ACCOUNT_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        logger.info(f"Initialized TradierClient in {'sandbox' if USE_SANDBOX else 'production'} mode")
        
    def get_account_balances(self):
        """
        Get account balances
        
        Returns:
            dict: Account balance information
        """
        url = f"{self.base_url}/accounts/{self.account_id}/balances"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Response for account balances: {json.dumps(data, indent=2)}")
                
                if 'balances' in data:
                    logger.info(f"Successfully retrieved account balances")
                    return data['balances']
                else:
                    logger.warning(f"Unexpected response format for account balances: {data}")
                    return {}
                    
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for account balances, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to retrieve account balances after {MAX_RETRIES} attempts: {e}")
                    if ENABLE_SANDBOX_FALLBACK and USE_SANDBOX:
                        logger.warning("Using simulated account balances for sandbox testing")
                        return self._generate_simulated_balances()
                    return {}
        
        return {}
    
    def get_account_positions(self):
        """
        Get current account positions
        
        Returns:
            list: List of current positions
        """
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Response for account positions: {json.dumps(data, indent=2)}")
                
                if 'positions' in data:
                    if 'position' in data['positions']:
                        positions = data['positions']['position']
                        # Handle case where only one position is returned (not in a list)
                        if not isinstance(positions, list):
                            positions = [positions]
                        logger.info(f"Successfully retrieved {len(positions)} positions")
                        return positions
                    else:
                        logger.info("No positions found in account")
                        return []
                else:
                    logger.warning(f"Unexpected response format for positions: {data}")
                    return []
                    
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for positions, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to retrieve positions after {MAX_RETRIES} attempts: {e}")
                    if ENABLE_SANDBOX_FALLBACK and USE_SANDBOX:
                        logger.warning("Using simulated positions for sandbox testing")
                        return self._generate_simulated_positions()
                    return []
        
        return []
    
    def place_order(self, order_data):
        """
        Place an order
        
        Args:
            order_data (dict): Order details including:
                - symbol: The underlying symbol (for options)
                - option_symbol: The option symbol (for options)
                - side: 'buy_to_open', 'sell_to_close', etc. for options
                - quantity: Number of contracts/shares
                - type: 'market', 'limit', 'stop', etc.
                - price: Limit price (if applicable)
                - stop: Stop price (if applicable)
                - duration: 'day', 'gtc', etc.
                - class: 'option' for option orders
        
        Returns:
            dict: Order confirmation details
        """
        url = f"{self.base_url}/accounts/{self.account_id}/orders"
        
        # Validate required fields based on order class
        if order_data.get('class') == 'option':
            required_fields = ['class', 'symbol', 'option_symbol', 'side', 'quantity', 'type', 'duration']
        else:
            required_fields = ['symbol', 'side', 'quantity', 'type', 'duration']
            
        for field in required_fields:
            if field not in order_data:
                logger.error(f"Missing required field '{field}' in order data")
                return {"error": f"Missing required field: {field}"}
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.post(url, headers=self.headers, data=order_data)
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Request for order placement: {order_data}")
                    
                response.raise_for_status()
                data = response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Response for order placement: {json.dumps(data, indent=2)}")
                
                if 'order' in data:
                    symbol_to_log = order_data.get('option_symbol', order_data.get('symbol', 'unknown'))
                    logger.info(f"Successfully placed order: {symbol_to_log} {order_data['side']} {order_data['quantity']}")
                    return data['order']
                else:
                    logger.warning(f"Unexpected response format for order placement: {data}")
                    return {"error": "Unexpected response format"}
                    
            except requests.exceptions.HTTPError as e:
                # Handle specific error codes
                if e.response.status_code == 400:
                    try:
                        error_data = e.response.json()
                        logger.error(f"Order validation error: {e} {error_data}")
                        return {"error": f"Order validation error: {error_data.get('fault', {}).get('message', str(e))}"}
                    except:
                        logger.error(f"Order validation error: {e}")
                        return {"error": f"Order validation error: {str(e)}"}
                
                if attempt < MAX_RETRIES - 1 and e.response.status_code in [429, 500, 502, 503, 504]:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for order placement, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to place order after {attempt+1} attempts: {e}")
                    return {"error": f"Failed to place order: {str(e)}"}
            
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for order placement, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to place order after {MAX_RETRIES} attempts: {e}")
                    return {"error": f"Failed to place order: {str(e)}"}
        
        return {"error": "Maximum retry attempts exceeded"}
    
    def place_option_order(self, option_symbol=None, symbol=None, side='buy_to_open', quantity=1, price=None, duration='day'):
        """
        Place an option order
        
        Args:
            option_symbol (str): The full option symbol in Tradier format (e.g. SPY220617C00400000)
            symbol (str): The underlying symbol (e.g. SPY) - required if option_symbol is provided
            side (str): 'buy_to_open', 'sell_to_close', etc.
            quantity (int): Number of contracts
            price (float): Limit price (optional)
            duration (str): 'day' or 'gtc'
        """
        # Ensure we have both the underlying symbol and option symbol
        if not option_symbol:
            logger.error("Option symbol is required for option orders")
            return {"error": "Option symbol is required"}
            
        if not symbol:
            # Try to extract the underlying symbol from the option symbol
            if option_symbol:
                # Option symbols start with the underlying symbol
                # Extract letters until we hit a digit
                symbol = ""
                for char in option_symbol:
                    if not char.isdigit():
                        symbol += char
                    else:
                        break
                        
                # Remove any trailing non-alphanumeric characters
                symbol = ''.join(c for c in symbol if c.isalnum())
                
                logger.info(f"Extracted underlying symbol '{symbol}' from option symbol '{option_symbol}'")
            else:
                logger.error("Either symbol or option_symbol must be provided")
                return {"error": "Either symbol or option_symbol must be provided"}
        
        order_data = {
            'class': 'option',
            'symbol': symbol,
            'option_symbol': option_symbol,
            'side': side,
            'quantity': quantity,
            'type': 'market' if price is None else 'limit',
            'duration': duration
        }
        
        if price is not None:
            order_data['price'] = price
            
        return self.place_order(order_data)
    
    def get_order_status(self, order_id):
        """
        Get the status of a specific order
        
        Args:
            order_id (str): The ID of the order to check
            
        Returns:
            dict: Order status details
        """
        url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Response for order status: {json.dumps(data, indent=2)}")
                
                if 'order' in data:
                    logger.info(f"Successfully retrieved status for order {order_id}: {data['order'].get('status')}")
                    return data['order']
                else:
                    logger.warning(f"Unexpected response format for order status: {data}")
                    return {"error": "Unexpected response format"}
                    
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for order status, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to get order status after {MAX_RETRIES} attempts: {e}")
                    return {"error": f"Failed to get order status: {str(e)}"}
        
        return {"error": "Maximum retry attempts exceeded"}
    
    def get_option_chains(self, symbol, expiration=None):
        """
        Get option chains for a symbol
        
        Args:
            symbol (str): The underlying symbol
            expiration (str, optional): Expiration date in YYYY-MM-DD format
            
        Returns:
            dict: Option chain data
        """
        base_url = "https://sandbox.tradier.com/v1/markets/options/chains" if USE_SANDBOX else "https://api.tradier.com/v1/markets/options/chains"
        
        params = {
            'symbol': symbol,
            'greeks': 'false'
        }
        
        if expiration:
            params['expiration'] = expiration
            
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(base_url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Response for option chains: {json.dumps(data, indent=2)}")
                
                if 'options' in data and 'option' in data['options']:
                    logger.info(f"Successfully retrieved option chains for {symbol}")
                    return data['options']['option']
                elif 'options' in data and data['options'] == []:
                    logger.warning(f"No options available for {symbol}")
                    return []
                else:
                    logger.warning(f"Unexpected response format for option chains: {data}")
                    return {"error": "Unexpected response format"}
                    
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for option chains, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to get option chains after {MAX_RETRIES} attempts: {e}")
                    return {"error": f"Failed to get option chains: {str(e)}"}
        
        return {"error": "Maximum retry attempts exceeded"}
    
    def get_expirations(self, symbol):
        """
        Get available option expiration dates for a symbol
        
        Args:
            symbol (str): The underlying symbol
            
        Returns:
            list: Available expiration dates
        """
        base_url = "https://sandbox.tradier.com/v1/markets/options/expirations" if USE_SANDBOX else "https://api.tradier.com/v1/markets/options/expirations"
        
        params = {
            'symbol': symbol,
            'includeAllRoots': 'true'
        }
            
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(base_url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Response for expirations: {json.dumps(data, indent=2)}")
                
                if 'expirations' in data and 'date' in data['expirations']:
                    logger.info(f"Successfully retrieved expirations for {symbol}")
                    return data['expirations']['date']
                elif 'expirations' in data and data['expirations'] == []:
                    logger.warning(f"No expirations available for {symbol}")
                    return []
                else:
                    logger.warning(f"Unexpected response format for expirations: {data}")
                    return {"error": "Unexpected response format"}
                    
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for expirations, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to get expirations after {MAX_RETRIES} attempts: {e}")
                    return {"error": f"Failed to get expirations: {str(e)}"}
        
        return {"error": "Maximum retry attempts exceeded"}
    
    def _generate_simulated_balances(self):
        """Generate simulated account balances for sandbox testing"""
        return {
            "option_short_value": 0.0,
            "total_equity": 25000.0,
            "account_number": self.account_id,
            "account_type": "margin",
            "close_pl": 0.0,
            "current_requirement": 0.0,
            "equity": 25000.0,
            "long_market_value": 0.0,
            "market_value": 0.0,
            "open_pl": 0.0,
            "option_long_value": 0.0,
            "option_requirement": 0.0,
            "pending_orders_count": 0,
            "short_market_value": 0.0,
            "stock_long_value": 0.0,
            "total_cash": 25000.0,
            "uncleared_funds": 0.0,
            "pending_cash": 0.0,
            "margin": {
                "fed_call": 0.0,
                "maintenance_call": 0.0,
                "option_buying_power": 25000.0,
                "stock_buying_power": 50000.0,
                "stock_short_value": 0.0,
                "sweep": 0.0
            }
        }
    
    def _generate_simulated_positions(self):
        """Generate simulated positions for sandbox testing"""
        return []  # Empty positions for now, could add sample positions if needed
