# opportunity_finder.py - Identify trading opportunities beyond the watchlist
import requests
import json
import logging
import pandas as pd
import re
from datetime import datetime, timedelta
from config import DEEPSEEK_API_KEY, PERPLEXITY_API_KEY
from market_data import get_latest_price_data, validate_option_symbol
from strategy import compute_technicals, decide_trade

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("opportunity_finder")

def identify_opportunities(market_news=None, max_opportunities=3):
    """
    Identify potential trading opportunities outside the watchlist based on 
    market news and AI analysis.
    
    Args:
        market_news (str, optional): Pre-fetched market news. If None, will fetch fresh news.
        max_opportunities (int): Maximum number of opportunities to identify
        
    Returns:
        list: List of dictionaries containing opportunity details
    """
    logger.info("Searching for trading opportunities outside watchlist")
    
    # Fetch market news if not provided
    if not market_news:
        market_news = fetch_opportunity_news()
    
    # Extract potential ticker symbols from news
    potential_tickers = extract_tickers_from_news(market_news)
    logger.info(f"Extracted {len(potential_tickers)} potential tickers from news")
    
    # Filter tickers to those with significant movement or interest
    filtered_tickers = filter_interesting_tickers(potential_tickers)
    logger.info(f"Filtered to {len(filtered_tickers)} interesting tickers")
    
    # Analyze each ticker with DeepSeek to determine trading potential
    opportunities = []
    for ticker in filtered_tickers[:max_opportunities*4]:  # Process more than needed in case some fail
        try:
            opportunity = analyze_ticker_opportunity(ticker, market_news)
            if opportunity and opportunity['confidence'] >= 0.6:  # Only include high confidence opportunities
                opportunities.append(opportunity)
                logger.info(f"Found high-confidence opportunity for {ticker}")
                
                # Stop once we have enough opportunities
                if len(opportunities) >= max_opportunities:
                    break
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {str(e)}")
    
    logger.info(f"Identified {len(opportunities)} actionable trading opportunities")
    return opportunities

def fetch_opportunity_news():
    """
    Fetch market news specifically focused on identifying trading opportunities
    
    Returns:
        str: News summary focused on potential trading opportunities
    """
    logger.info("Fetching news for opportunity identification")
    
    query = f"What are the top 10 stocks with unusual options activity or significant news catalysts today? List the stock ticker with \"$\" before it ({datetime.now().strftime('%Y-%m-%d')})? Focus on stocks with high volatility and clear directional signals."
    
    if PERPLEXITY_API_KEY and PERPLEXITY_API_KEY != "your_perplexity_api_key":
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}"
            }
            
            data = {
                "model": "sonar-deep-research",
                "messages": [
                    {"role": "system", "content": "You are a financial analyst specializing in identifying unusual options activity and stocks with significant news catalysts. Focus on providing actionable trading opportunities with clear directional bias."},
                    {"role": "user", "content": query}
                ]
            }
            
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                news = result['choices'][0]['message']['content']
                logger.info("Successfully fetched opportunity news from Perplexity")
                return news
            else:
                logger.warning(f"Perplexity API error: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching opportunity news from Perplexity: {str(e)}")
    
    # Fallback to DeepSeek if Perplexity fails
    if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your_deepseek_api_key":
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a financial analyst specializing in identifying unusual options activity and stocks with significant news catalysts. Focus on providing actionable trading opportunities with clear directional bias."},
                    {"role": "user", "content": query}
                ]
            }
            
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                news = result['choices'][0]['message']['content']
                logger.info("Successfully fetched opportunity news from DeepSeek")
                return news
            else:
                logger.warning(f"DeepSeek API error: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching opportunity news from DeepSeek: {str(e)}")
    
    # If all APIs fail, return a message
    logger.error("Failed to fetch opportunity news from all sources")
    return "Unable to fetch market news for opportunity identification."

