# test_market_hours.py - Test script for market hours check in trade execution
import sys
import os
import logging
from datetime import datetime, time

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution import TradierClient
from opportunity_finder import execute_opportunity_trade
from main import is_market_open, EASTERN_TZ

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_market_hours.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_market_hours")

def test_market_hours_check():
    """Test that trades are rejected when market is closed"""
    logger.info("Starting market hours check test")
    
    # Initialize Tradier client
    tradier = TradierClient()
    logger.info("Tradier client initialized")
    
    # Check current market status
    market_open = is_market_open()
    now = datetime.now(EASTERN_TZ)
    logger.info(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"Market is {'OPEN' if market_open else 'CLOSED'}")
    
    # Test trade execution
    ticker = "SPY"
    contract = "SPY250321C00450000"  # Example contract
    signal = "BUY_CALL"
    
    logger.info(f"Attempting to execute trade for {ticker} ({contract})")
    result = execute_opportunity_trade(
        ticker=ticker,
        contract=contract,
        signal=signal,
        tradier_client=tradier,
        num_contracts=1
    )
    
    # Check result
    if result and "error" in result and result["error"] == "Market is closed":
        logger.info("PASS: Trade was correctly rejected because market is closed")
    elif market_open and result and "id" in result:
        logger.info("PASS: Trade was executed because market is open")
    else:
        logger.error(f"FAIL: Unexpected result: {result}")
    
    return result

if __name__ == "__main__":
    test_result = test_market_hours_check()
    print("\nTest Result:")
    print(test_result)
