import os
import time
import logging
import datetime
import psutil
import json
from pathlib import Path

# Set up logging
logging.basicConfig(
    filename='trading_bot_monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TradingBotMonitor:
    def __init__(self):
        self.log_file = 'trading_bot_monitor.log'
        self.monitoring_interval = 300  # Check every 5 minutes
        self.symbols = self._get_symbols_from_config()
        
    def _get_symbols_from_config(self):
        """Extract symbols from config.py without importing it"""
        try:
            with open('config.py', 'r') as f:
                config_content = f.read()
            
            # Find the SYMBOLS list in the config file
            import re
            symbols_match = re.search(r'SYMBOLS\s*=\s*\[(.*?)\]', config_content, re.DOTALL)
            if symbols_match:
                symbols_str = symbols_match.group(1)
                # Extract quoted strings from the list
                symbols = re.findall(r'"([^"]*)"', symbols_str)
                if not symbols:
                    symbols = re.findall(r"'([^']*)'", symbols_str)
                return symbols
            return ["Unknown"]
        except Exception as e:
            logging.error(f"Error reading symbols from config: {e}")
            return ["Unknown"]
    
    def find_trading_bot_processes(self):
        """Find Python processes that are likely the trading bot"""
        bot_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
            try:
                if proc.info['name'] == 'python.exe':
                    cmdline = proc.info['cmdline']
                    # Look for main.py in the command line
                    if cmdline and any('main.py' in cmd for cmd in cmdline):
                        mem_mb = proc.info['memory_info'].rss / (1024 * 1024)
                        bot_processes.append({
                            'pid': proc.info['pid'],
                            'memory_mb': round(mem_mb, 2),
                            'cmdline': ' '.join(cmdline) if cmdline else 'Unknown'
                        })
                    # Also include high-memory Python processes
                    elif proc.info['memory_info'].rss > (10 * 1024 * 1024):  # > 10MB
                        mem_mb = proc.info['memory_info'].rss / (1024 * 1024)
                        bot_processes.append({
                            'pid': proc.info['pid'],
                            'memory_mb': round(mem_mb, 2),
                            'cmdline': 'Unknown (high memory Python process)'
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        return bot_processes
    
    def check_scheduled_tasks(self):
        """Check if scheduled tasks should have run"""
        current_time = datetime.datetime.now()
        scheduled_tasks = []
        
        # Morning analysis (9:00 AM)
        morning = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
        morning_diff = (current_time - morning).total_seconds() / 60  # minutes
        
        if morning_diff >= 0:
            scheduled_tasks.append({
                'task': 'Morning Analysis',
                'scheduled_time': morning.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Should have run',
                'minutes_ago': round(morning_diff, 1)
            })
        else:
            scheduled_tasks.append({
                'task': 'Morning Analysis',
                'scheduled_time': morning.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Not yet run today',
                'minutes_until': round(abs(morning_diff), 1)
            })
            
        # Midday analysis (12:00 PM)
        midday = current_time.replace(hour=12, minute=0, second=0, microsecond=0)
        midday_diff = (current_time - midday).total_seconds() / 60  # minutes
        
        if midday_diff >= 0:
            scheduled_tasks.append({
                'task': 'Midday Analysis',
                'scheduled_time': midday.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Should have run',
                'minutes_ago': round(midday_diff, 1)
            })
        else:
            scheduled_tasks.append({
                'task': 'Midday Analysis',
                'scheduled_time': midday.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Not yet run today',
                'minutes_until': round(abs(midday_diff), 1)
            })
            
        # Random checks (every 2 hours)
        # Calculate the most recent 2-hour interval
        hours_since_midnight = current_time.hour + current_time.minute / 60
        last_random_check_hour = int(hours_since_midnight / 2) * 2
        last_random_check = current_time.replace(
            hour=last_random_check_hour, 
            minute=0, 
            second=0, 
            microsecond=0
        )
        
        if last_random_check_hour > current_time.hour:
            last_random_check = last_random_check.replace(hour=last_random_check_hour - 2)
            
        random_diff = (current_time - last_random_check).total_seconds() / 60  # minutes
        
        scheduled_tasks.append({
            'task': 'Random Check',
            'scheduled_time': last_random_check.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Should have run',
            'minutes_ago': round(random_diff, 1),
            'next_check': (last_random_check + datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        })
        
        return scheduled_tasks
    
    def check_market_data(self):
        """Check for market data files"""
        market_data_info = {
            'data_files': [],
            'last_updated': None
        }
        
        # Look for market data files
        data_dir = Path('.')
        data_files = list(data_dir.glob('*data*.csv')) + list(data_dir.glob('*price*.csv'))
        
        if data_files:
            for data_file in data_files:
                mod_time = datetime.datetime.fromtimestamp(data_file.stat().st_mtime)
                market_data_info['data_files'].append({
                    'filename': data_file.name,
                    'last_modified': mod_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'size_kb': round(data_file.stat().st_size / 1024, 2)
                })
                
                # Track the most recent update
                if market_data_info['last_updated'] is None or mod_time > datetime.datetime.strptime(market_data_info['last_updated'], '%Y-%m-%d %H:%M:%S'):
                    market_data_info['last_updated'] = mod_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return market_data_info
    
    def log_bot_status(self):
        """Log comprehensive information about the trading bot status"""
        status_report = {
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'bot_processes': self.find_trading_bot_processes(),
            'scheduled_tasks': self.check_scheduled_tasks(),
            'market_data': self.check_market_data(),
            'monitored_symbols': self.symbols
        }
        
        # Log the status report
        logging.info(f"Trading Bot Status Report: {json.dumps(status_report, indent=2)}")
        
        # Create a more readable summary
        bot_running = len(status_report['bot_processes']) > 0
        
        summary = [
            f"=== Trading Bot Status at {status_report['timestamp']} ===",
            f"Bot Running: {'Yes' if bot_running else 'No'}",
            f"Monitored Symbols: {', '.join(status_report['monitored_symbols'])}",
            "",
            "Scheduled Tasks:",
        ]
        
        for task in status_report['scheduled_tasks']:
            if 'minutes_ago' in task:
                summary.append(f"- {task['task']}: {task['status']} ({task['minutes_ago']} minutes ago)")
            else:
                summary.append(f"- {task['task']}: {task['status']} (in {task['minutes_until']} minutes)")
                
        if 'next_check' in status_report['scheduled_tasks'][-1]:
            summary.append(f"  Next Random Check: {status_report['scheduled_tasks'][-1]['next_check']}")
            
        summary.append("")
        summary.append("Market Data:")
        if status_report['market_data']['data_files']:
            summary.append(f"- Last Updated: {status_report['market_data']['last_updated']}")
            for file in status_report['market_data']['data_files']:
                summary.append(f"- {file['filename']} ({file['size_kb']} KB)")
        else:
            summary.append("- No market data files found")
            
        # Write the summary to a separate file for easy reading
        with open('bot_status_summary.txt', 'w') as f:
            f.write('\n'.join(summary))
            
        return status_report
    
    def monitor_continuously(self):
        """Run continuous monitoring of the trading bot"""
        logging.info("Starting continuous trading bot monitoring")
        print(f"Starting continuous trading bot monitoring. Checking every {self.monitoring_interval/60} minutes.")
        print(f"Log file: {self.log_file}")
        print(f"Summary file: bot_status_summary.txt")
        print("Press Ctrl+C to stop monitoring")
        
        try:
            while True:
                self.log_bot_status()
                time.sleep(self.monitoring_interval)
        except KeyboardInterrupt:
            logging.info("Bot monitoring stopped by user")
            print("\nBot monitoring stopped")
            
    def run_once(self):
        """Run a single monitoring check"""
        status = self.log_bot_status()
        print(f"Monitoring complete. Check {self.log_file} for details.")
        print(f"A readable summary has been saved to bot_status_summary.txt")
        return status

if __name__ == "__main__":
    monitor = TradingBotMonitor()
    monitor.run_once()
    
    # Uncomment to run continuous monitoring
    # monitor.monitor_continuously()
