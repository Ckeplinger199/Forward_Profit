# test_order.py - Test script for placing option orders with Tradier API
import sys
import os
import logging
import json
from datetime import datetime, timedelta

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution import TradierClient
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_order.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_order")

def create_test_price_data(symbol="SPY", days=30, start_price=400):
    """Create fake price data for testing"""
    dates = [datetime.now() - timedelta(days=i) for i in range(days)]
    prices = [start_price + (i % 10) for i in range(days)]
    
    data = {
        'date': dates,
        'open': prices,
        'high': [p + 2 for p in prices],
        'low': [p - 2 for p in prices],
        'close': [p + (i % 5 - 2) for i, p in enumerate(prices)],
        'volume': [1000000 + (i * 10000) for i in range(days)]
    }
    
    return pd.DataFrame(data)

def get_valid_option_contract(tradier, symbol="SPY", option_type="call"):
    """Get a valid option contract from Tradier API"""
    # Get available expirations
    expirations = tradier.get_expirations(symbol)
    if isinstance(expirations, dict) and "error" in expirations:
        logger.error(f"Failed to get expirations: {expirations['error']}")
        return None
    
    if not expirations:
        logger.error(f"No expirations available for {symbol}")
        return None
    
    # Use the first expiration date
    expiration = expirations[0]
    logger.info(f"Using expiration date: {expiration}")
    
    # Get option chain for this expiration
    options = tradier.get_option_chains(symbol, expiration)
    if isinstance(options, dict) and "error" in options:
        logger.error(f"Failed to get option chain: {options['error']}")
        return None
    
    if not options:
        logger.error(f"No options available for {symbol} with expiration {expiration}")
        return None
    
    # Filter by option type
    filtered_options = [opt for opt in options if opt['option_type'] == option_type]
    if not filtered_options:
        logger.error(f"No {option_type} options found for {symbol}")
        return None
    
    # Pick an option near the money
    option = filtered_options[len(filtered_options) // 2]
    logger.info(f"Selected option: {json.dumps(option, indent=2)}")
    
    return option['symbol']

def test_option_order():
    """Test placing an option order with the Tradier API"""
    logger.info("Starting option order test")
    
    # Initialize Tradier client
    tradier = TradierClient()
    logger.info("Tradier client initialized")
    
    # Get a valid option contract
    symbol = "SPY"
    option_type = "call"
    contract = get_valid_option_contract(tradier, symbol, option_type)
    
    if not contract:
        logger.error("Could not get a valid option contract. Test aborted.")
        return {"error": "No valid option contract available"}
    
    logger.info(f"Selected option contract: {contract}")
    
    # Place test order
    logger.info("Attempting to place option order...")
    result = tradier.place_option_order(
        option_symbol=contract,
        symbol=symbol,
        side="buy_to_open",
        quantity=1,
        duration="day"
    )
    
    # Log result
    if isinstance(result, dict) and "error" in result:
        logger.error(f"Order failed: {result['error']}")
    else:
        logger.info(f"Order placed successfully: {result}")
    
    return result

if __name__ == "__main__":
    test_result = test_option_order()
    print("\nTest Result:")
    print(test_result)
