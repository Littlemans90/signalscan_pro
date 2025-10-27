"""
SignalScan PRO - Halt Monitor
Fetches halt data from NASDAQ API every 2.5 minutes
Tracks active halts and historical halts
"""

import requests
import json
from datetime import datetime
import time
from threading import Thread, Event
from core.file_manager import FileManager
from core.logger import Logger


class HaltMonitor:
    def __init__(self, file_manager: FileManager, logger: Logger):
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.thread = None
        
        # Fetch interval: 2.5 minutes
        self.fetch_interval = 150  # seconds
        
    def start(self):
        """Start halt monitoring"""
        self.log.halt("[HALT-MONITOR] Starting halt monitor (every 2.5 minutes)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop halt monitoring"""
        self.log.halt("[HALT-MONITOR] Stopping halt monitor")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            
    def _run_loop(self):
        """Main loop: fetch halts every 2.5 minutes"""
        # Run immediately on start
        self._fetch_halts()
        
        # Then run every 2.5 minutes
        while not self.stop_event.is_set():
            self.stop_event.wait(self.fetch_interval)
            if not self.stop_event.is_set():
                self._fetch_halts()
                
    def _fetch_halts(self):
        """Fetch halt data from NASDAQ API"""
        try:
            self.log.halt("[HALT-MONITOR] Fetching halt data...")
            
            # Fetch from NASDAQ (primary source)
            nasdaq_halts = self._fetch_nasdaq_halts()
            
            if nasdaq_halts:
                self._process_halts(nasdaq_halts)
                self.log.halt(f"[HALT-MONITOR] ✓ Processed {len(nasdaq_halts)} halts")
            else:
                self.log.halt("[HALT-MONITOR] No halts found")
                
        except Exception as e:
            self.log.crash(f"[HALT-MONITOR] Error fetching halts: {e}")
            
    def _fetch_nasdaq_halts(self) -> dict:
        """Fetch halts from NASDAQ API (JSON endpoint)"""
        try:
            # NASDAQ provides a JSON API for halt data
            url = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                self.log.halt(f"[HALT-MONITOR] NASDAQ API returned status {response.status_code}")
                return {}
            
            # Parse RSS/XML response
            from xml.etree import ElementTree as ET
            
            root = ET.fromstring(response.content)
            halts = {}
            
            # Parse RSS items
            for item in root.findall('.//item'):
                try:
                    title = item.find('title').text if item.find('title') is not None else ''
                    description = item.find('description').text if item.find('description') is not None else ''
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
                    
                    # Extract symbol from title (format: "Symbol: XXXX - Halt/Resume")
                    if 'Symbol:' in title:
                        parts = title.split('Symbol:')[1].strip().split('-')
                        symbol = parts[0].strip()
                        status_text = parts[1].strip() if len(parts) > 1 else ''
                        
                        # Determine if halted or resumed
                        is_halted = 'halt' in status_text.lower() and 'resume' not in status_text.lower()
                        
                        halts[symbol] = {
                            'symbol': symbol,
                            'halt_time': pub_date,
                            'resume_time': None if is_halted else pub_date,
                            'reason': description,
                            'status': 'halted' if is_halted else 'resumed',
                            'exchange': 'NASDAQ',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        
                except Exception as e:
                    self.log.crash(f"[HALT-MONITOR] Error parsing halt item: {e}")
                    continue
            
            return halts
            
        except Exception as e:
            self.log.crash(f"[HALT-MONITOR] NASDAQ fetch error: {e}")
            return {}
            
    def _process_halts(self, halts: dict):
        """Process halt data and update files"""
        try:
            # Load existing data
            active_halts = self.fm.load_active_halts()
            historical_halts = self.fm.load_halts()
            
            for symbol, halt_data in halts.items():
                status = halt_data.get('status', 'halted')
                
                if status == 'halted':
                    # Add to active halts
                    active_halts[symbol] = halt_data
                    self.log.halt(f"[HALT-MONITOR] 🔴 HALTED: {symbol} - {halt_data.get('reason', 'Unknown')[:50]}")
                    
                elif status == 'resumed':
                    # Move from active to historical
                    if symbol in active_halts:
                        del active_halts[symbol]
                        
                    # Add to historical with unique key (symbol + timestamp)
                    halt_id = f"{symbol}_{int(time.time())}"
                    historical_halts[halt_id] = halt_data
                    self.log.halt(f"[HALT-MONITOR] 🟢 RESUMED: {symbol}")
                    
            # Save updated data
            self.fm.save_active_halts(active_halts)
            self.fm.save_halts(historical_halts)
            
        except Exception as e:
            self.log.crash(f"[HALT-MONITOR] Error processing halts: {e}")