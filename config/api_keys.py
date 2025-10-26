# config/api_keys.py

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class APIKeys:
    """
    Secure API key management
    Loads keys from .env file
    """
    
    def __init__(self):
        # Required APIs
        self.ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
        self.ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '')
        self.TRADIER_ACCESS_TOKEN = os.getenv('TRADIER_ACCESS_TOKEN', '')
        
        # Optional backup news providers
        self.POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
        self.MARKETAUX_API_KEY = os.getenv('MARKETAUX_API_KEY', '')
        self.FMP_API_KEY = os.getenv('FMP_API_KEY', '')
        self.NEWSAPI_API_KEY = os.getenv('NEWSAPI_API_KEY', '')
        self.ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY', '')
        self.FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '')
        
        # AI provider (optional)
        self.PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', '')
    
    def validate(self):
        """Check if required API keys are present"""
        missing = []
        
        if not self.ALPACA_API_KEY:
            missing.append('ALPACA_API_KEY')
        if not self.ALPACA_SECRET_KEY:
            missing.append('ALPACA_SECRET_KEY')
        if not self.TRADIER_ACCESS_TOKEN:
            missing.append('TRADIER_ACCESS_TOKEN')
        
        if missing:
            print(f"[API-KEYS] ⚠️ Missing required keys: {', '.join(missing)}")
            print("[API-KEYS] Add them to your .env file")
            return False
        
        print("[API-KEYS] ✓ All required API keys loaded")
        return True
    
    def get_alpaca_credentials(self):
        """Get Alpaca API credentials"""
        return {
            'api_key': self.ALPACA_API_KEY,
            'secret_key': self.ALPACA_SECRET_KEY
        }
    
    def get_tradier_token(self):
        """Get Tradier access token"""
        return self.TRADIER_ACCESS_TOKEN


# Singleton instance
api_keys = APIKeys()