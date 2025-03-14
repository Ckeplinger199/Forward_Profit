# test_option_validation.py - Test script for option symbol validation
import sys
import os
import logging
from unittest.mock import patch

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution import TradierClient
from opportunity_finder import execute_opportunity_trade
from main import is_market_open

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_option_validation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_option_validation")

def test_option_symbol_validation():
    """Test the option symbol validation in execute_opportunity_trade"""
    logger.info("Starting option symbol validation test")
    
    # Initialize Tradier client
    tradier = TradierClient()
    logger.info("Tradier client initialized")
    
    # Test cases with various option symbols
    test_cases = [
        # Valid format
        {"ticker": "SPY", "contract": "SPY250321C00450000", "expected": "valid"},
        # Invalid format - too short
        {"ticker": "AAPL", "contract": "AAPL250C00", "expected": "invalid"},
        # Invalid format - wrong pattern
        {"ticker": "XLU", "contract": "XLU_250413C00008300", "expected": "invalid"},
        # Empty string
        {"ticker": "MSFT", "contract": "", "expected": "invalid"},
        # None value
        {"ticker": "GOOG", "contract": None, "expected": "invalid"}
    ]
    
    results = []
    
    # Use patch to bypass the market hours check
    with patch('main.is_market_open', return_value=True):
        for i, test in enumerate(test_cases):
            logger.info(f"Test case {i+1}: {test['ticker']} with contract {test['contract']}")
            
            result = execute_opportunity_trade(
                ticker=test["ticker"],
                contract=test["contract"],
                signal="BUY_CALL",
                tradier_client=tradier,
                num_contracts=1
            )
            
            # Check if result matches expectation
            if test["expected"] == "valid":
                if "error" in result and "Invalid option contract format" in result["error"]:
                    logger.error(f"FAIL: Valid contract was rejected: {result}")
                    passed = False
                else:
                    logger.info(f"PASS: Valid contract was accepted or rejected for other reasons")
                    passed = True
            else:  # expected invalid
                if "error" in result and "Invalid option contract format" in result["error"]:
                    logger.info(f"PASS: Invalid contract was correctly rejected")
                    passed = True
                else:
                    logger.error(f"FAIL: Invalid contract was not properly rejected: {result}")
                    passed = False
            
            results.append({
                "test_case": test,
                "result": result,
                "passed": passed
            })
    
    # Summary
    passed_count = sum(1 for r in results if r["passed"])
    logger.info(f"Test summary: {passed_count}/{len(results)} tests passed")
    
    return results

if __name__ == "__main__":
    test_results = test_option_symbol_validation()
    print("\nTest Results Summary:")
    for i, result in enumerate(test_results):
        print(f"Test {i+1}: {'PASS' if result['passed'] else 'FAIL'} - {result['test_case']['ticker']} ({result['test_case']['contract']})")
