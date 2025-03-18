# Docker Deployment Guide for Trading Bot

This guide explains how to deploy your trading bot using Docker, which provides a consistent and isolated environment for running your application.

## Prerequisites

1. [Docker](https://docs.docker.com/get-docker/) installed on your system
2. [Docker Compose](https://docs.docker.com/compose/install/) installed on your system
3. Your trading bot code with the provided Docker configuration files

## Files Overview

- `Dockerfile`: Defines how to build your trading bot container
- `docker-compose.yml`: Configures the container deployment with volumes and environment variables
- `.dockerignore`: Specifies which files should be excluded from the Docker build context
- `.env`: Contains your environment variables and API keys (never commit this to version control)

## Step 1: Prepare Your Environment

Ensure your `.env` file is properly configured with all required API keys and settings:

```
TRADIER_API_KEY=your_key_here
TRADIER_SANDBOX_KEY=your_sandbox_key_here
USE_SANDBOX=True
...
```

## Step 2: Build and Run with Docker Compose

From your project directory, run:

```bash
docker-compose up -d --build
```

This command:
- Builds the Docker image based on your Dockerfile
- Creates and starts the container in detached mode (-d)
- Sets up volume mounts for logs
- Loads environment variables from your .env file

## Step 3: Monitor Your Trading Bot

Check if your container is running:

```bash
docker ps
```

View the logs:

```bash
docker logs -f trading-bot
```

## Step 4: Managing Your Trading Bot

### Stopping the Bot

```bash
docker-compose down
```

### Restarting the Bot

```bash
docker-compose restart
```

### Updating the Bot

When you make changes to your code:

```bash
docker-compose down
docker-compose up -d --build
```

## Deploying to DigitalOcean with Docker

### 1. Create a Droplet with Docker

When creating your DigitalOcean Droplet, select the "Marketplace" tab and choose the "Docker" image. This will create a Droplet with Docker pre-installed.

### 2. Transfer Your Files

Transfer your project files to the Droplet:

```bash
scp -r /path/to/Forward_Profit/* root@your-droplet-ip:~/trading-bot/
```

### 3. Deploy with Docker Compose

SSH into your Droplet:

```bash
ssh root@your-droplet-ip
```

Navigate to your project directory and start the container:

```bash
cd ~/trading-bot
docker-compose up -d --build
```

## Best Practices for Production

1. **Container Health Checks**: Already configured in docker-compose.yml
2. **Automatic Restarts**: Set with `restart: unless-stopped` in docker-compose.yml
3. **Volume Mounts**: Configured to persist logs outside the container
4. **Environment Variables**: Loaded from .env file, keeping sensitive data separate from code
5. **Timezone Configuration**: Set to Eastern Time for accurate market hours

## Troubleshooting

### Container Exits Immediately

Check the logs:
```bash
docker logs trading-bot
```

### API Connection Issues

Verify your .env file contains the correct API keys and that they're being properly loaded.

### Persisting Data

If you need to persist additional data, add more volume mounts in docker-compose.yml:

```yaml
volumes:
  - ./data:/app/data
```

## Backup Strategy

To back up your container data:

```bash
# Create a backup directory
mkdir -p ~/backups

# Create a backup script
cat > ~/backup-trading-bot.sh << 'EOL'
#!/bin/bash
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$HOME/backups"
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/trading_bot_$TIMESTAMP.tar.gz -C $HOME/trading-bot .
EOL

# Make it executable
chmod +x ~/backup-trading-bot.sh

# Set up a cron job for daily backups
(crontab -l 2>/dev/null || echo "") | grep -v "backup-trading-bot.sh" | { cat; echo "0 5 * * * $HOME/backup-trading-bot.sh"; } | crontab -
```
