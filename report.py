# report.py - Compose and send daily email reports
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json
from config import EMAIL_USERNAME, EMAIL_PASSWORD

def log_trade(trade_data):
    """
    Log trade details to file for reporting.
    
    Args:
        trade_data (dict): Trade details including symbol, contract, side, price, etc.
    """
    # Create a timestamped record
    trade_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Define the log file path
    log_file = "trading_log.json"
    
    # Read existing log if it exists
    trades = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                trades = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # If the file is empty or not valid JSON, start with an empty list
            trades = []
    
    # Append the new trade
    trades.append(trade_data)
    
    # Write back to the log file
    with open(log_file, 'w') as f:
        json.dump(trades, f, indent=4)
    
    print(f"Trade logged: {trade_data['symbol']} - {trade_data['action']} at ${trade_data.get('price', 'N/A')}")

def generate_daily_report():
    """
    Generate a daily trading report from the log file.
    
    Returns:
        str: HTML formatted report
    """
    log_file = "trading_log.json"
    today = datetime.now().strftime("%Y-%m-%d")
    
    if not os.path.exists(log_file):
        return f"<h1>Daily Trading Report - {today}</h1><p>No trades executed today.</p>"
        
    try:
        with open(log_file, 'r') as f:
            trades = json.load(f)
            
        # Filter trades from today
        today_trades = [t for t in trades if t['timestamp'].startswith(today)]
        
        if not today_trades:
            return f"<h1>Daily Trading Report - {today}</h1><p>No trades executed today.</p>"
            
        # Compile the report
        report = f"<h1>Daily Trading Report - {today}</h1>"
        report += "<h2>Trades Executed:</h2>"
        report += "<table border='1'><tr><th>Time</th><th>Symbol</th><th>Action</th><th>Contract</th><th>Price</th><th>Notes</th></tr>"
        
        for trade in today_trades:
            time = trade['timestamp'].split()[1]
            report += f"<tr><td>{time}</td><td>{trade['symbol']}</td><td>{trade['action']}</td>"
            report += f"<td>{trade.get('contract', 'N/A')}</td><td>${trade.get('price', 'N/A')}</td>"
            report += f"<td>{trade.get('notes', '')}</td></tr>"
            
        report += "</table>"
        
        return report
        
    except Exception as e:
        print(f"Error generating report: {e}")
        return f"<h1>Daily Trading Report - {today}</h1><p>Error generating report: {e}</p>"

def send_email_report(recipient):
    """
    Send a daily email report to the specified recipient.
    
    Args:
        recipient (str): Email address to send report to
    """
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print("EMAIL_USERNAME or EMAIL_PASSWORD not set in config.py")
        print("For Gmail, you must use an app-specific password.")
        print("Go to your Google Account > Security > App Passwords to create one.")
        return
        
    report_html = generate_daily_report()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create email
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USERNAME
    msg['To'] = recipient
    msg['Subject'] = f"Options Trading Bot Daily Report - {today}"
    
    # Attach HTML report
    msg.attach(MIMEText(report_html, 'html'))
    
    try:
        # Connect to Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        # Login and send
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"Email report sent to {recipient}")
        
    except smtplib.SMTPAuthenticationError:
        print("Error sending email report: Authentication failed")
        print("\nNOTE: For Gmail, you MUST use an App Password, not your regular password!")
        print("To create an App Password:")
        print("1. Go to your Google Account > Security > 2-Step Verification")
        print("2. At the bottom, click 'App passwords'")
        print("3. Select 'Mail' and 'Other (Custom name)'")
        print("4. Enter a name like 'Options Trading Bot'")
        print("5. Click 'Generate' and use the 16-character password in your config.py")
    except Exception as e:
        print(f"Error sending email report: {e}")
        
    return
