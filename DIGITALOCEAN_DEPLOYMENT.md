# Deploying Trading Bot to DigitalOcean

This guide provides step-by-step instructions for deploying your trading bot to DigitalOcean.

## Prerequisites

1. A DigitalOcean account
2. SSH key set up for secure access
3. Your trading bot code ready for deployment

## Step 1: Create a DigitalOcean Droplet

1. Log in to your DigitalOcean account
2. Click "Create" and select "Droplets"
3. Choose the following configuration:
   - **OS**: Ubuntu 22.04 LTS
   - **Plan**: Basic Shared CPU (4GB RAM / 2 CPUs / 80GB SSD)
   - **Authentication**: SSH keys (select your key)
   - **Hostname**: trading-bot (or your preferred name)
4. Click "Create Droplet"

## Step 2: Connect to Your Droplet

Once your droplet is created, connect to it via SSH:

```bash
ssh root@your-droplet-ip
```

## Step 3: Transfer Your Code

### Option 1: Using Git (Recommended)

1. Create a private repository on GitHub or GitLab
2. Push your code to the repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/your-repo.git
   git push -u origin main
   ```
3. On your DigitalOcean droplet, clone the repository:
   ```bash
   mkdir -p ~/trading-bot
   cd ~/trading-bot
   git clone https://github.com/yourusername/your-repo.git .
   ```

### Option 2: Using SCP (Direct Transfer)

Transfer your files directly from your local machine:

```bash
scp -r /path/to/Forward_Profit/* root@your-droplet-ip:~/trading-bot/
```

## Step 4: Set Up Environment Variables

1. Create a `.env` file on your droplet:
   ```bash
   nano ~/trading-bot/.env
   ```

2. Copy the contents of your local `.env` file to this file
3. Save and exit (Ctrl+X, then Y, then Enter)

## Step 5: Run the Deployment Script

The deployment script will set up everything you need:

```bash
cd ~/trading-bot
chmod +x deploy_digitalocean.sh
./deploy_digitalocean.sh
```

This script will:
- Install required system packages
- Set up a Python virtual environment
- Install Python dependencies
- Configure systemd for automatic startup
- Set up log rotation
- Configure daily backups
- Set the timezone to Eastern Time

## Step 6: Verify Deployment

Check if your trading bot is running:

```bash
sudo systemctl status tradingbot.service
```

View the logs:

```bash
sudo journalctl -u tradingbot.service
```

## Managing Your Trading Bot

### Starting/Stopping/Restarting

```bash
# Start the bot
sudo systemctl start tradingbot.service

# Stop the bot
sudo systemctl stop tradingbot.service

# Restart the bot
sudo systemctl restart tradingbot.service
```

### Updating Your Bot

When you want to update your bot:

1. Push changes to your Git repository
2. On your droplet:
   ```bash
   cd ~/trading-bot
   git pull
   sudo systemctl restart tradingbot.service
   ```

### Monitoring

To monitor your bot's performance:

```bash
# View real-time logs
sudo journalctl -fu tradingbot.service

# Check system resources
htop
```

## Security Considerations

1. **API Keys**: Never commit your `.env` file to Git
2. **Firewall**: Consider enabling UFW for additional security:
   ```bash
   sudo ufw allow OpenSSH
   sudo ufw enable
   ```
3. **Regular Updates**: Keep your system updated:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

## Troubleshooting

If your bot isn't running properly:

1. Check the logs: `sudo journalctl -u tradingbot.service`
2. Verify your `.env` file has all required variables
3. Check Python dependencies: `pip list`
4. Ensure the timezone is correct: `timedatectl`

## Backup and Recovery

The deployment script sets up daily backups at 5 AM. To restore from a backup:

```bash
tar -xzf ~/backups/trading_bot_TIMESTAMP.tar.gz -C ~/trading-bot-restore
```
