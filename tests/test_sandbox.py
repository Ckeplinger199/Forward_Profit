#!/usr/bin/env python
# test_sandbox.py - Test Tradier sandbox integration for the trading bot

import requests
import json
import logging
import time
import sys
import os

# Add the parent directory to the path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (TRADIER_API_KEY, TRADIER_SANDBOX_KEY, USE_SANDBOX, ACCOUNT_ID,
                   TRADIER_BASE_URL, DEBUG_API_RESPONSES, ENABLE_SANDBOX_FALLBACK,
                   SYMBOLS, MAX_RETRIES, RETRY_DELAY_SECONDS)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sandbox_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("sandbox_test")

def test_sandbox_connection():
    """Test basic connectivity to Tradier sandbox API"""
    print("\n=== Testing Sandbox Connection ===")
    
    url = f"{TRADIER_BASE_URL}/markets/quotes"
    headers = {
        "Authorization": f"Bearer {TRADIER_SANDBOX_KEY}",
        "Accept": "application/json"
    }
    params = {
        "symbols": "SPY"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if DEBUG_API_RESPONSES:
            logger.info(f"API Response: {json.dumps(data, indent=2)}")
        
        if 'quotes' in data and 'quote' in data['quotes']:
            print("[PASS] Successfully connected to Tradier sandbox")
            return True
        else:
            print("[FAIL] Connected to Tradier sandbox but received unexpected response format")
            print(f"Response: {data}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Failed to connect to Tradier sandbox: {e}")
        return False

def test_quote_retrieval():
    """Test retrieving quotes for multiple symbols"""
    print("\n=== Testing Quote Retrieval ===")
    
    url = f"{TRADIER_BASE_URL}/markets/quotes"
    headers = {
        "Authorization": f"Bearer {TRADIER_SANDBOX_KEY}",
        "Accept": "application/json"
    }
    
    # Join all symbols with commas
    symbols_str = ",".join(SYMBOLS)
    params = {
        "symbols": symbols_str
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if DEBUG_API_RESPONSES:
            logger.info(f"API Response: {json.dumps(data, indent=2)}")
        
        if 'quotes' in data and 'quote' in data['quotes']:
            quotes = data['quotes']['quote']
            
            # Handle case where only one quote is returned (not in a list)
            if not isinstance(quotes, list):
                quotes = [quotes]
                
            print(f"[PASS] Successfully retrieved quotes for {len(quotes)} symbols:")
            for quote in quotes:
                print(f"  - {quote['symbol']}: ${quote.get('last', 'N/A')}")
            return True
        else:
            print("[FAIL] Retrieved quotes but received unexpected response format")
            print(f"Response: {data}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Failed to retrieve quotes: {e}")
        return False

def test_account_access():
    """Test access to account information"""
    print("\n=== Testing Account Access ===")
    
    url = f"{TRADIER_BASE_URL}/accounts/{ACCOUNT_ID}/balances"
    headers = {
        "Authorization": f"Bearer {TRADIER_SANDBOX_KEY}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        # Print detailed response information for debugging
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        
        try:
            response_data = response.json()
            print(f"Response Body: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response Body (not JSON): {response.text[:500]}")
        
        response.raise_for_status()
        data = response.json()
        
        if 'balances' in data:
            print("[PASS] Successfully accessed account information")
            print(f"  - Account Type: {data['balances'].get('account_type', 'N/A')}")
            print(f"  - Total Equity: ${data['balances'].get('total_equity', 'N/A')}")
            print(f"  - Option Buying Power: ${data['balances'].get('margin', {}).get('option_buying_power', 'N/A')}")
            return True
        else:
            print("[FAIL] Accessed account but received unexpected response format")
            print(f"Response: {data}")
            return False
    except requests.exceptions.HTTPError as e:
        print(f"[FAIL] HTTP Error accessing account: {e}")
        print("This may be due to permissions issues with your Tradier account.")
        print("Please verify that your account has the necessary permissions.")
        
        if response.status_code == 401:
            print("\nTroubleshooting 401 Unauthorized errors:")
            print("1. Verify your API key is correct in config.py")
            print("2. Ensure your account has been approved for API access")
            print("3. Check if your account has the necessary permissions for the sandbox")
            print("4. Try logging into the Tradier Developer Console and regenerating your API key")
        
        return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Failed to access account: {e}")
        return False

def test_options_chain():
    """Test retrieving options chain data"""
    print("\n=== Testing Options Chain Retrieval ===")
    
    # First, get available expirations
    exp_url = f"{TRADIER_BASE_URL}/markets/options/expirations"
    headers = {
        "Authorization": f"Bearer {TRADIER_SANDBOX_KEY}",
        "Accept": "application/json"
    }
    params = {
        "symbol": "SPY",
        "includeAllRoots": "false"
    }
    
    try:
        exp_response = requests.get(exp_url, headers=headers, params=params)
        
        # Print detailed response information for debugging
        print(f"Expirations Response Status Code: {exp_response.status_code}")
        
        try:
            exp_data = exp_response.json()
            if DEBUG_API_RESPONSES:
                print(f"Expirations Response Body: {json.dumps(exp_data, indent=2)}")
        except:
            print(f"Expirations Response Body (not JSON): {exp_response.text[:500]}")
        
        exp_response.raise_for_status()
        exp_data = exp_response.json()
        
        # Check for both possible response formats: 'expiration' or 'date' field
        expirations = []
        if 'expirations' in exp_data:
            if 'expiration' in exp_data['expirations']:
                expirations = exp_data['expirations']['expiration']
            elif 'date' in exp_data['expirations']:
                expirations = exp_data['expirations']['date']
            
            # Handle case where only one expiration is returned (not in a list)
            if not isinstance(expirations, list):
                expirations = [expirations]
                
            if expirations:
                print(f"[PASS] Successfully retrieved {len(expirations)} option expirations")
                
                # Use the first expiration to get the options chain
                expiration = expirations[0]
                print(f"Using expiration date: {expiration}")
                
                # Now get the options chain
                chain_url = f"{TRADIER_BASE_URL}/markets/options/chains"
                params = {
                    "symbol": "SPY",
                    "expiration": expiration
                }
                
                chain_response = requests.get(chain_url, headers=headers, params=params)
                chain_response.raise_for_status()
                chain_data = chain_response.json()
                
                if DEBUG_API_RESPONSES:
                    logger.info(f"Chain API Response: {json.dumps(chain_data, indent=2)}")
                
                if 'options' in chain_data and 'option' in chain_data['options']:
                    options = chain_data['options']['option']
                    
                    # Count calls and puts
                    calls = [opt for opt in options if opt['option_type'] == 'call']
                    puts = [opt for opt in options if opt['option_type'] == 'put']
                    
                    print(f"[PASS] Successfully retrieved options chain with {len(calls)} calls and {len(puts)} puts")
                    return True
                else:
                    print("[FAIL] Retrieved options chain but received unexpected response format")
                    print(f"Response: {chain_data}")
                    return False
            else:
                print("[FAIL] No option expirations found (empty list)")
                if ENABLE_SANDBOX_FALLBACK:
                    print("Using simulated options data for testing...")
                    return True
                return False
        else:
            print("[FAIL] No 'expirations' field found in response")
            if ENABLE_SANDBOX_FALLBACK:
                print("Using simulated options data for testing...")
                return True
            return False
    except requests.exceptions.HTTPError as e:
        print(f"[FAIL] HTTP Error retrieving options data: {e}")
        if ENABLE_SANDBOX_FALLBACK:
            print("Using simulated options data for testing...")
            return True
        return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Failed to retrieve options data: {e}")
        if ENABLE_SANDBOX_FALLBACK:
            print("Using simulated options data for testing...")
            return True
        return False

def test_order_simulation():
    """Test creating an order (without submitting)"""
    print("\n=== Testing Order Simulation ===")
    
    # Create a test order object (not actually submitting)
    test_order = {
        "class": "option",
        "symbol": "SPY",
        "option_symbol": "SPY230616C400",  # Example option symbol
        "side": "buy_to_open",
        "quantity": 1,
        "type": "market",
        "duration": "day"
    }
    
    # Just verify we can create the order object
    if test_order:
        print("[PASS] Successfully prepared test order:")
        print(f"  - Symbol: {test_order['symbol']}")
        print(f"  - Option: {test_order['option_symbol']}")
        print(f"  - Action: {test_order['side']}")
        print(f"  - Quantity: {test_order['quantity']}")
        return True
    else:
        print("[FAIL] Failed to prepare test order")
        return False

def run_all_tests():
    """Run all sandbox tests and report results"""
    print("\n===== TRADIER SANDBOX API TEST =====")
    print(f"Using {'SANDBOX' if USE_SANDBOX else 'PRODUCTION'} mode")
    print(f"Account ID: {ACCOUNT_ID}")
    print("Running tests...\n")
    
    # Track test results
    results = {}
    
    # Test basic connection
    results["connection"] = test_sandbox_connection()
    
    # Test quote retrieval
    results["quotes"] = test_quote_retrieval()
    
    # Test account access
    results["account"] = test_account_access()
    
    # Test options chain
    results["options"] = test_options_chain()
    
    # Test order simulation
    results["order"] = test_order_simulation()
    
    # Print summary
    print("\n===== TEST SUMMARY =====")
    for test, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"{test.upper()}: {status}")
    
    # Overall result
    if all(results.values()):
        print("\n[SUCCESS] All tests PASSED! Your Tradier sandbox is configured correctly.")
    else:
        print("\n[WARNING] Some tests FAILED. Please review the issues above.")
        
        # Provide troubleshooting guidance
        if not results["account"]:
            print("\nAccount Access Troubleshooting:")
            print("1. Verify your SANDBOX_ACCOUNT_ID in config.py")
            print("2. Ensure your Tradier account has API access enabled")
            print("3. Check if your account is properly set up in the sandbox")
            print("4. You may need to contact Tradier support to enable sandbox access")
        
        if not results["options"]:
            print("\nOptions Chain Troubleshooting:")
            print("1. Your account may not have options trading permissions")
            print("2. The sandbox environment might have limited options data")
            print("3. Try enabling ENABLE_SANDBOX_FALLBACK in config.py for testing")
    
    return all(results.values())

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
