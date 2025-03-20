# config.py - Configuration settings for the options trading bot

# Tradier API access
# Get your API key from https://documentation.tradier.com/brokerage-api
TRADIER_API_KEY = "asvbrhCEAHQMWDARnBOcFaRVPED8"  # Production API key
TRADIER_SANDBOX_KEY = "OglEGAAEnliosD2uB4R0ux9vXxJG"  # Sandbox API key for testing
# Sandbox mode settings
USE_SANDBOX = True
ENABLE_SANDBOX_FALLBACK = True  # Allow simulated trades when sandbox API fails

# API endpoints
TRADIER_PRODUCTION_URL = "https://api.tradier.com/v1"
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"
TRADIER_BASE_URL = TRADIER_SANDBOX_URL if USE_SANDBOX else TRADIER_PRODUCTION_URL

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
SYMBOLS = ["OXY", "KO", "SPY", "X"]  

# Tradier account settings
PRODUCTION_ACCOUNT_ID = "6YB52094"  # Production account ID 
SANDBOX_ACCOUNT_ID = "VA8259127"  # Sandbox account ID for testing
ACCOUNT_ID = SANDBOX_ACCOUNT_ID if USE_SANDBOX else PRODUCTION_ACCOUNT_ID  # Automatically selects correct account based on mode

# Sandbox fallback settings
# If true, will log detailed API responses for debugging
DEBUG_API_RESPONSES = True

# Trading parameters
MAX_POSITIONS = 5  # Maximum number of open positions
POSITION_SIZE = 0.05  # Percentage of account value per position (e.g., 0.05 = 5%)
STOP_LOSS_PERCENT = 0.20  # Exit position if it loses this percentage (e.g., 0.20 = 20%)
TAKE_PROFIT_PERCENT = 0.50  # Exit position if it gains this percentage (e.g., 0.50 = 50%)
MAX_OPTION_DTE = 45  # Maximum days to expiration for option contracts
MIN_OPTION_DTE = 14  # Minimum days to expiration for option contracts

# API request retry settings
MAX_RETRIES = 3  # Maximum number of retries for API requests
RETRY_DELAY_SECONDS = 2  # Initial delay between retries (will be exponentially increased)

# Trading activity settings
CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence to execute a trade (lowered to increase activity)
MAX_DAILY_TRADES = 100  # Maximum number of trades per day
ENABLE_OPPORTUNITY_FINDER = True  # Enable finding opportunities outside watchlist

# Technical indicator parameters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MIN_PRICE_DATA_DAYS = 30  # Minimum days of price data needed for reliable analysis

# Bollinger Bands
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# API Rate Limiting Settings (Based on Tradier documentation)
# Tradier enforces the following rate limits:
# - Standard Endpoints: 120 requests per minute
# - Market Data: 120 requests per minute
# - Trading: 60 requests per minute
MAX_REQUESTS_PER_MINUTE = 100  # Stay below the limit

# Logging settings
LOG_LEVEL = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
CLEAR_LOGS_ON_STARTUP = True  # Clear logs when the bot starts
LOG_TRADE_CONFIRMATIONS = True  # Log detailed trade confirmations