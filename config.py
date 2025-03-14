# config.py - Configuration settings for the options trading bot

# Tradier API access
# Get your API key from https://documentation.tradier.com/brokerage-api
TRADIER_API_KEY = "asvbrhCEAHQMWDARnBOcFaRVPED8"  # Production API key
TRADIER_SANDBOX_KEY = "OglEGAAEnliosD2uB4R0ux9vXxJG"  # Sandbox API key for testing
USE_SANDBOX = True  # Set to False for real trading

# Perplexity API for news fetching
# Get your API key from https://perplexity.ai
PERPLEXITY_API_KEY = "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"

# Email settings for reports
# For Gmail, you MUST use an App Password, not your regular password
# To create an App Password:
# 1. Go to your Google Account > Security > 2-Step Verification
# 2. At the bottom, click 'App passwords'
# 3. Select 'Mail' and 'Other (Custom name)'
# 4. Enter a name like 'Options Trading Bot'
# 5. Click 'Generate' and use the 16-character password below
EMAIL_USERNAME = "cameronkeplinger@gmail.com"
EMAIL_PASSWORD = "Fordfriendsclub22"

# DeepSeek API key
# This is used for sentiment analysis and market reasoning
DEEPSEEK_API_KEY = "sk-6ab60858c77d42989ea28c76379f7c5a"

# Watchlist symbols to monitor
SYMBOLS = ["OXY", "KO", "SPY", "X", "MDC"]  # Corrected MDC (not MCD)

# Tradier account settings
ACCOUNT_ID = "6YB52094"

# Trading parameters
MAX_POSITIONS = 5  # Maximum number of open positions
POSITION_SIZE = 0.05  # Percentage of account value per position (e.g., 0.05 = 5%)
STOP_LOSS_PERCENT = 0.20  # Exit position if it loses this percentage (e.g., 0.20 = 20%)
TAKE_PROFIT_PERCENT = 0.50  # Exit position if it gains this percentage (e.g., 0.50 = 50%)
MAX_OPTION_DTE = 45  # Maximum days to expiration for option contracts
MIN_OPTION_DTE = 7  # Minimum days to expiration for option contracts

# Technical indicator parameters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
FAST_MA_PERIOD = 20
SLOW_MA_PERIOD = 50

# API Rate Limiting Settings (Based on Tradier documentation)
# Tradier enforces the following rate limits:
# - Standard Endpoints: 120 requests per minute
# - Market Data: 120 requests per minute
# - Trading: 60 requests per minute
MAX_REQUESTS_PER_MINUTE = 100  # Stay below the limit
RETRY_DELAY_SECONDS = 2  # Delay between retries on rate limiting
MAX_RETRIES = 3  # Maximum number of retry attempts