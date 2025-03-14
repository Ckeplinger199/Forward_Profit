# execution.py – Tradier API integration for executing trades
import requests
from config import TRADIER_API_KEY, TRADIER_SANDBOX_KEY, USE_SANDBOX, ACCOUNT_ID

class TradierClient:
    """Client for Tradier API to execute option trades."""
    def __init__(self):
        self.base_url = "https://sandbox.tradier.com/v1" if USE_SANDBOX else "https://api.tradier.com/v1"
        self.session = requests.Session()
        api_key = TRADIER_SANDBOX_KEY if USE_SANDBOX else TRADIER_API_KEY
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        })
    
    def place_option_order(self, account_id, option_symbol, side, quantity=1, order_type="market"):
        """
        Place an order to trade an option contract.
        
        Args:
            account_id (str): Tradier account ID
            option_symbol (str): Full OCC option symbol (e.g., 'SPY_220318C450')
            side (str): 'buy_to_open', 'sell_to_close', etc.
            quantity (int): Number of contracts to trade
            order_type (str): 'market' or 'limit'
            
        Returns:
            dict: Order status and confirmation details
        """
        url = f"{self.base_url}/accounts/{account_id}/orders"
        data = {
            "class": "option",
            "symbol": option_symbol.split("_")[0],  # Extract underlying symbol (e.g., 'SPY')
            "option_symbol": option_symbol,         # Full OCC option symbol
            "side": side,                           # e.g., 'buy_to_open'
            "quantity": quantity,
            "type": order_type,
            "duration": "day"
        }
        
        try:
            response = self.session.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error placing option order: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_account_positions(self, account_id):
        """
        Get current positions in the account.
        
        Args:
            account_id (str): Tradier account ID
            
        Returns:
            list: Current positions in the account
        """
        url = f"{self.base_url}/accounts/{account_id}/positions"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if 'positions' not in data or data['positions'] == 'null':
                return []
                
            positions = data['positions']['position']
            # Ensure positions is a list (API returns a dict if only one position)
            if not isinstance(positions, list):
                positions = [positions]
                
            return positions
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving account positions: {e}")
            return []
    
    def get_account_balances(self, account_id):
        """
        Get account balances.
        
        Args:
            account_id (str): Tradier account ID
            
        Returns:
            dict: Account balance information
        """
        url = f"{self.base_url}/accounts/{account_id}/balances"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json().get('balances', {})
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving account balances: {e}")
            return {}
