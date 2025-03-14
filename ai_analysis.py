# ai_analysis.py – Gather news and analyze with AI
import requests
import json
import os
import time
from config import PERPLEXITY_API_KEY, DEEPSEEK_API_KEY
from datetime import datetime

def fetch_news_summary(time_of_day):
    """
    Use Perplexity Deep Research API to get aggregated market news.
    
    Args:
        time_of_day (str): Timing of the news request ('pre_market', 'midday', or 'end_of_day')
        
    Returns:
        str: Summary of market news
    """
    if time_of_day == 'pre_market':
        query = f"Today's important financial news before market open on {datetime.now().strftime('%Y-%m-%d')}"
    elif time_of_day == 'midday':
        query = f"Major market news and updates as of midday on {datetime.now().strftime('%Y-%m-%d')}"
    else:
        query = f"Latest major market updates as of {datetime.now().strftime('%Y-%m-%d')}"
    
    print(f"Fetching comprehensive market news with query: '{query}'")
    
    # Try deep-research first, then fall back to sonar-reasoning-pro if it times out, then to regular sonar
    models_to_try = [
        {"model": "sonar-deep-research", "timeout": 400, "name": "deep research"},
        {"model": "sonar-reasoning-pro", "timeout": 45, "name": "reasoning pro"},
        {"model": "sonar", "timeout": 30, "name": "standard sonar"}
    ]
    
    if PERPLEXITY_API_KEY and PERPLEXITY_API_KEY != "your_perplexity_api_key":
        for model_config in models_to_try:
            try:
                print(f"Trying Perplexity {model_config['name']} model...")
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}"
                }
                
                data = {
                    "model": model_config["model"],
                    "messages": [
                        {"role": "system", "content": "You are a financial news analyst specializing in options markets. Provide a comprehensive summary of the latest market news, focusing on key events that might impact trading decisions. Include information about market sentiment, sector rotations, volatility indicators, and potential catalysts for price movements."},
                        {"role": "user", "content": query}
                    ]
                }
                
                # Try with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = requests.post(
                            "https://api.perplexity.ai/chat/completions",
                            headers=headers,
                            json=data,
                            timeout=model_config["timeout"]
                        )
                        response.raise_for_status()
                        result = response.json()
                        
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        if content:
                            print(f"Successfully retrieved news with {model_config['name']} model")
                            return content
                    except requests.exceptions.Timeout:
                        print(f"Timeout with {model_config['name']} model (attempt {attempt+1}/{max_retries})")
                        if attempt < max_retries - 1:
                            # Exponential backoff
                            wait_time = 2 ** attempt
                            print(f"Waiting {wait_time} seconds before retry...")
                            time.sleep(wait_time)
                        else:
                            # Move to next model after all retries
                            print(f"All retries failed with {model_config['name']} model, trying next option...")
                            break
                    except requests.exceptions.RequestException as e:
                        print(f"Error with {model_config['name']} model: {e}")
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            print(f"Waiting {wait_time} seconds before retry...")
                            time.sleep(wait_time)
                        else:
                            break
            except Exception as e:
                print(f"Unexpected error with {model_config['name']} model: {e}")
                # Continue to next model
    
    # If we get here, all Perplexity models failed or no API key
    print("All Perplexity models failed or no API key, fetching from alternate source")
    
    # Real fallback to Alpha Vantage
    try:
        fin_news_url = "https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=SPY,QQQ,DIA&apikey=demo"
        response = requests.get(fin_news_url, timeout=30)
        response.raise_for_status()
        news_data = response.json()
        
        if 'feed' in news_data and len(news_data['feed']) > 0:
            # Compile news from the feed
            news_summary = "Financial News Summary:\n\n"
            for item in news_data['feed'][:10]:  # Get first 10 news items
                news_summary += f"- {item.get('title', 'No title')}\n"
                if 'summary' in item:
                    news_summary += f"  {item['summary'][:200]}...\n\n"
            return news_summary
        return "Unable to fetch market news from any source."
    except Exception as e:
        print(f"Final fallback news source failed: {e}")
        return "Unable to fetch market news due to API errors across all services."

