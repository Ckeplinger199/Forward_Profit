# trade_tracker.py - Track day trades to comply with Pattern Day Trader (PDT) rules
import logging
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Set up logging
logger = logging.getLogger("trade_tracker")

class TradeTracker:
    """
    Track day trades to comply with Pattern Day Trader (PDT) rules
    
    The PDT rule applies to margin accounts with less than $25,000 in equity
    and restricts traders to no more than 3 day trades in a rolling 5-business-day period.
    
    A day trade is defined as buying and selling the same security on the same day.
    """
    
    def __init__(self, data_file="trade_tracker_data.json", max_trades=3):
        """
        Initialize the trade tracker
        
        Args:
            data_file (str): Path to the JSON file for storing trade data
            max_trades (int): Maximum number of day trades allowed
        """
        self.data_file = data_file
        self.max_trades = max_trades
        # Enhanced trades dict to track more position details
        self.trades = {}  # Dict to track open positions: {symbol: {'entry_time': datetime, 'contracts': int, 'option_data': {...}}}
        self.day_trades = []  # List of day trades: [{'symbol': str, 'entry_time': datetime, 'exit_time': datetime, 'contracts': int}]
        
        # Load existing data if available
        self.load_data()
        
        # Clean up expired day trades (older than 5 business days)
        self.cleanup_expired_day_trades()
        
        logger.info(f"Initialized TradeTracker with {len(self.day_trades)} recent day trades")
    
    def load_data(self):
        """Load trade data from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                # Convert string dates back to datetime objects
                self.trades = data.get('trades', {})
                for symbol, trade_info in self.trades.items():
                    if 'entry_time' in trade_info and trade_info['entry_time']:
                        trade_info['entry_time'] = datetime.fromisoformat(trade_info['entry_time'])
                
                self.day_trades = data.get('day_trades', [])
                for day_trade in self.day_trades:
                    if 'entry_time' in day_trade and day_trade['entry_time']:
                        day_trade['entry_time'] = datetime.fromisoformat(day_trade['entry_time'])
                    if 'exit_time' in day_trade and day_trade['exit_time']:
                        day_trade['exit_time'] = datetime.fromisoformat(day_trade['exit_time'])
                
                logger.info(f"Loaded trade data: {len(self.trades)} open positions, {len(self.day_trades)} day trades")
            except Exception as e:
                logger.error(f"Error loading trade data: {e}")
                # Initialize with empty data
                self.trades = {}
                self.day_trades = []
        else:
            logger.info("No existing trade data found, starting fresh")
    
    def save_data(self):
        """Save trade data to file"""
        try:
            # Convert datetime objects to ISO format strings for JSON serialization
            data = {
                'trades': {},
                'day_trades': []
            }
            
            # Process trades
            for symbol, trade_info in self.trades.items():
                data['trades'][symbol] = trade_info.copy()
                if 'entry_time' in trade_info and isinstance(trade_info['entry_time'], datetime):
                    data['trades'][symbol]['entry_time'] = trade_info['entry_time'].isoformat()
            
            # Process day trades
            for day_trade in self.day_trades:
                dt_copy = day_trade.copy()
                if 'entry_time' in dt_copy and isinstance(dt_copy['entry_time'], datetime):
                    dt_copy['entry_time'] = dt_copy['entry_time'].isoformat()
                if 'exit_time' in dt_copy and isinstance(dt_copy['exit_time'], datetime):
                    dt_copy['exit_time'] = dt_copy['exit_time'].isoformat()
                data['day_trades'].append(dt_copy)
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved trade data to {self.data_file}")
        except Exception as e:
            logger.error(f"Error saving trade data: {e}")
    
    def cleanup_expired_day_trades(self):
        """Remove day trades older than 5 business days"""
        if not self.day_trades:
            return
        
        # Calculate the cutoff date (5 business days ago)
        # This is a simplified approach; for production, consider using a proper business day calendar
        cutoff_date = datetime.now() - timedelta(days=7)  # 7 calendar days is a conservative approximation
        
        # Filter out expired day trades
        original_count = len(self.day_trades)
        self.day_trades = [dt for dt in self.day_trades if dt.get('exit_time', datetime.now()) > cutoff_date]
        
        if original_count != len(self.day_trades):
            logger.info(f"Removed {original_count - len(self.day_trades)} expired day trades")
            self.save_data()
    
    def add_position(self, symbol, contracts, entry_time=None, option_data=None):
        """
        Record a new position
        
        Args:
            symbol (str): The option symbol
            contracts (int): Number of contracts
            entry_time (datetime, optional): Entry time, defaults to current time
            option_data (dict, optional): Additional option data, defaults to None
        """
        if entry_time is None:
            entry_time = datetime.now()
        
        # If position already exists, add to it
        if symbol in self.trades:
            self.trades[symbol]['contracts'] += contracts
            logger.info(f"Added {contracts} contracts to existing position in {symbol}, total: {self.trades[symbol]['contracts']}")
        else:
            self.trades[symbol] = {
                'entry_time': entry_time,
                'contracts': contracts,
                'option_data': option_data
            }
            logger.info(f"Opened new position: {contracts} contracts of {symbol}")
        
        self.save_data()
    
    def close_position(self, symbol, contracts, exit_time=None):
        """
        Close a position and record a day trade if applicable
        
        Args:
            symbol (str): The option symbol
            contracts (int): Number of contracts to close
            exit_time (datetime, optional): Exit time, defaults to current time
            
        Returns:
            bool: True if this was a day trade, False otherwise
        """
        if exit_time is None:
            exit_time = datetime.now()
        
        is_day_trade = False
        
        if symbol in self.trades:
            position = self.trades[symbol]
            
            # Check if this is a day trade (same trading day)
            entry_date = position['entry_time'].date()
            exit_date = exit_time.date()
            
            if entry_date == exit_date:
                is_day_trade = True
                self.day_trades.append({
                    'symbol': symbol,
                    'entry_time': position['entry_time'],
                    'exit_time': exit_time,
                    'contracts': min(contracts, position['contracts'])
                })
                logger.info(f"Recorded day trade: {contracts} contracts of {symbol}")
            
            # Update or remove the position
            position['contracts'] -= contracts
            if position['contracts'] <= 0:
                del self.trades[symbol]
                logger.info(f"Closed position in {symbol}")
            else:
                logger.info(f"Partially closed position in {symbol}, remaining: {position['contracts']} contracts")
            
            self.save_data()
        else:
            logger.warning(f"Attempted to close non-existent position: {symbol}")
        
        return is_day_trade
    
    def add_day_trade(self, symbol, contracts, entry_time=None, exit_time=None):
        """
        Manually record a day trade
        
        Args:
            symbol (str): The option symbol
            contracts (int): Number of contracts
            entry_time (datetime, optional): Entry time, defaults to current time
            exit_time (datetime, optional): Exit time, defaults to current time
        """
        if entry_time is None:
            entry_time = datetime.now()
        
        if exit_time is None:
            exit_time = datetime.now()
        
        self.day_trades.append({
            'symbol': symbol,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'contracts': contracts
        })
        
        logger.info(f"Manually recorded day trade: {contracts} contracts of {symbol}")
        self.save_data()
    
    def get_day_trade_count(self):
        """
        Get the number of day trades in the past 5 business days
        
        Returns:
            int: Number of day trades
        """
        self.cleanup_expired_day_trades()
        return len(self.day_trades)
    
    def can_day_trade(self):
        """
        Check if more day trades are allowed under PDT rules
        
        Returns:
            bool: True if day trades are allowed, False otherwise
        """
        # Use configurable max_trades instance variable instead of global MAX_DAILY_TRADES
        return self.get_day_trade_count() < self.max_trades
    
    def get_status(self):
        """
        Get the current status of the trade tracker
        
        Returns:
            dict: Status information
        """
        self.cleanup_expired_day_trades()
        
        # Calculate days to clear for each day trade
        for day_trade in self.day_trades:
            if 'exit_time' in day_trade and day_trade['exit_time']:
                # Calculate 5 business days from exit time (approximately 7 calendar days)
                clear_date = day_trade['exit_time'] + timedelta(days=7)
                day_trade['days_to_clear'] = max(0, (clear_date - datetime.now()).days)
        
        return {
            'current_day_trades': len(self.day_trades),
            'max_day_trades': self.max_trades,
            'day_trades_remaining': max(0, self.max_trades - len(self.day_trades)),
            'recent_day_trades': [
                {
                    'symbol': dt['symbol'],
                    'date': dt['exit_time'].strftime('%Y-%m-%d') if 'exit_time' in dt and dt['exit_time'] else 'Unknown',
                    'days_to_clear': dt.get('days_to_clear', 0)
                }
                for dt in self.day_trades
            ]
        }

    def reset_day_trades(self):
        """
        Reset day trades count by clearing all recorded day trades
        
        Returns:
            dict: Day trade status information after reset
        """
        original_count = len(self.day_trades)
        self.day_trades = []
        self.save_data()
        logger.info(f"Reset day trades counter. Cleared {original_count} day trades.")
        return self.get_status()
    
    def __str__(self):
        """String representation of the trade tracker status"""
        status = self.get_status()
        return (
            f"Day Trades: {status['current_day_trades']}/{self.max_trades} in last 5 business days\n"
            f"Can Day Trade: {'Yes' if self.can_day_trade() else 'No'}\n"
            f"Open Positions: {len(self.trades)}"
        )


# Singleton instance
_trade_tracker = None

def get_trade_tracker():
    """
    Get the singleton instance of the TradeTracker
    
    Returns:
        TradeTracker: The trade tracker instance
    """
    global _trade_tracker
    from config import MAX_DAILY_TRADES
    if _trade_tracker is None:
        _trade_tracker = TradeTracker(max_trades=MAX_DAILY_TRADES)
    return _trade_tracker