def extract_tickers_from_news(news_text):
    """
    Extract potential ticker symbols from news text
    
    Args:
        news_text (str): Market news text
        
    Returns:
        list: List of potential ticker symbols
    """
    # Pattern to match ticker symbols (1-5 uppercase letters, often in parentheses)
    ticker_pattern = r'\(([A-Z]{1,5})\)|\b([A-Z]{2,5})\b'
    
    # Common words that might be mistaken for tickers
    common_words = common_words = {
    # Original set
    'A', 'I', 'AM', 'PM', 'CEO', 'VIX', 'CFO', 'CTO', 'AI', 'ML', 'API', 'USA', 'US', 'UK', 'EU', 
    'GDP', 'CPI', 'IPO', 'ETF', 'MACD', 'RSI', 'EPS', 'PE', 'THE', 'FOR', 'AND', 'OR',
    'IS', 'ARE', 'WAS', 'WERE', 'BE', 'BEEN', 'BEING', 'HAVE', 'HAS', 'HAD', 'DO', 'DOES',
    'DID', 'CAN', 'COULD', 'WILL', 'WOULD', 'SHALL', 'SHOULD', 'MAY', 'MIGHT', 'MUST', 'YTD', 
    'NYSE', 'NASDAQ', 'S&P', 'DOW', 'SP', 'DJIA', 'FED', 'QE', 'USD', 'EUR', 'GBP', 'JPY', 'CNY',
    'CAD', 'AUD', 'CHF', 'HKD', 'NZD', 'KRW', 'INR', 'NHTSA', 'BOJ', 'ECB', 'IMF', 'WTO', 'OPEC',
    'DXY', 'TSX', 'FTSE', 'DAX', 'BNPL', 'SEC', 'FINRA', 'WTI', 'ESG', 'FOMC', 'COP', 'NFT', 'CBDC',
    'CDC', 'WHO', 'FDA', 'EPA', 'DOJ', 'IRS', 'CIA', 'FBI', 'NSA', 'DEA', 'DOE', 'DOD', 'HHS', 'DHS',
    'QQQ', 'SSE', 'HSI', 'ASX', 'BTC', 'ETH', 'LTC', 'XRP', 'USDT', 'USDC', 'BNB', 'SOL', 'ADA', 'DOT',
    
    # Common financial terms
    'APR', 'APY', 'ATH', 'ATL', 'ATM', 'AUM', 'BPS', 'CAGR', 'CAPE', 'CBOE', 'COO', 'CRO', 'DCF', 'DD',
    'EBIT', 'EBITDA', 'EMH', 'EOD', 'EOM', 'EOY', 'EV', 'FANG', 'FAANG', 'GAAP', 'ICO', 'IRR', 'KPI', 'LBO',
    'LIBOR', 'LTCG', 'MBS', 'MOM', 'NAV', 'NOI', 'NPV', 'OTC', 'P2P', 'PEG', 'PPP', 'QOQ', 'ROA', 'ROE',
    'ROI', 'ROIC', 'ROR', 'SaaS', 'SMA', 'SOFR', 'SPAC', 'STCG', 'TTM', 'VAR', 'WACC', 'YOY',
    
    # Common words that are actual tickers
    'ALL', 'GOOD', 'REAL', 'TRUE', 'FAST', 'SAFE', 'CASH', 'PLAY', 'LIFE', 'LOVE', 'PEAK', 'CUBE', 'WELL',
    'LAND', 'LUNG', 'LEG', 'CAT', 'DOG', 'SKY', 'DISH', 'COLD', 'CONE', 'FORD', 'ZION', 'RCM', 'MDC', 'F',
    'BIG', 'NOW', 'GO', 'ON', 'OUT', 'UP', 'DOWN', 'LOW', 'HIGH', 'EVER', 'NEXT', 'LAST', 'FIRST', 'BEST',
    
    # Trading slang and jargon
    'ATH', 'BTFD', 'FOMO', 'FUD', 'HODL', 'MOON', 'YOLO', 'BULL', 'BEAR', 'TIGER', 'WHALE',
    
    # Common abbreviations
    'AN', 'AS', 'AT', 'BY', 'IF', 'IN', 'IT', 'ME', 'MY', 'NO', 'OF', 'OH', 'OK', 'ON', 'SO', 'TO', 'UP',
    'WE', 'AMP', 'INC', 'LLC', 'LTD', 'PLC', 'AG', 'SA', 'SE', 'NV', 'BV', 'CO', 'LLP', 'LP', 'GP',
    
    # Common text/chat abbreviations
    'IM', 'U', 'UR', 'R', 'B', 'C', 'K', 'N', 'Y', 'IDK', 'IMO', 'TBH', 'BTW', 'FYI', 'ICYMI', 'NGL',
    
    # Time-related
    'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
    'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN', 'Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2',
    
    # Measurements and units
    'KG', 'LB', 'OZ', 'CM', 'MM', 'KM', 'MI', 'FT', 'IN', 'HR', 'MIN', 'SEC', 'GB', 'MB', 'TB', 'KB',
    
    # Other common abbreviations
    'CEO', 'CFO', 'COO', 'CTO', 'CMO', 'CIO', 'CSO', 'CDO', 'CHRO', 'CPO', 'EVP', 'SVP', 'VP', 'AVP',
    'PhD', 'MBA', 'MD', 'JD', 'BS', 'BA', 'MS', 'MA', 'CFA', 'CPA', 'ACCA', 'CIMA', 'CAIA',
    
    # Technology terms
    'AR', 'VR', 'XR', 'IoT', 'ML', 'DL', 'NLP', 'CV', 'UI', 'UX', 'API', 'SDK', 'IDE', 'SQL', 'NoSQL',
    'AWS', 'GCP', 'AI', 'ML', 'GPU', 'CPU', 'RAM', 'ROM', 'SSD', 'HDD', 'LAN', 'WAN', 'VPN', 'DNS',
    
    # Social media
    'FB', 'IG', 'TW', 'YT', 'LI', 'PIN', 'SC', 'TT', 'WA', 'DC',
    
    # Filler words
    'THE', 'AN', 'A', 'BUT', 'BY', 'FROM', 'WITH', 'WITHOUT', 'ABOUT', 'ABOVE', 'BELOW', 'UNDER', 'OVER',
    'BETWEEN', 'AMONG', 'THROUGH', 'THROUGHOUT', 'DURING', 'BEFORE', 'AFTER', 'SINCE', 'UNTIL', 'WHILE'
}

    
    # Find all matches
    matches = re.findall(ticker_pattern, news_text)
    
    # Process matches
    tickers = set()
    for match in matches:
        # Each match is a tuple with two groups, one of which might be empty
        ticker = match[0] if match[0] else match[1]
        
        # Skip common words and ensure minimum length
        if ticker not in common_words and len(ticker) >= 2:
            tickers.add(ticker)
    
    return list(tickers)

