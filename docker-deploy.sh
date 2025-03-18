#!/bin/bash
# Docker Deployment Script for Trading Bot on DigitalOcean
# This script helps set up and deploy your trading bot on a DigitalOcean droplet

# Exit on error
set -e

echo "=== Trading Bot Docker Deployment Script ==="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in for group changes to take effect."
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose not found. Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.18.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installed."
fi

# Create backup directory
mkdir -p ~/backups

# Create backup script
echo "Creating backup script..."
cat > ~/backup-trading-bot.sh << 'EOL'
#!/bin/bash
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$HOME/backups"
mkdir -p $BACKUP_DIR
cd $HOME/trading-bot
docker-compose down
tar -czf $BACKUP_DIR/trading_bot_$TIMESTAMP.tar.gz .
docker-compose up -d
echo "Backup created at $BACKUP_DIR/trading_bot_$TIMESTAMP.tar.gz"
EOL

chmod +x ~/backup-trading-bot.sh

# Set up cron job for backups
echo "Setting up daily backup cron job..."
(crontab -l 2>/dev/null || echo "") | grep -v "backup-trading-bot.sh" | { cat; echo "0 5 * * * $HOME/backup-trading-bot.sh"; } | crontab -

# Set timezone to Eastern Time
echo "Setting timezone to Eastern Time..."
sudo timedatectl set-timezone America/New_York

# Set up firewall
echo "Setting up basic firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Build and start the container
echo "Building and starting the trading bot container..."
cd ~/trading-bot
docker-compose up -d --build

# Display status
echo "=== Deployment Complete ==="
echo "Your trading bot is now running in a Docker container on DigitalOcean."
echo ""
echo "Useful commands:"
echo "  - View container status: docker ps"
echo "  - View logs: docker logs -f trading-bot"
echo "  - Stop the bot: docker-compose down"
echo "  - Restart the bot: docker-compose restart"
echo "  - Create a backup: ~/backup-trading-bot.sh"
echo ""
echo "Your trading bot should now be running. Check the logs to verify."
docker ps
