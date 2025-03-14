# test_opportunity_finder.py - Test the opportunity finder functionality
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import json
import logging
from datetime import datetime

# Import the function to test
from opportunity_finder import (
    identify_opportunities, 
    fetch_opportunity_news,
    extract_tickers_from_news,
    filter_interesting_tickers,
    analyze_ticker_opportunity
)

# Set up logging to a test log file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_opportunity_finder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_opportunity_finder")

class TestOpportunityFinder(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Sample market news for testing
        self.sample_news = """
        Market News for Testing:
        Apple (AAPL) announced a new product line that analysts expect to boost revenue.
        Tesla (TSLA) reported better than expected earnings, stock up 5% in pre-market.
        Microsoft (MSFT) is facing regulatory scrutiny over recent acquisitions.
        Meta (META) unveiled new AI features for its social media platforms.
        """
        
        # Sample price data for testing
        self.sample_price_data = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=100),
            'open': [100 + i*0.1 for i in range(100)],
            'high': [105 + i*0.1 for i in range(100)],
            'low': [95 + i*0.1 for i in range(100)],
            'close': [102 + i*0.1 for i in range(100)],
            'volume': [1000000 + i*1000 for i in range(100)]
        })
    
    @patch('opportunity_finder.fetch_opportunity_news')
    def test_extract_tickers_from_news(self, mock_fetch_news):
        """Test the ticker extraction functionality"""
        # Mock the news fetching function
        mock_fetch_news.return_value = self.sample_news
        
        # Test ticker extraction
        tickers = extract_tickers_from_news(self.sample_news)
        
        # Assert that the expected tickers are found
        expected_tickers = ['AAPL', 'TSLA', 'MSFT', 'META']
        for ticker in expected_tickers:
            self.assertIn(ticker, tickers, f"Expected ticker {ticker} not found in extracted tickers")
        
        # Assert that common words are not mistakenly identified as tickers
        common_words = ['AI', 'UP', 'IS']
        for word in common_words:
            if word in tickers:
                self.fail(f"Common word {word} was incorrectly identified as a ticker")
        
        logger.info(f"Successfully extracted tickers: {tickers}")
    
    @patch('opportunity_finder.get_latest_price_data')
    def test_filter_interesting_tickers(self, mock_get_price_data):
        """Test the ticker filtering functionality"""
        # Mock the price data function
        mock_get_price_data.return_value = self.sample_price_data
        
        # Test ticker filtering
        tickers = ['AAPL', 'TSLA', 'MSFT', 'META']
        filtered_tickers = filter_interesting_tickers(tickers, min_volume=500000)
        
        # Since our mock returns valid price data for all tickers, all should pass the filter
        self.assertEqual(len(filtered_tickers), len(tickers), 
                         "All tickers should pass the filter with our mock data")
        
        logger.info(f"Successfully filtered tickers: {filtered_tickers}")
    
    @patch('opportunity_finder.analyze_ticker_opportunity')
    @patch('opportunity_finder.filter_interesting_tickers')
    @patch('opportunity_finder.extract_tickers_from_news')
    @patch('opportunity_finder.fetch_opportunity_news')
    def test_identify_opportunities(self, mock_fetch_news, mock_extract_tickers, 
                                   mock_filter_tickers, mock_analyze_ticker):
        """Test the main identify_opportunities function"""
        # Set up mocks
        mock_fetch_news.return_value = self.sample_news
        mock_extract_tickers.return_value = ['AAPL', 'TSLA', 'MSFT', 'META']
        mock_filter_tickers.return_value = ['AAPL', 'TSLA']
        
        # Mock the analyze_ticker_opportunity function to return test data
        mock_analyze_ticker.side_effect = [
            {
                'ticker': 'AAPL',
                'sentiment': 'bullish',
                'signal': 'BUY_CALL',
                'reasoning': 'Strong product line and earnings',
                'confidence': 0.85,
                'price': 150.25,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            {
                'ticker': 'TSLA',
                'sentiment': 'bullish',
                'signal': 'BUY_CALL',
                'reasoning': 'Earnings beat and positive outlook',
                'confidence': 0.75,
                'price': 900.50,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        ]
        
        # Test the identify_opportunities function
        opportunities = identify_opportunities(market_news=self.sample_news, max_opportunities=2)
        
        # Assertions
        self.assertEqual(len(opportunities), 2, "Expected 2 opportunities to be identified")
        self.assertEqual(opportunities[0]['ticker'], 'AAPL', "First opportunity should be AAPL")
        self.assertEqual(opportunities[1]['ticker'], 'TSLA', "Second opportunity should be TSLA")
        
        logger.info(f"Successfully identified opportunities: {json.dumps(opportunities, indent=2)}")
    
    @patch('opportunity_finder.extract_ticker_specific_news')
    @patch('opportunity_finder.get_latest_price_data')
    @patch('opportunity_finder.compute_technicals')
    @patch('opportunity_finder.analyze_with_deepseek_opportunity')
    @patch('opportunity_finder.calculate_confidence')
    def test_analyze_ticker_opportunity(self, mock_calculate_confidence,
                                      mock_analyze_deepseek, mock_compute_technicals, 
                                      mock_get_price_data, mock_extract_news):
        """Test the analyze_ticker_opportunity function"""
        # Set up mocks
        mock_extract_news.return_value = "AAPL announced strong earnings"
        mock_get_price_data.return_value = self.sample_price_data
        mock_compute_technicals.return_value = {
            'rsi': 65,
            'ma20': 110,
            'ma50': 105,
            'trend': 'bullish'
        }
        mock_analyze_deepseek.return_value = ('bullish', 'Strong earnings and outlook', 'BUY_CALL')
        mock_calculate_confidence.return_value = 0.85
        
        # Test the analyze_ticker_opportunity function
        result = analyze_ticker_opportunity('AAPL', self.sample_news)
        
        # Assertions
        self.assertIsNotNone(result, "Expected a result from analyze_ticker_opportunity")
        self.assertEqual(result['ticker'], 'AAPL', "Ticker should be AAPL")
        self.assertEqual(result['sentiment'], 'bullish', "Sentiment should be bullish")
        self.assertEqual(result['signal'], 'BUY_CALL', "Signal should be BUY_CALL")
        self.assertEqual(result['confidence'], 0.85, "Confidence should be 0.85")
        
        logger.info(f"Successfully analyzed ticker opportunity: {json.dumps(result, indent=2)}")

if __name__ == '__main__':
    unittest.main()
