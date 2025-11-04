"""
SignalScan PRO - Tier 3: Tradier Categorizer
Subscribes to validated symbols via Tradier WebSocket
Categorizes by channel rules, maintains live data for GUI
Subscribes to: alpaca_validated, active_halts, bkgnews
"""

import json
import time
import websocket
from threading import Thread, Event
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from core.file_manager import FileManager
from core.logger import Logger
from config.api_keys import API_KEYS
from .channel_detector import ChannelDetector


class TradierCategorizer(QObject):
    # PyQt5 signals for live GUI updates
    pregap_signal = pyqtSignal(dict)
    hod_signal = pyqtSignal(dict)
    runup_signal = pyqtSignal(dict)
    reversal_signal = pyqtSignal(dict)
    
    def __init__(self, file_manager: FileManager, logger: Logger):
        super().__init__()  # Initialize QObject
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.thread = None
        
        # Tradier credentials
        self.api_key = API_KEYS['TRADIER_API_KEY']
        
        # WebSocket connection
        self.ws = None
        self.session_id = None
        self.subscribed_symbols = set()
        
        # Live data cache (for GUI)
        self.live_data = {}
        
        # Channel detector
        self.detector = ChannelDetector(logger)
        
        # Track previous data for calculations
        self.prev_closes = {}
        self.day_opens = {}
        self.day_highs = {}
        self.price_history = {}
        
        # Categorized stocks by channel
        self.channels = {
            'pregap': [],
            'hod': [],
            'runup': [],
            'rvsl': [],
            'bkgnews': []
        }
        
    def start(self):
        """Start Tradier WebSocket categorizer"""
        self.log.scanner("[TIER3-TRADIER] Starting Tradier categorizer (WebSocket)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop the categorizer"""
        self.log.scanner("[TIER3-TRADIER] Stopping Tradier categorizer")
        self.stop_event.set()
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=5)
            
    def _run_loop(self):
        """Main loop: connect to Tradier WebSocket and maintain subscriptions"""
        # Get session ID
        self._get_session_id()
        
        # Connect to WebSocket
        self._connect_websocket()
        
        while not self.stop_event.is_set():
            try:
                # Load alpaca_validated.json
                validated = self.fm.load_validated()
                
                # Load active_halts.json
                active_halts = self.fm.load_active_halts()
                
                # Load bkgnews.json
                bkgnews = self.fm.load_bkgnews()
                
                # Combine symbols to subscribe
                all_symbols = set()
                all_symbols.update([s['symbol'] for s in validated if 'symbol' in s])
                all_symbols.update(active_halts.keys())
                all_symbols.update(bkgnews.keys())
                
                # Update subscriptions
                self._update_subscriptions(all_symbols)
                
                # Wait 10 seconds
                time.sleep(10)
                
            except Exception as e:
                self.log.crash(f"[TIER3-TRADIER] Error in run loop: {e}")
                time.sleep(10)
                
    def _get_session_id(self):
        """Get Tradier WebSocket session ID"""
        try:
            import requests
            
            url = "https://api.tradier.com/v1/markets/events/session"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }
            
            response = requests.post(url, headers=headers)
            data = response.json()
            
            self.session_id = data['stream']['sessionid']
            self.log.scanner(f"[TIER3-TRADIER] Got session ID: {self.session_id}")
            
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error getting session ID: {e}")
            
    def _connect_websocket(self):
        """Connect to Tradier WebSocket"""
        try:
            import ssl
        
            ws_url = "wss://ws.tradier.com/v1/markets/events"
        
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
        
            # Run WebSocket in background thread with SSL bypass
            ws_thread = Thread(
                target=lambda: self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}),
                daemon=True
            )
            ws_thread.start()
        
            self.log.scanner("[TIER3-TRADIER] WebSocket connected")
        
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error connecting WebSocket: {e}")
            
    def _on_open(self, ws):
        """WebSocket opened"""
        self.log.scanner("[TIER3-TRADIER] WebSocket opened")
        
    def _on_message(self, ws, message):
        self.log.scanner(f"[TIER3-TRADIER] Received message: {message[:200]}")
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle quote/trade data
            if 'type' in data:
                if data['type'] == 'quote':
                    self._handle_quote(data)
                elif data['type'] == 'trade':
                    self._handle_trade(data)
                    
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling message: {e}")
            
    def _on_error(self, ws, error):
        """WebSocket error"""
        self.log.crash(f"[TIER3-TRADIER] WebSocket error: {error}")
        
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket closed"""
        self.log.scanner(f"[TIER3-TRADIER] WebSocket closed: {close_msg}")
    
        # Auto-reconnect after 30 seconds
        if not self.stop_event.is_set():
            self.log.scanner("[TIER3-TRADIER] Reconnecting in 30 seconds...")
            time.sleep(30)
            self._get_session_id()
            self._connect_websocket()
        
    def _update_subscriptions(self, symbols: set):
        """
        Subscribe to new symbols in Tradier WebSocket in safe chunks (max 50 per batch).
        Filters out invalid symbols.
        """
        new_symbols = symbols - self.subscribed_symbols
        if new_symbols and self.ws and self.session_id:
            # Filter out invalid symbols for Tradier
            symbol_list = [
                s for s in new_symbols
                if s and s.isalpha() and 0 < len(s) <= 5
            ]
            max_per_batch = 50  # Tradier's per-request symbol limit

            for i in range(0, len(symbol_list), max_per_batch):
                batch = symbol_list[i:i+max_per_batch]
                self.log.scanner(f"[TIER3-TRADIER] Subscribing to batch: {batch}")
                subscribe_msg = {
                    "symbols": batch,
                    "sessionid": self.session_id,
                    "filter": ["quote", "trade"]
                }
                try:
                    self.ws.send(json.dumps(subscribe_msg))
                except Exception as e:
                    self.log.crash(f"[TIER3-TRADIER] Error subscribing batch: {e}")

            self.subscribed_symbols.update(symbol_list)
            
    def _handle_quote(self, data: dict):
        self.log.scanner(f"[TIER3-TRADIER] Handling QUOTE: {data.get('symbol')}")
        """Handle real-time quote"""
        try:
            symbol = data.get('symbol')
            
            if not symbol:
                return
                
            # Update live data
            if symbol not in self.live_data:
                self.live_data[symbol] = {}
                
            self.live_data[symbol].update({
                'symbol': symbol,
                'bid': data.get('bid'),
                'ask': data.get('ask'),
                'bid_size': data.get('bidsz'),
                'ask_size': data.get('asksz'),
                'last_update': datetime.utcnow().isoformat()
            })
            
            # Detect channel and emit signal
            self._categorize_symbol(symbol)
            
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling quote: {e}")
            
    def _handle_trade(self, data: dict):
        self.log.scanner(f"[TIER3-TRADIER] Handling TRADE: {data.get('symbol')}")
        """Handle real-time trade"""
        try:
            symbol = data.get('symbol')
        
            if not symbol:
                return
            
            if symbol not in self.live_data:
                self.live_data[symbol] = {}
        
            # Convert price to float
            price = data.get('price')
            if price:
                price = float(price)
            
            self.live_data[symbol].update({
                'price': price,
                'volume': data.get('size'),
                'timestamp': datetime.utcnow().isoformat()
            })
        
            # Detect channel and emit signal
            self._categorize_symbol(symbol)
        
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling trade: {e}")

    def _enrich_stock_data(self, symbol: str, live_data: dict) -> dict:
        """Calculate all fields needed for channel detection"""
        try:
            validated = self.fm.load_validated()
            validated_data = next((s for s in validated if s.get('symbol') == symbol), {})
            enriched = {**validated_data, **live_data}
            
            price = live_data.get('price')
            if not price:
                bid = enriched.get('bid', 0)
                ask = enriched.get('ask', 0)
                price = (bid + ask) / 2 if bid and ask else 0
            enriched['price'] = price
            
            prev_close = self.prev_closes.get(symbol, price)
            if prev_close > 0:
                enriched['gap_pct'] = ((price - prev_close) / prev_close) * 100
            else:
                enriched['gap_pct'] = 0
            
            current_high = self.day_highs.get(symbol, price)
            if price > current_high:
                self.day_highs[symbol] = price
                enriched['is_hod'] = True
            else:
                enriched['is_hod'] = False
            enriched['hod_price'] = self.day_highs.get(symbol, price)
            
            current_vol = live_data.get('volume', 0)
            avg_vol = enriched.get('volume_avg', 1000000)
            enriched['rvol'] = current_vol / avg_vol if avg_vol > 0 else 0
            
            now = datetime.utcnow()
            if symbol not in self.price_history:
                self.price_history[symbol] = []
            self.price_history[symbol].append((now, price))
            
            cutoff = now.timestamp() - 900
            self.price_history[symbol] = [(ts, p) for ts, p in self.price_history[symbol] if ts.timestamp() > cutoff]
            
            five_min_ago = now.timestamp() - 300
            old_prices = [p for ts, p in self.price_history[symbol] if ts.timestamp() <= five_min_ago]
            if old_prices:
                old_price = old_prices[-1]
                enriched['move_5min'] = ((price - old_price) / old_price) * 100 if old_price > 0 else 0
            else:
                enriched['move_5min'] = 0
            
            ten_min_ago = now.timestamp() - 600
            old_prices_10 = [p for ts, p in self.price_history[symbol] if ts.timestamp() <= ten_min_ago]
            if old_prices_10:
                old_price = old_prices_10[-1]
                enriched['move_10min'] = ((price - old_price) / old_price) * 100 if old_price > 0 else 0
            else:
                enriched['move_10min'] = 0
            
            enriched['rvol_5min'] = enriched['rvol']
            enriched['float'] = enriched.get('float', 50000000)
            
            bkgnews = self.fm.load_bkgnews()
            enriched['has_breaking_news'] = symbol in bkgnews
            if enriched['has_breaking_news']:
                news_ts = bkgnews[symbol].get('timestamp', '')
                try:
                    news_time = datetime.fromisoformat(news_ts.replace('Z', '+00:00'))
                    age_hours = (datetime.now(news_time.tzinfo) - news_time).total_seconds() / 3600
                    enriched['news_age_hours'] = age_hours
                except:
                    enriched['news_age_hours'] = 999
            else:
                enriched['news_age_hours'] = 999
            
            return enriched
        except Exception as e:
            self.log.crash(f"[TIER3] Error enriching {symbol}: {e}")
            return live_data
   
    def _categorize_symbol(self, symbol: str):
        """Categorize symbol into appropriate channel and emit signal to GUI"""
        try:
            live_data = self.live_data.get(symbol, {})
            
            # Enrich with calculated fields
            stock_data = self._enrich_stock_data(symbol, live_data)
            
            # Detect channel
            channel = self.detector.detect_channel(stock_data)
            
            if channel:
                # Add to channel if not already there
                if symbol not in self.channels[channel]:
                    self.channels[channel].append(symbol)
                    self.log.scanner(f"[TIER3-TRADIER] ✓ {symbol} → {channel.upper()}")
                
                # Emit signal to GUI based on channel
                if channel == 'pregap':
                    self.pregap_signal.emit(stock_data)
                elif channel == 'hod':
                    self.hod_signal.emit(stock_data)
                elif channel == 'runup':
                    self.runup_signal.emit(stock_data)
                elif channel == 'rvsl':
                    self.reversal_signal.emit(stock_data)
                    
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error categorizing {symbol}: {e}")
            
    def get_channel_data(self, channel: str) -> list:
        """Get live data for a specific channel (for GUI)"""
        symbols = self.channels.get(channel, [])
        return [self.live_data.get(s, {}) for s in symbols]
