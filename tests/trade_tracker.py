# trade_tracker.py - Track day trades to comply with PDT rules
import json
import os
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("trade_tracker")

class TradeTracker:
    """
    Track day trades to ensure compliance with Pattern Day Trader (PDT) rules:
    - Maximum 3 day trades in a rolling 5-business-day period for accounts under $25,000
    - A day trade occurs when you buy and sell the same security on the same day
    """
    
    def __init__(self, tracker_file="day_trades.json"):
        """
        Initialize the trade tracker
        
        Args:
            tracker_file (str): Path to the JSON file for storing trade data
        """
        self.tracker_file = tracker_file
        self.day_trades = self._load_trades()
        
    def _load_trades(self):
        """Load existing trade data from file"""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading trade data: {str(e)}")
                return []
        return []
    
    def _save_trades(self):
        """Save trade data to file"""
        try:
            with open(self.tracker_file, 'w') as f:
                json.dump(self.day_trades, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving trade data: {str(e)}")
    
    def add_day_trade(self, symbol, contracts, entry_time=None, exit_time=None):
        """
        Record a day trade
        
        Args:
            symbol (str): The traded symbol
            contracts (int): Number of contracts traded
            entry_time (datetime, optional): Entry time, defaults to current time
            exit_time (datetime, optional): Exit time, defaults to current time
        """
        if entry_time is None:
            entry_time = datetime.now()
            
        if exit_time is None:
            exit_time = datetime.now()
            
        trade = {
            "symbol": symbol,
            "contracts": contracts,
            "entry_time": entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
            "trade_date": entry_time.strftime("%Y-%m-%d")
        }
        
        self.day_trades.append(trade)
        self._save_trades()
        logger.info(f"Recorded day trade: {symbol} ({contracts} contracts)")
        
        # Check if we're approaching PDT limit
        remaining = self.remaining_day_trades()
        if remaining <= 1:
            logger.warning(f"WARNING: Only {remaining} day trades remaining in 5-day period!")
    
    def get_recent_day_trades(self, days=5):
        """
        Get day trades within the specified number of recent business days
        
        Args:
            days (int): Number of business days to look back
            
        Returns:
            list: Recent day trades
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        recent_trades = [trade for trade in self.day_trades 
                        if trade["trade_date"] >= cutoff_date]
        return recent_trades
    
    def count_day_trades(self, days=5):
        """
        Count day trades within the specified number of recent business days
        
        Args:
            days (int): Number of business days to look back
            
        Returns:
            int: Number of day trades
        """
        return len(self.get_recent_day_trades(days))
    
    def remaining_day_trades(self):
        """
        Calculate remaining day trades allowed under PDT rule
        
        Returns:
            int: Number of remaining day trades
        """
        used_trades = self.count_day_trades()
        return max(0, 3 - used_trades)  # PDT rule allows 3 day trades in 5 business days
    
    def can_day_trade(self):
        """
        Check if a day trade can be made without violating PDT rules
        
        Returns:
            bool: True if a day trade can be made, False otherwise
        """
        return self.remaining_day_trades() > 0
    
    def get_trade_summary(self):
        """
        Get a summary of recent trading activity
        
        Returns:
            dict: Summary of trading activity
        """
        recent_trades = self.get_recent_day_trades()
        return {
            "recent_day_trades": len(recent_trades),
            "remaining_day_trades": self.remaining_day_trades(),
            "can_day_trade": self.can_day_trade(),
            "trades": recent_trades
        }

# Singleton instance
_trade_tracker = None

def get_trade_tracker():
    """Get the singleton trade tracker instance"""
    global _trade_tracker
    if _trade_tracker is None:
        _trade_tracker = TradeTracker()
    return _trade_tracker
