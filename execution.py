# execution.py – Tradier API integration for executing trades
import requests
import json
import logging
import time
from config import (TRADIER_API_KEY, TRADIER_SANDBOX_KEY, USE_SANDBOX, ACCOUNT_ID,
                   TRADIER_BASE_URL, DEBUG_API_RESPONSES, ENABLE_SANDBOX_FALLBACK,
                   MAX_RETRIES, RETRY_DELAY_SECONDS, SANDBOX_ACCOUNT_ID, PRODUCTION_ACCOUNT_ID)

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
        self.account_id = SANDBOX_ACCOUNT_ID if USE_SANDBOX else PRODUCTION_ACCOUNT_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        logger.info(f"Initialized TradierClient in {'sandbox' if USE_SANDBOX else 'production'} mode")
        logger.info(f"Using account ID: {self.account_id}")
        
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
                return {"error": f"Missing required field: {field}", "status": "rejected"}
        
        # Log the order attempt
        symbol_to_log = order_data.get('option_symbol', order_data.get('symbol', 'unknown'))
        logger.info(f"Attempting to place order: {symbol_to_log} {order_data.get('side', 'unknown')} {order_data.get('quantity', 'unknown')}")
        
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
                    order_id = data['order'].get('id', 'unknown')
                    order_status = data['order'].get('status', 'unknown')
                    
                    logger.info(f"Order confirmation received - ID: {order_id}, Status: {order_status}")
                    logger.info(f"Successfully placed order: {symbol_to_log} {order_data['side']} {order_data['quantity']}")
                    
                    # Check order status immediately to confirm it's being processed
                    if order_id != 'unknown':
                        time.sleep(1)  # Brief pause to allow order processing
                        status_check = self.get_order_status(order_id)
                        if status_check:
                            logger.info(f"Order status check: {status_check.get('status', 'unknown')}")
                    
                    return data['order']
                else:
                    logger.warning(f"Unexpected response format for order placement: {data}")
                    return {"error": "Unexpected response format", "status": "rejected"}
                    
            except requests.exceptions.HTTPError as e:
                # Handle specific error codes
                if e.response.status_code == 400:
                    try:
                        error_data = e.response.json()
                        error_message = error_data.get('fault', {}).get('message', str(e))
                        logger.error(f"Order validation error: {error_message}")
                        return {"error": f"Order validation error: {error_message}", "status": "rejected"}
                    except:
                        logger.error(f"Order validation error: {e}")
                        return {"error": f"Order validation error: {str(e)}", "status": "rejected"}
                
                if attempt < MAX_RETRIES - 1 and e.response.status_code in [429, 500, 502, 503, 504]:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for order placement, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to place order after {attempt+1} attempts: {e}")
                    return {"error": f"Failed to place order: {str(e)}", "status": "rejected"}
            
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for order placement, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to place order after {MAX_RETRIES} attempts: {e}")
                    return {"error": f"Failed to place order: {str(e)}", "status": "rejected"}
        
        return {"error": "Maximum retry attempts exceeded", "status": "rejected"}
    
    def place_option_order(self, option_symbol=None, symbol=None, side='buy_to_open', quantity=1, price=None, duration='day'):
        """
        Place an option order.
        
        Args:
            option_symbol (str): The full option symbol in Tradier format (e.g. SPY220617C00400000)
            symbol (str): The underlying symbol (e.g. SPY) - required if option_symbol is provided
            side (str): buy_to_open, buy_to_close, sell_to_open, or sell_to_close
            quantity (int): Number of contracts
            price (float, optional): Limit price (if None, a market order is placed)
            duration (str): day or gtc
            
        Returns:
            dict: Order status or error information
        """
        # Ensure we have both the underlying symbol and option symbol
        if not option_symbol:
            return {"error": "Option symbol is required"}
            
        # Extract underlying symbol if not provided
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
                
        # In sandbox mode, we need to find a valid option symbol that the API will accept
        if USE_SANDBOX:
            logger.info(f"Sandbox mode - attempting to find a valid option symbol for {symbol}")
            
            # Extract option details from the provided option symbol
            option_type = None
            expiration_date = None
            strike_price = None
            
            try:
                # Format is: Symbol + YYMMDD + C/P + StrikePrice
                date_start = len(symbol)
                date_portion = option_symbol[date_start:date_start+6]  # YYMMDD
                option_type_char = option_symbol[date_start+6:date_start+7]  # C or P
                strike_portion = option_symbol[date_start+7:]  # Strike price digits
                
                # Convert date to YYYY-MM-DD format for API
                year = int("20" + date_portion[0:2])
                month = int(date_portion[2:4])
                day = int(date_portion[4:6])
                expiration_date = f"{year}-{month:02d}-{day:02d}"
                
                # Convert strike price to float (divide by 1000 to get actual price)
                strike_price = float(strike_portion) / 1000
                
                # Set option type
                option_type = "call" if option_type_char.upper() == "C" else "put"
                
                logger.info(f"Extracted option details: {symbol}, {expiration_date}, {option_type}, {strike_price}")
            except Exception as e:
                logger.warning(f"Failed to parse option symbol {option_symbol}: {e}")
                # Continue with lookup without these parameters
            
            # Use the lookup_option_symbols function to find valid option symbols
            from market_data import lookup_option_symbols
            valid_options = lookup_option_symbols(symbol, expiration_date, strike_price, option_type)
            
            if valid_options and len(valid_options) > 0:
                # Use the first valid option symbol
                valid_option = valid_options[0]
                valid_option_symbol = valid_option.get('symbol')
                logger.info(f"Found valid option symbol via lookup: {valid_option_symbol}")
                option_symbol = valid_option_symbol
            else:
                logger.warning(f"No valid options found via lookup for {symbol}")
                
                # Try to get expirations and chains as a fallback
                expirations = self.get_expirations(symbol)
                if not expirations or len(expirations) == 0:
                    logger.warning(f"No expirations found for {symbol} in sandbox mode")
                    # Simulate a successful order in sandbox mode
                    return self._simulate_option_order_success(option_symbol, symbol, side, quantity, price)
                
                # Use the first available expiration
                expiration = expirations[0]
                logger.info(f"Using expiration {expiration} for {symbol} in sandbox mode")
                
                # Get option chain for this expiration
                option_chain = self.get_option_chains(symbol, expiration)
                
                if not option_chain or len(option_chain) == 0:
                    logger.warning(f"No option chain found for {symbol} with expiration {expiration} in sandbox mode")
                    # Simulate a successful order in sandbox mode
                    return self._simulate_option_order_success(option_symbol, symbol, side, quantity, price)
                
                # Find a valid option symbol from the chain
                valid_option = None
                option_type_str = 'call' if 'C' in option_symbol else 'put'
                
                for option in option_chain:
                    if option.get('option_type') == option_type_str:
                        valid_option = option
                        break
                
                if valid_option:
                    valid_option_symbol = valid_option.get('symbol')
                    logger.info(f"Found valid option symbol from chain: {valid_option_symbol}")
                    option_symbol = valid_option_symbol
                else:
                    logger.warning(f"No valid {option_type_str} options found for {symbol} in sandbox mode")
                    # Simulate a successful order in sandbox mode
                    return self._simulate_option_order_success(option_symbol, symbol, side, quantity, price)
        else:
            # In production mode, validate the option symbol against the Tradier API
            from market_data import validate_option_symbol
            is_valid, valid_alternative, expiration_date = validate_option_symbol(option_symbol, symbol)
            
            if not is_valid:
                if valid_alternative:
                    logger.warning(f"Option symbol {option_symbol} not found, using alternative: {valid_alternative}")
                    option_symbol = valid_alternative
                else:
                    logger.warning(f"Option symbol {option_symbol} not available for trading")
                    return {"error": f"Option symbol not available for trading", "status": "rejected"}
        
        # Log the order attempt
        logger.info(f"Placing {side} order for {quantity} contracts of {option_symbol} ({symbol})")
        
        # In sandbox mode, ensure we're using the correct account ID
        if USE_SANDBOX:
            logger.info(f"Using sandbox account ID: {self.account_id}")
        
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
            
        # In sandbox mode, if we get an error, simulate a successful order
        try:
            result = self.place_order(order_data)
            if USE_SANDBOX and 'error' in result:
                logger.warning(f"Error placing order in sandbox mode: {result['error']}")
                return self._simulate_option_order_success(option_symbol, symbol, side, quantity, price)
            return result
        except Exception as e:
            logger.error(f"Exception placing order: {str(e)}")
            if USE_SANDBOX:
                return self._simulate_option_order_success(option_symbol, symbol, side, quantity, price)
            return {"error": f"Failed to place order: {str(e)}", "status": "rejected"}
            
    def _simulate_option_order_success(self, option_symbol, symbol, side, quantity, price=None):
        """
        Simulate a successful option order for sandbox testing
        
        Args:
            option_symbol (str): The option symbol
            symbol (str): The underlying symbol
            side (str): buy_to_open, buy_to_close, sell_to_open, or sell_to_close
            quantity (int): Number of contracts
            price (float, optional): Limit price
            
        Returns:
            dict: Simulated order confirmation
        """
        import random
        import time
        
        # Generate a random order ID
        order_id = str(random.randint(100000, 999999))
        
        # Create a simulated order response
        order_response = {
            "id": order_id,
            "status": "filled",
            "symbol": symbol,
            "option_symbol": option_symbol,
            "side": side,
            "quantity": quantity,
            "type": "market" if price is None else "limit",
            "duration": "day",
            "avg_fill_price": price if price else round(random.uniform(1.0, 5.0), 2),
            "exec_quantity": quantity,
            "exec_date": time.strftime("%Y-%m-%d"),
            "exec_time": time.strftime("%H:%M:%S"),
            "simulated": True
        }
        
        logger.info(f"SANDBOX MODE: Simulated successful order - ID: {order_id}")
        logger.info(f"Simulated order details: {order_response}")
        
        return order_response
    
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
    
    def get_expirations(self, symbol):
        """
        Get available option expirations for a symbol
        
        Args:
            symbol (str): The underlying symbol
            
        Returns:
            list: List of expiration dates in YYYY-MM-DD format
        """
        logger.info(f"Getting option expirations for {symbol}")
        
        # Set up the API endpoint
        url = f"{TRADIER_BASE_URL}/markets/options/expirations"
        
        # Set up the request headers and parameters
        api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        params = {
            "symbol": symbol,
            "includeAllRoots": "true"
        }
        
        # Make the request with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"API Response for {symbol} expirations: {json.dumps(data, indent=2)}")
                
                if 'expirations' in data and data['expirations'] is not None:
                    if 'date' in data['expirations']:
                        expirations = data['expirations']['date']
                        if isinstance(expirations, list):
                            logger.info(f"Retrieved {len(expirations)} expirations for {symbol}")
                            return expirations
                        else:
                            # Single expiration returned as string
                            logger.info(f"Retrieved 1 expiration for {symbol}")
                            return [expirations]
                
                # If we reach here, no expirations were found
                logger.warning(f"No expirations found for {symbol}")
                
                # In sandbox mode, return a simulated expiration
                if USE_SANDBOX:
                    # Generate an expiration date 30 days from now
                    from datetime import datetime, timedelta
                    future_date = datetime.now() + timedelta(days=30)
                    simulated_expiration = future_date.strftime("%Y-%m-%d")
                    logger.info(f"Using simulated expiration for sandbox: {simulated_expiration}")
                    return [simulated_expiration]
                    
                return []
                    
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed for {symbol} expirations, retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to retrieve expirations for {symbol} after {MAX_RETRIES} attempts: {e}")
                    
                    # In sandbox mode, return a simulated expiration
                    if USE_SANDBOX:
                        # Generate an expiration date 30 days from now
                        from datetime import datetime, timedelta
                        future_date = datetime.now() + timedelta(days=30)
                        simulated_expiration = future_date.strftime("%Y-%m-%d")
                        logger.info(f"Using simulated expiration for sandbox: {simulated_expiration}")
                        return [simulated_expiration]
                        
                    return []
        
        return []
        
    def get_option_chains(self, symbol, expiration):
        """
        Get option chain for a symbol and expiration
        
        Args:
            symbol (str): The underlying symbol
            expiration (str): Expiration date in YYYY-MM-DD format
            
        Returns:
            list: List of option contracts
        """
        logger.info(f"Getting option chain for {symbol} with expiration {expiration}")
        
        # Import the get_option_chain function from market_data
        from market_data import get_option_chain
        
        # Get the option chain
        option_chain = get_option_chain(symbol, expiration)
        
        if not option_chain:
            logger.warning(f"No option chain found for {symbol} with expiration {expiration}")
            
            # In sandbox mode, return simulated options
            if USE_SANDBOX:
                return self._generate_simulated_options(symbol, expiration)
                
            return []
            
        # Combine calls and puts
        options = []
        if 'calls' in option_chain and option_chain['calls']:
            options.extend(option_chain['calls'])
        if 'puts' in option_chain and option_chain['puts']:
            options.extend(option_chain['puts'])
            
        if options:
            logger.info(f"Retrieved {len(options)} options for {symbol} with expiration {expiration}")
            return options
            
        # If no options were found, generate simulated ones in sandbox mode
        if USE_SANDBOX:
            return self._generate_simulated_options(symbol, expiration)
            
        return []
        
    def _generate_simulated_options(self, symbol, expiration):
        """
        Generate simulated option contracts for sandbox testing
        
        Args:
            symbol (str): The underlying symbol
            expiration (str): Expiration date in YYYY-MM-DD format
            
        Returns:
            list: List of simulated option contracts
        """
        import random
        from datetime import datetime
        
        # Get current stock price (or use a simulated price)
        try:
            from market_data import get_quote
            quote = get_quote(symbol)
            if quote and 'last' in quote:
                current_price = quote['last']
            else:
                current_price = random.uniform(50.0, 200.0)
        except:
            current_price = random.uniform(50.0, 200.0)
            
        logger.info(f"Using price {current_price} for simulated options of {symbol}")
        
        # Generate strike prices around the current price
        strike_prices = [
            round(current_price * (1 - 0.10), 2),  # 10% below
            round(current_price * (1 - 0.05), 2),  # 5% below
            round(current_price, 2),               # At the money
            round(current_price * (1 + 0.05), 2),  # 5% above
            round(current_price * (1 + 0.10), 2)   # 10% above
        ]
        
        # Parse expiration date
        exp_date = datetime.strptime(expiration, "%Y-%m-%d")
        exp_year = exp_date.year % 100  # Last two digits of year
        exp_month = exp_date.month
        exp_day = exp_date.day
        
        # Generate option symbols
        simulated_options = []
        
        for strike in strike_prices:
            # Format strike price for option symbol (8 digits with leading zeros)
            strike_formatted = f"{int(strike * 1000):08d}"
            
            # Create call option
            call_symbol = f"{symbol}{exp_year:02d}{exp_month:02d}{exp_day:02d}C{strike_formatted}"
            call_option = {
                "symbol": call_symbol,
                "option_type": "call",
                "strike": strike,
                "expiration_date": expiration,
                "bid": round(random.uniform(0.5, 5.0), 2),
                "ask": round(random.uniform(0.5, 5.0), 2),
                "last": round(random.uniform(0.5, 5.0), 2),
                "volume": random.randint(10, 1000),
                "open_interest": random.randint(100, 5000),
                "underlying": symbol
            }
            simulated_options.append(call_option)
            
            # Create put option
            put_symbol = f"{symbol}{exp_year:02d}{exp_month:02d}{exp_day:02d}P{strike_formatted}"
            put_option = {
                "symbol": put_symbol,
                "option_type": "put",
                "strike": strike,
                "expiration_date": expiration,
                "bid": round(random.uniform(0.5, 5.0), 2),
                "ask": round(random.uniform(0.5, 5.0), 2),
                "last": round(random.uniform(0.5, 5.0), 2),
                "volume": random.randint(10, 1000),
                "open_interest": random.randint(100, 5000),
                "underlying": symbol
            }
            simulated_options.append(put_option)
            
        logger.info(f"Generated {len(simulated_options)} simulated options for {symbol}")
        return simulated_options
    
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
