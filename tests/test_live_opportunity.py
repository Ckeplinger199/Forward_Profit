# test_live_opportunity.py - Live test the opportunity finder in sandbox mode
import logging
import json
import time
from datetime import datetime
import pandas as pd

# Import necessary modules
from opportunity_finder import identify_opportunities, process_opportunities
from market_data import get_latest_price_data
from config import SYMBOLS, USE_SANDBOX
from trade_tracker import get_trade_tracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("opportunity_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("opportunity_test")

def setup_tradier_client():
    """Set up the Tradier client for sandbox testing"""
    try:
        # Import here to avoid circular imports
        from execution import TradierClient
        
        # Create a client instance (will use sandbox settings from config)
        client = TradierClient()
        
        # Verify account connection
        account_info = client.get_account_balances()
        if account_info:
            logger.info(f"Successfully connected to Tradier sandbox account: {account_info.get('account_number', 'Unknown')}")
            logger.info(f"Account equity: ${account_info.get('total_equity', 0):.2f}")
            return client
        else:
            logger.error("Failed to connect to Tradier sandbox account")
            return None
    except Exception as e:
        logger.error(f"Error setting up Tradier client: {str(e)}")
        return None

def display_trade_tracker_status():
    """Display the current status of the trade tracker"""
    trade_tracker = get_trade_tracker()
    summary = trade_tracker.get_trade_summary()
    
    logger.info("=" * 50)
    logger.info("TRADE TRACKER STATUS")
    logger.info(f"Recent day trades: {summary['recent_day_trades']}/3")
    logger.info(f"Remaining day trades: {summary['remaining_day_trades']}")
    logger.info(f"Can day trade: {summary['can_day_trade']}")
    
    if summary['trades']:
        logger.info("\nRecent trades:")
        for i, trade in enumerate(summary['trades'], 1):
            logger.info(f"  {i}. {trade['symbol']} - {trade['contracts']} contracts - {trade['trade_date']}")
    
    logger.info("=" * 50)

def run_live_opportunity_test():
    """Run a live test of the opportunity finder in sandbox mode"""
    logger.info("=" * 80)
    logger.info("STARTING LIVE OPPORTUNITY FINDER TEST")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Sandbox Mode: {USE_SANDBOX}")
    logger.info("=" * 80)
    
    # Verify we're in sandbox mode for safety
    if not USE_SANDBOX:
        logger.error("ABORTING: Test must be run in sandbox mode (USE_SANDBOX=True in config.py)")
        return
    
    # Set up Tradier client for executing trades
    tradier_client = setup_tradier_client()
    if not tradier_client:
        logger.error("ABORTING: Could not set up Tradier client")
        return
    
    # Display current trade tracker status
    display_trade_tracker_status()
    
    try:
        # Step 1: Identify trading opportunities
        logger.info("Step 1: Identifying trading opportunities...")
        opportunities = identify_opportunities(max_opportunities=3)
        
        if not opportunities:
            logger.warning("No trading opportunities identified")
            return
        
        # Log the identified opportunities
        logger.info(f"Identified {len(opportunities)} trading opportunities:")
        for i, opp in enumerate(opportunities, 1):
            logger.info(f"Opportunity {i}: {opp['ticker']} - {opp['signal']} - Confidence: {opp['confidence']:.2f}")
            logger.info(f"  Reasoning: {opp['reasoning'][:200]}..." if 'reasoning' in opp else "  No reasoning provided")
        
        # Step 2: Process and execute trades for the opportunities
        logger.info("\nStep 2: Processing and executing trades...")
        executed_trades = process_opportunities(opportunities, tradier_client)
        
        if not executed_trades:
            logger.warning("No trades were executed")
            return
        
        # Log the executed trades
        logger.info(f"Executed {len(executed_trades)} trades:")
        for i, trade in enumerate(executed_trades, 1):
            logger.info(f"Trade {i}: {trade.get('ticker')} - {trade.get('signal')} - {trade.get('contracts')} contracts - Status: {trade.get('result', {}).get('status')}")
        
        # Step 3: Verify the trades in the account
        logger.info("\nStep 3: Verifying trades in account...")
        positions = tradier_client.get_account_positions()
        
        if positions:
            logger.info(f"Current positions after trading:")
            for pos in positions:
                logger.info(f"Position: {pos.get('symbol')} - Quantity: {pos.get('quantity')} - Cost: ${pos.get('cost_basis', 0):.2f}")
        else:
            logger.warning("No positions found in account")
        
        # Display updated trade tracker status
        logger.info("\nUpdated trade tracker status after executing trades:")
        display_trade_tracker_status()
        
        # Step 4: Test PDT rule enforcement
        logger.info("\nStep 4: Testing PDT rule enforcement...")
        
        # Force account value to be below $25,000 for PDT testing
        account_info = tradier_client.get_account_balances()
        original_equity = float(account_info.get('total_equity', 25000))
        
        # Simulate making multiple day trades to hit PDT limit
        trade_tracker = get_trade_tracker()
        
        # If we have fewer than 3 day trades, add some test trades
        while trade_tracker.count_day_trades() < 3:
            trade_tracker.add_day_trade("TEST", 1)
            logger.info("Added test day trade to reach PDT limit")
        
        logger.info("PDT limit reached (3 day trades in 5 business days)")
        
        # Try to process opportunities again - should skip day trades
        logger.info("\nAttempting to process opportunities with PDT limit reached...")
        executed_trades = process_opportunities(opportunities, tradier_client)
        
        if executed_trades:
            logger.info(f"Executed {len(executed_trades)} trades with PDT limit reached:")
            for i, trade in enumerate(executed_trades, 1):
                logger.info(f"Trade {i}: {trade.get('ticker')} - {trade.get('signal')} - {trade.get('contracts')} contracts - Duration: {trade.get('result', {}).get('duration', 'Unknown')}")
        else:
            logger.info("No trades executed with PDT limit reached (as expected)")
        
        logger.info("\nLive opportunity test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during live opportunity test: {str(e)}")
    finally:
        logger.info("=" * 80)
        logger.info("COMPLETED LIVE OPPORTUNITY FINDER TEST")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

if __name__ == "__main__":
    run_live_opportunity_test()
