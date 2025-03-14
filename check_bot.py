import os
import subprocess
import datetime

def check_running_processes():
    """Check if the trading bot is running among Python processes"""
    print(f"Checking for running trading bot at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get list of running Python processes
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], 
                                   capture_output=True, text=True, check=True)
            processes = result.stdout
        else:  # Linux/Mac
            result = subprocess.run(['ps', 'aux', '|', 'grep', 'python'], 
                                   capture_output=True, text=True, check=True, shell=True)
            processes = result.stdout
            
        print("Running Python processes:")
        print(processes)
        
        # Check for main.py in the process list
        if 'main.py' in processes:
            print("✅ Trading bot appears to be running!")
        else:
            print("❌ Could not confirm trading bot is running")
            
    except Exception as e:
        print(f"Error checking processes: {e}")
    
    # Check for new log file creation
    try:
        log_files = [f for f in os.listdir('.') if f.endswith('.log')]
        print("\nLog files in directory:")
        for log in log_files:
            modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(log))
            print(f"- {log} (Last modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')})")
    except Exception as e:
        print(f"Error checking log files: {e}")

if __name__ == "__main__":
    check_running_processes()
