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
from core.file_manager import FileManager
from core.logger import Logger
from config.api_keys import API_KEYS
from .channel_detector import ChannelDetector


class TradierCategorizer:
    def __init__(self, file_manager: FileManager, logger: Logger):
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
            self.log.scanner(f"[TIER3-TRADIER] ✓ Got session ID: {self.session_id}")
            
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
        
            self.log.scanner("[TIER3-TRADIER] ✓ WebSocket connected")
        
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error connecting WebSocket: {e}")
            
    def _on_open(self, ws):
        """WebSocket opened"""
        self.log.scanner("[TIER3-TRADIER] WebSocket opened")
        
    def _on_message(self, ws, message):
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
        """Subscribe to new symbols"""
        new_symbols = symbols - self.subscribed_symbols
        
        if new_symbols and self.ws and self.session_id:
            self.log.scanner(f"[TIER3-TRADIER] Subscribing to {len(new_symbols)} new symbols")
            
            # Subscribe via WebSocket
            subscribe_msg = {
                "symbols": list(new_symbols),
                "sessionid": self.session_id,
                "filter": ["quote", "trade"]
            }
            
            self.ws.send(json.dumps(subscribe_msg))
            
            self.subscribed_symbols.update(new_symbols)
            
    def _handle_quote(self, data: dict):
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
            
            # Detect channel
            self._categorize_symbol(symbol)
            
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling quote: {e}")
            
    def _handle_trade(self, data: dict):
        """Handle real-time trade"""
        try:
            symbol = data.get('symbol')
            
            if not symbol:
                return
                
            if symbol not in self.live_data:
                self.live_data[symbol] = {}
                
            self.live_data[symbol].update({
                'price': data.get('price'),
                'volume': data.get('size'),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Detect channel
            self._categorize_symbol(symbol)
            
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling trade: {e}")
            
    def _categorize_symbol(self, symbol: str):
        """Categorize symbol into appropriate channel"""
        try:
            stock_data = self.live_data.get(symbol, {})
            
            # Detect channel
            channel = self.detector.detect_channel(stock_data)
            
            if channel:
                # Add to channel if not already there
                if symbol not in self.channels[channel]:
                    self.channels[channel].append(symbol)
                    self.log.scanner(f"[TIER3-TRADIER] ✓ {symbol} → {channel.upper()}")
                    
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error categorizing {symbol}: {e}")
            
    def get_channel_data(self, channel: str) -> list:
        """Get live data for a specific channel (for GUI)"""
        symbols = self.channels.get(channel, [])
        return [self.live_data.get(s, {}) for s in symbols]
