#!/bin/bash
# DigitalOcean Deployment Script for Trading Bot
# This script sets up the environment and deploys the trading bot on a DigitalOcean droplet

# Exit on error
set -e

echo "=== Trading Bot Deployment Script ==="
echo "Setting up environment on DigitalOcean..."

# Update system packages
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
echo "Installing Python and dependencies..."
sudo apt install -y python3-pip python3-dev build-essential git

# Create project directory
echo "Creating project directory..."
mkdir -p ~/trading-bot

# Set up virtual environment
echo "Setting up Python virtual environment..."
python3 -m pip install --upgrade pip
python3 -m pip install virtualenv
python3 -m virtualenv ~/trading-bot/venv

# Activate virtual environment
echo "Activating virtual environment..."
source ~/trading-bot/venv/bin/activate

# Install required Python packages
echo "Installing required Python packages..."
pip install requests pandas numpy schedule pytz python-dotenv

# Create log directories
echo "Creating log directories..."
mkdir -p ~/trading-bot/logs
mkdir -p ~/trading-bot/log_archives

# Set up systemd service
echo "Setting up systemd service..."
cat > /tmp/tradingbot.service << EOL
[Unit]
Description=Trading Bot Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/trading-bot
ExecStart=$HOME/trading-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=tradingbot

[Install]
WantedBy=multi-user.target
EOL

sudo mv /tmp/tradingbot.service /etc/systemd/system/tradingbot.service

# Set up log rotation
echo "Setting up log rotation..."
cat > /tmp/tradingbot << EOL
$HOME/trading-bot/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 $USER $USER
}
EOL

sudo mv /tmp/tradingbot /etc/logrotate.d/tradingbot

# Create backup script
echo "Creating backup script..."
cat > ~/trading-bot/backup.sh << EOL
#!/bin/bash
TIMESTAMP=\$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="\$HOME/backups"
mkdir -p \$BACKUP_DIR
tar -czf \$BACKUP_DIR/trading_bot_\$TIMESTAMP.tar.gz -C \$HOME/trading-bot .
EOL

chmod +x ~/trading-bot/backup.sh

# Set up cron job for backups
echo "Setting up cron job for daily backups..."
(crontab -l 2>/dev/null || echo "") | grep -v "trading-bot/backup.sh" | { cat; echo "0 5 * * * $HOME/trading-bot/backup.sh"; } | crontab -

# Set timezone to Eastern Time
echo "Setting timezone to Eastern Time..."
sudo timedatectl set-timezone America/New_York

# Enable and start the service
echo "Enabling and starting the trading bot service..."
sudo systemctl daemon-reload
sudo systemctl enable tradingbot.service
sudo systemctl start tradingbot.service

echo "=== Deployment Complete ==="
echo "Your trading bot is now running as a service on DigitalOcean."
echo "To check the status: sudo systemctl status tradingbot.service"
echo "To view logs: sudo journalctl -u tradingbot.service"
echo "To restart: sudo systemctl restart tradingbot.service"
