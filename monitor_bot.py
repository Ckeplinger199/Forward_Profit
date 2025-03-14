import os
import time
import datetime
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    filename='bot_monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def monitor_trading_bot():
    """Create a new monitoring log for the trading bot"""
    logging.info("Starting trading bot monitor")
    
    # Check for running Python processes with high memory usage (likely our bot)
    try:
        import psutil
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            if proc.info['name'] == 'python.exe':
                mem_mb = proc.info['memory_info'].rss / (1024 * 1024)
                if mem_mb > 10:  # Only log processes using more than 10MB
                    python_processes.append(f"PID: {proc.info['pid']}, Memory: {mem_mb:.2f} MB")
        
        if python_processes:
            logging.info(f"Found potential trading bot processes:")
            for proc in python_processes:
                logging.info(proc)
        else:
            logging.warning("No Python processes with significant memory usage found")
    except ImportError:
        logging.warning("psutil not installed, can't check processes in detail")
    
    # Check for any new log files that might have been created
    log_dir = Path('.')
    log_files = list(log_dir.glob('*.log'))
    
    if log_files:
        logging.info("Log files found in directory:")
        for log_file in log_files:
            mod_time = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
            logging.info(f"- {log_file.name} (Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')})")
    else:
        logging.warning("No log files found in directory")
    
    # Check if scheduled tasks are likely running
    current_time = datetime.datetime.now()
    logging.info(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if midday analysis should have run (12:00 PM)
    midday = current_time.replace(hour=12, minute=0, second=0, microsecond=0)
    time_diff = (current_time - midday).total_seconds() / 60  # minutes
    
    if 0 <= time_diff <= 5:
        logging.info("✅ Midday analysis should have just run (within last 5 minutes)")
    elif time_diff < 0:
        logging.info("❌ Midday analysis hasn't run yet today")
    else:
        logging.info(f"✅ Midday analysis should have run {time_diff:.1f} minutes ago")
    
    logging.info("Bot monitoring complete")
    
if __name__ == "__main__":
    monitor_trading_bot()
    print("Monitoring complete. Check bot_monitor.log for details.")
