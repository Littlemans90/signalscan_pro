"""
SignalScan PRO - News Aggregator
Multi-provider news system with rotation
Primary: Alpaca News WebSocket (always open)
Secondary: Polygon → Marketaux → FMP → NewsAPI → AlphaVantage → Finnhub (rotates every 3 min)
Special: GDELT (4 AM daily), Perplexity (deep scan button)
"""

import json
import time
import requests
from datetime import datetime, timedelta
from threading import Thread, Event
from alpaca.data.live import NewsDataStream
from core.file_manager import FileManager
from core.logger import Logger
from config.api_keys import API_KEYS
from config.keywords import categorize_news_by_age, should_exclude


class NewsAggregator:
    def __init__(self, file_manager: FileManager, logger: Logger):
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.primary_thread = None
        self.secondary_thread = None
        
        # API Keys
        self.alpaca_key = API_KEYS['ALPACA_API_KEY']
        self.alpaca_secret = API_KEYS['ALPACA_SECRET_KEY']
        
        # Secondary providers (in priority order)
        self.secondary_providers = [
            'polygon',
            'marketaux', 
            'fmp',
            'newsapi',
            'alphavantage',
            'finnhub'
        ]
        self.current_provider_index = 0
        
        # Alpaca News WebSocket
        self.news_stream = None
        
        # News cache (de-duplication)
        self.seen_news_ids = set()
        
    def start(self):
        """Start news aggregation"""
        self.log.news("[NEWS-AGGREGATOR] Starting news aggregation")
        self.stop_event.clear()
        
        # Start primary (Alpaca WebSocket)
        self.primary_thread = Thread(target=self._run_primary, daemon=True)
        self.primary_thread.start()
        
        # Start secondary (rotating providers)
        self.secondary_thread = Thread(target=self._run_secondary, daemon=True)
        self.secondary_thread.start()
        
    def stop(self):
        """Stop news aggregation"""
        self.log.news("[NEWS-AGGREGATOR] Stopping news aggregation")
        self.stop_event.set()
        
        if self.news_stream:
            self.news_stream.close()
            
        if self.primary_thread:
            self.primary_thread.join(timeout=5)
            
        if self.secondary_thread:
            self.secondary_thread.join(timeout=5)
            
    def _run_primary(self):
        """Primary: Alpaca News WebSocket (always open)"""
        try:
            self.log.news("[NEWS-AGGREGATOR] Starting Alpaca News WebSocket")
        
            # Initialize Alpaca News stream
            self.news_stream = NewsDataStream(self.alpaca_key, self.alpaca_secret)
        
            # Subscribe to all news with SYNCHRONOUS handler
            def news_handler(news):
                self._handle_alpaca_news(news)
        
            self.news_stream.subscribe_news(news_handler, '*')
        
            self.log.news("[NEWS-AGGREGATOR] ✓ Alpaca News WebSocket subscribed")
        
            # Run stream (blocking)
            self.news_stream.run()
        
        except Exception as e:
            self.log.crash(f"[NEWS-AGGREGATOR] Alpaca WebSocket error: {e}")
            
    def _run_secondary(self):
        """Secondary: Rotating providers (every 3 minutes)"""
        while not self.stop_event.is_set():
            try:
                provider = self.secondary_providers[self.current_provider_index]
                
                self.log.news(f"[NEWS-AGGREGATOR] Fetching from secondary: {provider.upper()}")
                
                # Fetch news from current provider
                news_items = self._fetch_from_provider(provider)
                
                if news_items:
                    # Process news items
                    for item in news_items:
                        self._process_news_item(item, provider)
                else:
                    # Provider failed, rotate to next
                    self.log.news(f"[NEWS-AGGREGATOR] {provider.upper()} failed, rotating to next provider")
                    self._rotate_provider()
                
                # Wait 3 minutes
                self.stop_event.wait(180)
                
            except Exception as e:
                self.log.crash(f"[NEWS-AGGREGATOR] Secondary error: {e}")
                self.stop_event.wait(180)
                
    def _handle_alpaca_news(self, news):
        """Handle news from Alpaca WebSocket"""
        try:
            news_item = {
                'news_id': str(news.id),
                'symbol': news.symbols[0] if news.symbols else 'UNKNOWN',
                'headline': news.headline,
                'summary': news.summary,
                'source': news.author,
                'url': news.url,
                'timestamp': news.created_at.isoformat(),
                'provider': 'alpaca'
            }
        
            self._process_news_item(news_item, 'alpaca')
            self.log.news(f"[NEWS-AGGREGATOR] ✓ Processed Alpaca news: {news_item['symbol']}")
        
        except Exception as e:
            self.log.crash(f"[NEWS-AGGREGATOR] Error handling Alpaca news: {e}")
            
    def _fetch_from_provider(self, provider: str) -> list:
        """Fetch news from specific provider"""
        try:
            if provider == 'polygon':
                return self._fetch_polygon()
            elif provider == 'marketaux':
                return self._fetch_marketaux()
            elif provider == 'fmp':
                return self._fetch_fmp()
            elif provider == 'newsapi':
                return self._fetch_newsapi()
            elif provider == 'alphavantage':
                return self._fetch_alphavantage()
            elif provider == 'finnhub':
                return self._fetch_finnhub()
            else:
                return []
                
        except Exception as e:
            self.log.crash(f"[NEWS-AGGREGATOR] Error fetching from {provider}: {e}")
            return []
            
    def _fetch_polygon(self) -> list:
        """Fetch from Polygon.io"""
        try:
            api_key = API_KEYS.get('POLYGON_API_KEY')
            if not api_key:
                return []
                
            url = f"https://api.polygon.io/v2/reference/news?apiKey={api_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                news_items = []
                
                for item in data.get('results', []):
                    news_items.append({
                        'news_id': item['id'],
                        'symbol': item['tickers'][0] if item.get('tickers') else 'UNKNOWN',
                        'headline': item['title'],
                        'summary': item.get('description', ''),
                        'source': item.get('publisher', {}).get('name', 'Polygon'),
                        'url': item['article_url'],
                        'timestamp': item['published_utc'],
                        'provider': 'polygon'
                    })
                    
                return news_items
            else:
                return []
                
        except Exception as e:
            self.log.crash(f"[NEWS-AGGREGATOR] Polygon error: {e}")
            return []
            
    def _fetch_finnhub(self) -> list:
        """Fetch from Finnhub"""
        try:
            api_key = API_KEYS.get('FINNHUB_API_KEY')
            if not api_key:
                return []
                
            url = f"https://finnhub.io/api/v1/news?category=general&token={api_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                news_items = []
                
                for item in data:
                    news_items.append({
                        'news_id': str(item['id']),
                        'symbol': item.get('related', 'UNKNOWN'),
                        'headline': item['headline'],
                        'summary': item['summary'],
                        'source': item['source'],
                        'url': item['url'],
                        'timestamp': datetime.fromtimestamp(item['datetime']).isoformat(),
                        'provider': 'finnhub'
                    })
                    
                return news_items
            else:
                return []
                
        except Exception as e:
            self.log.crash(f"[NEWS-AGGREGATOR] Finnhub error: {e}")
            return []
            
    def _fetch_marketaux(self) -> list:
        """Placeholder for Marketaux"""
        return []
        
    def _fetch_fmp(self) -> list:
        """Placeholder for FMP"""
        return []
        
    def _fetch_newsapi(self) -> list:
        """Placeholder for NewsAPI"""
        return []
        
    def _fetch_alphavantage(self) -> list:
        """Placeholder for Alpha Vantage"""
        return []
            
    def _process_news_item(self, item: dict, provider: str):
        """Process a single news item (de-duplicate and categorize)"""
        try:
            news_id = item['news_id']
            
            # De-duplicate
            if news_id in self.seen_news_ids:
                return
                
            self.seen_news_ids.add(news_id)
            
            headline = item['headline']
            
            # Check if should exclude
            if should_exclude(headline):
                return
            
            # Calculate news age
            timestamp = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
            age_hours = (datetime.now(timestamp.tzinfo) - timestamp).total_seconds() / 3600
            
            # Categorize by age and keywords
            category = categorize_news_by_age(headline, age_hours)
            
            if category == 'breaking':
                # Save to bkgnews.json
                bkgnews = self.fm.load_bkgnews()
                bkgnews[news_id] = {
                    **item,
                    'age_hours': age_hours,
                    'category': 'breaking'
                }
                self.fm.save_bkgnews(bkgnews)
                self.log.news(f"[NEWS-AGGREGATOR] 🔵 BREAKING: {item['symbol']} - {headline[:50]}...")
                
            elif category == 'general':
                # Save to news.json
                news = self.fm.load_news()
                news[news_id] = {
                    **item,
                    'age_hours': age_hours,
                    'category': 'general'
                }
                self.fm.save_news(news)
                self.log.news(f"[NEWS-AGGREGATOR] 🟡 NEWS: {item['symbol']} - {headline[:50]}...")
                
        except Exception as e:
            self.log.crash(f"[NEWS-AGGREGATOR] Error processing news item: {e}")
            
    def _rotate_provider(self):
        """Rotate to next secondary provider"""
        self.current_provider_index = (self.current_provider_index + 1) % len(self.secondary_providers)
        next_provider = self.secondary_providers[self.current_provider_index]
        self.log.news(f"[NEWS-AGGREGATOR] Rotated to: {next_provider.upper()}")
        
    def force_refresh(self):
        """Force news refresh (triggered by News Refresh button)"""
        self.log.news("[NEWS-AGGREGATOR] Force refresh triggered")
        
        # Fetch from GDELT
        self._fetch_gdelt()
        
        # Fetch from Alpaca REST API
        self._fetch_alpaca_rest()
        
        # Fetch from Finnhub
        finnhub_news = self._fetch_finnhub()
        for item in finnhub_news:
            self._process_news_item(item, 'finnhub')
            
    def _fetch_gdelt(self):
        """Special: GDELT bulk scan"""
        self.log.news("[NEWS-AGGREGATOR] Fetching from GDELT...")
        # TODO: Implement GDELT API
        
    def _fetch_alpaca_rest(self):
        """Fetch from Alpaca REST API"""
        self.log.news("[NEWS-AGGREGATOR] Fetching from Alpaca REST API...")
        # TODO: Implement Alpaca REST news fetch