def filter_interesting_tickers(tickers, min_volume=500000):
    """
    Filter tickers to those with significant trading volume or price movement
    
    Args:
        tickers (list): List of potential ticker symbols
        min_volume (int): Minimum trading volume to consider interesting
        
    Returns:
        list: Filtered list of ticker symbols
    """
    interesting_tickers = []
    
    for ticker in tickers:
        try:
            # Get latest price data
            price_data = get_latest_price_data(ticker, lookback_days=5)
            
            # Skip if we couldn't get price data
            if price_data.empty:
                continue
            
            # Check if volume is significant
            recent_volume = price_data['volume'].iloc[-1] if 'volume' in price_data.columns else 0
            
            # Check for significant price movement (>2% in last day)
            if len(price_data) >= 2:
                price_change_pct = abs((price_data['close'].iloc[-1] / price_data['close'].iloc[-2] - 1) * 100)
            else:
                price_change_pct = 0
            
            # Add ticker if it meets criteria
            if recent_volume >= min_volume or price_change_pct >= 2:
                interesting_tickers.append(ticker)
                
        except Exception as e:
            logger.warning(f"Error checking ticker {ticker}: {str(e)}")
    
    return interesting_tickers

def analyze_ticker_opportunity(ticker, market_news):
    """
    Analyze a specific ticker for trading opportunities using DeepSeek
    
    Args:
        ticker (str): Ticker symbol to analyze
        market_news (str): Market news for context
        
    Returns:
        dict or None: Opportunity details if found, None otherwise
    """
    logger.info(f"Analyzing potential opportunity for {ticker}")
    
    try:
        # Get price data for technical analysis
        price_data = get_latest_price_data(ticker, lookback_days=60)
        
        if price_data.empty:
            logger.warning(f"No price data available for {ticker}")
            return None
        
        # Compute technical indicators
        technicals = compute_technicals(price_data)
        
        # Extract ticker-specific news from the general market news
        ticker_news = extract_ticker_specific_news(ticker, market_news)
        
        # Use DeepSeek to analyze the opportunity
        sentiment, reasoning, signal = analyze_with_deepseek_opportunity(ticker, ticker_news, technicals, price_data)
        
        # Only proceed if we have a clear signal
        if not signal or signal == 'NEUTRAL':
            logger.info(f"No clear trading signal for {ticker}")
            return None
        
        # Calculate confidence based on sentiment strength and technical alignment
        confidence = calculate_confidence(sentiment, technicals, price_data, signal)
        
        # Create opportunity object
        opportunity = {
            'ticker': ticker,
            'signal': signal,  # 'BUY_CALL' or 'BUY_PUT'
            'sentiment': sentiment,
            'reasoning': reasoning,
            'confidence': confidence,
            'price': price_data['close'].iloc[-1],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Check YTD performance
        ytd_data = price_data.get('ytd', {})
        if ytd_data and isinstance(ytd_data, dict):
            price_change = ytd_data.get('price_change')
            if price_change is not None:
                if price_change > 0.2:  # 20% YTD gain
                    logger.info(f"{ticker} has strong YTD performance: {price_change:.0%}")
                    opportunity['ytd_performance'] = 'strong'
                elif price_change < -0.2:  # 20% YTD loss
                    logger.info(f"{ticker} has poor YTD performance: {price_change:.0%}")
                    opportunity['ytd_performance'] = 'poor'
        else:
            logger.warning(f"Insufficient YTD data for {ticker}")
            opportunity['ytd_performance'] = 'unknown'
        
        return opportunity
        
    except Exception as e:
        logger.error(f"Error analyzing opportunity for {ticker}: {str(e)}")
        return None

def extract_ticker_specific_news(ticker, market_news):
    """
    Extract news specific to a ticker from general market news
    
    Args:
        ticker (str): Ticker symbol
        market_news (str): General market news
        
    Returns:
        str: News specific to the ticker
    """
    # Split news into paragraphs
    paragraphs = market_news.split('\n')
    
    # Find paragraphs mentioning the ticker
    ticker_paragraphs = []
    for paragraph in paragraphs:
        if re.search(r'\b' + re.escape(ticker) + r'\b|\(' + re.escape(ticker) + r'\)', paragraph):
            ticker_paragraphs.append(paragraph)
    
    # If we found specific paragraphs, join them
    if ticker_paragraphs:
        return '\n'.join(ticker_paragraphs)
    
    # Otherwise, return a generic message with the full news
    return f"Analyzing {ticker} in the context of today's market. General market news: {market_news[:500]}..."

def analyze_with_deepseek_opportunity(ticker, ticker_news, technicals, price_data):
    """
    Use DeepSeek to analyze a specific ticker opportunity
    
    Args:
        ticker (str): Ticker symbol
        ticker_news (str): News specific to the ticker
        technicals (dict): Technical indicators
        price_data (pandas.DataFrame): Price data
        
    Returns:
        tuple: (sentiment, reasoning, signal)
    """
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_api_key":
        logger.error("DeepSeek API key not configured")
        return "neutral", "API key not configured", "NEUTRAL"
    
    # Prepare price data summary
    current_price = price_data['close'].iloc[-1]
    price_change = (current_price / price_data['close'].iloc[-2] - 1) * 100 if len(price_data) > 1 else 0
    
    # Create prompt for DeepSeek
    prompt = f"""
    Analyze {ticker} for options trading opportunities based on the following:
    
    NEWS:
    {ticker_news}
    
    TECHNICAL INDICATORS:
    - RSI: {technicals.get('rsi', 'N/A')}
    - 20-day MA: {technicals.get('ma20', 'N/A')}
    - 50-day MA: {technicals.get('ma50', 'N/A')}
    
    PRICE ACTION:
    - Current Price: ${current_price:.2f}
    - 1-day Change: {price_change:.2f}%
    
    Based on this information, determine if there's a strong case for buying call options (bullish) or put options (bearish).
    Provide your sentiment (bullish/bearish/neutral), detailed reasoning, and a clear trading signal (BUY_CALL/BUY_PUT/NEUTRAL).
    """
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a professional options trader with expertise in technical analysis and market sentiment. Your task is to analyze stocks for clear directional trading opportunities."},
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            analysis = result['choices'][0]['message']['content']
            
            # Extract sentiment, reasoning, and signal from the analysis
            sentiment = "neutral"
            if re.search(r'\bbullish\b', analysis.lower()):
                sentiment = "bullish"
            elif re.search(r'\bbearish\b', analysis.lower()):
                sentiment = "bearish"
            
            # Extract signal
            signal = "NEUTRAL"
            if re.search(r'\bBUY_CALL\b', analysis):
                signal = "BUY_CALL"
            elif re.search(r'\bBUY_PUT\b', analysis):
                signal = "BUY_PUT"
            
            # Use the full analysis as reasoning
            reasoning = analysis
            
            return sentiment, reasoning, signal
        else:
            logger.warning(f"DeepSeek API error: {response.status_code}")
            return "neutral", f"API error: {response.status_code}", "NEUTRAL"
    
    except Exception as e:
        logger.error(f"Error analyzing with DeepSeek: {str(e)}")
        return "neutral", f"Analysis error: {str(e)}", "NEUTRAL"

def calculate_confidence(sentiment, technicals, price_data, signal):
    """
    Calculate confidence score for a trading opportunity
    
    Args:
        sentiment (str): Sentiment from AI analysis
        technicals (dict): Technical indicators
        price_data (pandas.DataFrame): Price data
        signal (str): Trading signal
        
    Returns:
        float: Confidence score between 0 and 1
    """
    confidence = 0.5  # Base confidence
    
    # Adjust based on RSI
    if technicals.get('rsi') is not None:
        rsi = technicals['rsi']
        if signal == 'BUY_CALL' and rsi < 70:
            confidence += 0.1  # Not overbought
            if 40 <= rsi <= 60:
                confidence += 0.05  # In neutral territory with upward potential
        elif signal == 'BUY_PUT' and rsi > 30:
            confidence += 0.1  # Not oversold
            if rsi >= 70:
                confidence += 0.1  # Overbought
    
    # Adjust based on moving averages
    if technicals.get('ma20') is not None and technicals.get('ma50') is not None:
        current_price = price_data['close'].iloc[-1]
        ma20 = technicals['ma20']
        ma50 = technicals['ma50']
        
        # Check for golden/death cross
        if signal == 'BUY_CALL' and ma20 > ma50:
            confidence += 0.1  # Golden cross (bullish)
        elif signal == 'BUY_PUT' and ma20 < ma50:
            confidence += 0.1  # Death cross (bearish)
        
        # Check price relative to MAs
        if signal == 'BUY_CALL' and current_price > ma20 and current_price > ma50:
            confidence += 0.1  # Price above both MAs (bullish)
        elif signal == 'BUY_PUT' and current_price < ma20 and current_price < ma50:
            confidence += 0.1  # Price below both MAs (bearish)
    
    # Adjust based on recent price movement
    if len(price_data) >= 5:
        five_day_change = (price_data['close'].iloc[-1] / price_data['close'].iloc[-5] - 1) * 100
        
        if signal == 'BUY_CALL' and five_day_change > 0:
            confidence += 0.05  # Positive momentum
        elif signal == 'BUY_PUT' and five_day_change < 0:
            confidence += 0.05  # Negative momentum
    
    # Cap confidence at 1.0
    return min(confidence, 1.0)

def process_opportunities(opportunities, tradier_client):
    """
    Process identified opportunities and execute trades
    
    Args:
        opportunities (list): List of opportunity dictionaries
        tradier_client: TradierClient instance for executing trades
        
    Returns:
        list: List of executed trades
    """
    from strategy import select_option_contract
    from trade_tracker import get_trade_tracker
    
    executed_trades = []
    trade_tracker = get_trade_tracker()
    
    # Check account balance to determine if PDT rules apply
    account_info = tradier_client.get_account_balances()
    account_value = float(account_info.get('total_equity', 0))
    pdt_applies = account_value < 25000
    
    logger.info(f"Account value: ${account_value:.2f} - PDT rules apply: {pdt_applies}")
    
    # Check if we can make day trades
    if pdt_applies and not trade_tracker.can_day_trade():
        logger.warning("Cannot execute day trades - PDT limit reached (3 day trades in 5 business days)")
        logger.info("Only executing trades intended to be held overnight")
    
    # Sort opportunities by confidence (highest first)
    sorted_opportunities = sorted(opportunities, key=lambda x: x.get('confidence', 0), reverse=True)
    
    for opportunity in sorted_opportunities:
        try:
            ticker = opportunity['ticker']
            signal = opportunity['signal']
            confidence = opportunity['confidence']
            
            logger.info(f"Processing opportunity for {ticker} with signal {signal} (confidence: {confidence:.2f})")
            
            # Only trade high confidence opportunities
            if confidence < 0.70:  # Lowered threshold to increase trading activity
                logger.info(f"Skipping {ticker} due to insufficient confidence ({confidence:.2f})")
                continue
            
            # Get price data for the ticker
            try:
                price_data = get_latest_price_data(ticker)
                
                if price_data.empty:
                    logger.warning(f"No price data available for {ticker}")
                    continue
                    
                if len(price_data) < 20:  # Minimum required data points
                    logger.warning(f"Insufficient historical data for {ticker} (only {len(price_data)} days available, need at least 20)")
                    continue
            except Exception as e:
                logger.error(f"Error retrieving price data for {ticker}: {str(e)}")
                continue
            
            # Select appropriate option contract
            contract = select_option_contract(ticker, signal, price_data)
            
            if not contract:
                logger.warning(f"Could not select appropriate option contract for {ticker}")
                continue
            
            # Validate option symbol format
            if not contract or not isinstance(contract, str) or len(contract) < 15:
                logger.warning(f"Invalid option contract format: {contract}")
                continue
                
            # Validate option symbol against available option chains
            from market_data import validate_option_symbol
            is_valid, valid_alternative, expiration_date = validate_option_symbol(contract, ticker)
            
            if not is_valid:
                if valid_alternative:
                    logger.warning(f"Option symbol {contract} not found, using alternative: {valid_alternative}")
                    contract = valid_alternative
                    # Don't validate the alternative again - it came directly from the API and is valid
                else:
                    logger.warning(f"Option symbol {contract} not available for trading")
                    continue
            
            # Determine number of contracts based on confidence and account size
            # Higher confidence = more contracts, scaled by account size
            base_contracts = 1
            if confidence > 0.9:
                base_contracts = 3
            elif confidence > 0.8:
                base_contracts = 2
            
            # Scale by account size (simplified approach)
            account_scale = min(3, max(1, int(account_value / 10000)))
            num_contracts = base_contracts * account_scale
            
            # Execute the trade
            trade_result = execute_opportunity_trade(
                ticker, 
                contract, 
                signal, 
                tradier_client, 
                num_contracts, 
                day_trade_allowed=(not pdt_applies or trade_tracker.can_day_trade())
            )
            
            if trade_result and "error" not in trade_result:
                executed_trades.append({
                    'ticker': ticker,
                    'contract': contract,
                    'signal': signal,
                    'confidence': confidence,
                    'contracts': num_contracts,
                    'result': trade_result,
                    'order_id': trade_result.get('id', 'unknown')
                })
                logger.info(f"Successfully executed trade for {ticker} ({num_contracts} contracts)")
                
                # Check order status after a brief delay to confirm it's being processed
                if 'id' in trade_result:
                    import time
                    time.sleep(2)  # Brief pause to allow order processing
                    order_status = tradier_client.get_order_status(trade_result['id'])
                    if order_status:
                        logger.info(f"Order status confirmation: {order_status.get('status', 'unknown')}")
            else:
                error_msg = trade_result.get('error', 'Unknown error') if isinstance(trade_result, dict) else 'Failed to execute trade'
                logger.warning(f"Trade execution failed for {ticker}: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error processing opportunity for {ticker}: {str(e)}")
    
    return executed_trades

def execute_opportunity_trade(ticker, contract, signal, tradier_client, num_contracts=1, day_trade_allowed=True):
    """
    Execute a trade for an identified opportunity
    
    Args:
        ticker (str): Ticker symbol
        contract (str): Option contract symbol
        signal (str): Trading signal (BUY_CALL or BUY_PUT)
        tradier_client: TradierClient instance
        num_contracts (int): Number of contracts to trade
        day_trade_allowed (bool): Whether day trades are allowed
        
    Returns:
        dict or None: Trade result if successful, None otherwise
    """
    from trade_tracker import get_trade_tracker
    import sys
    import os
    
    # Import is_market_open from main.py
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from main import is_market_open
    
    try:
        # Check if market is open before placing trade
        if not is_market_open():
            logger.warning(f"Cannot execute trade for {ticker} ({contract}) - market is closed")
            return {"error": "Market is closed", "status": "rejected"}
            
        # Validate option symbol format
        if not contract or not isinstance(contract, str) or len(contract) < 15:
            logger.warning(f"Invalid option contract format: {contract}")
            return {"error": f"Invalid option contract format: {contract}", "status": "rejected"}
            
        # Determine trade parameters
        quantity = max(1, num_contracts)  # Ensure at least 1 contract
        
        # Set trade duration based on PDT status
        # If day trades aren't allowed, use GTC to indicate this is meant to be held overnight
        duration = 'day' if day_trade_allowed else 'gtc'
        
        # Determine the side based on the signal
        if signal == 'BUY_CALL':
            side = 'buy_to_open'
        elif signal == 'BUY_PUT':
            side = 'buy_to_open'
        elif signal == 'SELL_CALL':
            side = 'sell_to_close'
        elif signal == 'SELL_PUT':
            side = 'sell_to_close'
        else:
            side = 'buy_to_open'  # Default
        
        # Execute the trade using the updated method
        order_result = tradier_client.place_option_order(
            option_symbol=contract,
            symbol=ticker,
            side=side,
            quantity=quantity,
            duration=duration
        )
        
        # Check if order was successful
        if isinstance(order_result, dict) and "error" in order_result:
            logger.warning(f"Trade failed for {ticker} ({contract}): {order_result['error']}")
            return order_result
        
        # If this is a day trade, record it
        if day_trade_allowed and duration == 'day':
            trade_tracker = get_trade_tracker()
            trade_tracker.add_day_trade(ticker, quantity)
        
        # Log the trade
        if 'log_trade' in globals():
            from main import log_trade
            log_trade((ticker, contract, signal, quantity, datetime.now()))
        else:
            logger.info(f"Trade executed: {ticker} {contract} {signal} {quantity} contracts")
        
        logger.info(f"Successfully executed trade for {ticker} ({quantity} contracts)")
        return order_result
    
    except Exception as e:
        logger.error(f"Error executing trade for {ticker}: {str(e)}")
        return {"error": str(e), "status": "error"}

def analyze_market_news(news_data):
    """
    Analyze market news for trading opportunities
    
    Args:
        news_data (dict): Raw market news data from API
    """
    if not news_data or not isinstance(news_data, dict):
        logger.warning("Invalid or empty market news data received")
        return []

    try:
        articles = news_data.get('articles', [])
        if not isinstance(articles, list):
            logger.warning("Unexpected format for market news articles")
            return []

        potential_tickers = set()
        for article in articles:
            if not isinstance(article, dict):
                continue
            
            # Extract tickers from title and content
            title = article.get('title', '')
            content = article.get('content', '')
            
            # Use regex to find potential tickers
            tickers = re.findall(r'\b[A-Z]{2,5}\b', f"{title} {content}")
            potential_tickers.update(tickers)

        logger.info(f"Extracted {len(potential_tickers)} potential tickers from news")
        return list(potential_tickers)

    except Exception as e:
        logger.error(f"Error analyzing market news: {str(e)}")
        return []