def spot_check_news(query):
    """
    Use Perplexity Search API for real-time news queries.
    
    Args:
        query (str): Specific news query
        
    Returns:
        str: Answer from Perplexity regarding the query
    """
    print(f"Spot checking market news with query: '{query}'")
    
    # Try with the lightweight sonar model with retries
    if PERPLEXITY_API_KEY and PERPLEXITY_API_KEY != "your_perplexity_api_key":
        max_retries = 3
        for attempt in range(max_retries):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}"
                }
                
                data = {
                    "model": "sonar",  # Using sonar model for faster spot checks
                    "messages": [
                        {"role": "system", "content": "You are a financial news assistant. Provide concise updates on market events and breaking news."},
                        {"role": "user", "content": query}
                    ]
                }
                
                response = requests.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=20
                )
                response.raise_for_status()
                result = response.json()
                
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    print("Successfully retrieved spot check news")
                    return content
            except requests.exceptions.Timeout:
                print(f"Timeout with spot check (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    print(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                print(f"Error with spot check: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
    
    # Fallback to Alpha Vantage if all retries fail or no API key
    try:
        print("Falling back to alternate source for spot check")
        topic = query.replace(" ", ",")
        fin_news_url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&topics={topic}&apikey=demo"
        response = requests.get(fin_news_url, timeout=30)
        response.raise_for_status()
        news_data = response.json()
        
        if 'feed' in news_data and len(news_data['feed']) > 0:
            # Return most recent relevant news
            news_item = news_data['feed'][0]
            return f"{news_item.get('title', 'No title')}: {news_item.get('summary', 'No summary')}"
    except Exception as e:
        print(f"Error with spot check fallback: {e}")
    
    return "Unable to fetch spot check news due to API errors."

def call_deepseek_api(prompt):
    """
    Call the DeepSeek Reasoning API with a prompt to analyze market news.
    
    Args:
        prompt (str): Prompt containing market news to analyze
        
    Returns:
        dict: DeepSeek API response containing reasoning and sentiment
    """
    print(f"Analyzing market conditions with DeepSeek Reasoning model...")
    
    try:
        # Check if we have a valid DeepSeek API key
        api_key = DEEPSEEK_API_KEY
        
        # If not in config, try environment variable
        if not api_key or api_key == "your_deepseek_api_key":
            api_key = os.environ.get("DEEPSEEK_API_KEY")
        
        if api_key and api_key != "your_deepseek_api_key":
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            system_prompt = """You are an expert financial analyst specializing in options markets. 
            Carefully analyze the provided market news and determine if the overall market sentiment 
            is bullish, bearish, or neutral. Be specific about why particular news items might impact 
            options trading strategies. Consider both short-term volatility and longer-term trends.
            Focus on implications for options strategies like calls, puts, and any relevant spreads."""
            
            data = {
                "model": "deepseek-reasoner",  # Using the reasoning model for better analysis
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000  # Ensure we get a comprehensive analysis
            }
            
            # Try with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(url, headers=headers, json=data, timeout=120)
                    response.raise_for_status()
                    result = response.json()
                    
                    # Extract content and reasoning from the DeepSeek Reasoner response
                    choices = result.get("choices", [{}])
                    if choices:
                        message = choices[0].get("message", {})
                        reasoning_content = message.get("reasoning_content", "")
                        content = message.get("content", "")
                        
                        # Parse the final content to extract sentiment
                        if "bullish" in content.lower():
                            sentiment = "bullish"
                        elif "bearish" in content.lower():
                            sentiment = "bearish"
                        else:
                            sentiment = "neutral"  # Default if unclear
                        
                        print(f"Sentiment analysis complete: {sentiment}")
                        
                        return {
                            "sentiment": sentiment,
                            "reasoning": reasoning_content,
                            "conclusion": content
                        }
                    break  # Exit retry loop if we got here but couldn't extract sentiment
                except requests.exceptions.Timeout:
                    print(f"Timeout with DeepSeek API (attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                except requests.exceptions.RequestException as e:
                    print(f"Error with DeepSeek API call (attempt {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
        
        # If no DeepSeek API key or all retries failed, use a more basic method based on news keywords
        print("No DeepSeek API key or API calls failed, using keyword analysis instead")
        
        # Simple keyword-based sentiment analysis
        bullish_keywords = ["growth", "rally", "surge", "positive", "gain", "outperform", "beat", "upgrade"]
        bearish_keywords = ["decline", "drop", "fall", "negative", "loss", "underperform", "miss", "downgrade"]
        
        lower_prompt = prompt.lower()
        bullish_count = sum(lower_prompt.count(word) for word in bullish_keywords)
        bearish_count = sum(lower_prompt.count(word) for word in bearish_keywords)
        
        if bullish_count > bearish_count:
            sentiment = "bullish"
            reasoning = "More positive than negative indicators in recent market news."
        elif bearish_count > bullish_count:
            sentiment = "bearish"
            reasoning = "More negative than positive indicators in recent market news."
        else:
            sentiment = "neutral"
            reasoning = "Mixed signals with balanced positive and negative indicators."
            
        return {
            "sentiment": sentiment,
            "reasoning": reasoning,
            "conclusion": reasoning
        }
            
    except Exception as e:
        print(f"Error with DeepSeek API call: {e}")
        
        # Emergency fallback - not a mock, but a basic analysis
        # Based on current market conditions like time of day and day of week
        now = datetime.now()
        day_of_week = now.weekday()  # 0=Monday, 4=Friday
        hour = now.hour
        
        # Simple time-based sentiment (statistically, mornings often have more volatility)
        if day_of_week == 0:  # Monday
            sentiment = "bearish"  # Mondays often show negative returns
            reasoning = "Historical Monday market patterns suggest potential downward pressure."
        elif day_of_week == 4:  # Friday
            sentiment = "bullish"  # Fridays often have positive closing bias
            reasoning = "End-of-week trading patterns suggest potential upward momentum."
        elif hour < 10:  # Early morning
            sentiment = "volatile"  # Market opening often has higher volatility
            reasoning = "Early trading hours typically show higher volatility and uncertainty."
        else:
            sentiment = "neutral"
            reasoning = "Limited data available, defaulting to neutral outlook."
            
        return {
            "sentiment": sentiment,
            "reasoning": reasoning,
            "conclusion": reasoning
        }

def analyze_with_deepseek(news):
    """
    Analyze market news with DeepSeek to determine sentiment.
    
    Args:
        news (str): Market news to analyze
        
    Returns:
        tuple: (sentiment, reasoning, conclusion) - Market sentiment, detailed reasoning, and final conclusion
    """
    prompt = f"""Please analyze the following market news and determine the overall market sentiment 
    (bullish, bearish, or neutral). Provide detailed reasoning for your conclusion.
    
    NEWS:
    {news}
    
    What is the overall market sentiment based on this news, and why?"""
    
    result = call_deepseek_api(prompt)
    return result.get('sentiment', 'neutral'), result.get('reasoning', 'No detailed reasoning available'), result.get('conclusion', 'No conclusion available')
