"""
SignalScan PRO - Tier 2: NASDAQ Halt Scanner
Fetches live trading halts from NASDAQ Trader RSS feed
Updates active_halts.json every 30 seconds
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from threading import Thread, Event
import time
from core.file_manager import FileManager
from core.logger import Logger


class NasdaqHaltScanner:
    def __init__(self, file_manager: FileManager, logger: Logger):
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.thread = None
        
        # NASDAQ halt RSS feed
        self.halt_feed_url = "http://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
        
        # Track active halts
        self.active_halts = {}
        
    def start(self):
        """Start halt scanner"""
        self.log.halt("[TIER2-HALTS] Starting NASDAQ halt scanner")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop halt scanner"""
        self.log.halt("[TIER2-HALTS] Stopping halt scanner")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            
    def _run_loop(self):
        """Main loop: fetch halts every 30 seconds"""
        while not self.stop_event.is_set():
            try:
                self._fetch_halts()
                time.sleep(30)  # Poll every 30 seconds
            except Exception as e:
                self.log.crash(f"[TIER2-HALTS] Error in halt loop: {e}")
                time.sleep(30)
                
    def _fetch_halts(self):
        """Fetch and parse NASDAQ halt RSS feed"""
        try:
            response = requests.get(self.halt_feed_url, timeout=10)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.content)
            
            # Find all halt items
            items = root.findall(".//item")
            
            new_halts = 0
            resumed = 0
            
            for item in items:
                try:
                    # Extract halt data
                    title = item.find("title").text if item.find("title") is not None else ""
                    description = item.find("description").text if item.find("description") is not None else ""
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                    
                    # Parse halt info from description
                    halt_info = self._parse_halt_description(description)
                    
                    if halt_info:
                        symbol = halt_info['symbol']
                        status = halt_info['status']
                        
                        if status == "HALTED":
                            # Add to active halts
                            if symbol not in self.active_halts:
                                self.active_halts[symbol] = {
                                    'symbol': symbol,
                                    'status': status,
                                    'halt_time': halt_info.get('halt_time', pub_date),
                                    'resume_time': None,
                                    'reason': halt_info.get('reason', 'Unknown'),
                                    'price': halt_info.get('price', 0),
                                    'last_update': datetime.utcnow().isoformat()
                                }
                                new_halts += 1
                                self.log.halt(f"[TIER2-HALTS] 🛑 NEW HALT: {symbol} - {halt_info.get('reason', 'Unknown')}")
                        
                        elif status == "RESUMED":
                            # Mark as resumed and remove from active
                            if symbol in self.active_halts:
                                self.active_halts[symbol]['status'] = 'RESUMED'
                                self.active_halts[symbol]['resume_time'] = halt_info.get('resume_time', pub_date)
                                self.active_halts[symbol]['last_update'] = datetime.utcnow().isoformat()
                                
                                # Log and remove from active
                                self.log.halt(f"[TIER2-HALTS] ✅ RESUMED: {symbol}")
                                del self.active_halts[symbol]
                                resumed += 1
                
                except Exception as e:
                    self.log.crash(f"[TIER2-HALTS] Error parsing halt item: {e}")
                    continue
            
            # Save active halts
            self._save_active_halts()
            
            if new_halts > 0 or resumed > 0:
                self.log.halt(f"[TIER2-HALTS] Update: {new_halts} new halts, {resumed} resumed, {len(self.active_halts)} active")
            
        except Exception as e:
            self.log.crash(f"[TIER2-HALTS] Error fetching halts: {e}")
            
    def _parse_halt_description(self, description: str) -> dict:
        """
        Parse NASDAQ halt description
        Example: "Symbol: TSLA; Halt Time: 14:30:00 ET; Reason: LUDP; Price: $285.50"
        """
        try:
            halt_info = {}
            
            # Split by semicolon
            parts = description.split(';')
            
            for part in parts:
                part = part.strip()
                
                if part.startswith("Symbol:"):
                    halt_info['symbol'] = part.split(':')[1].strip()
                
                elif part.startswith("Halt Time:"):
                    halt_info['halt_time'] = part.split(':', 1)[1].strip()
                
                elif part.startswith("Resumption Time:"):
                    halt_info['resume_time'] = part.split(':', 1)[1].strip()
                    halt_info['status'] = 'RESUMED'
                
                elif part.startswith("Reason:"):
                    halt_info['reason'] = part.split(':')[1].strip()
                    if 'resume' not in halt_info:
                        halt_info['status'] = 'HALTED'
                
                elif part.startswith("Price:"):
                    price_str = part.split(':')[1].strip().replace('$', '').replace(',', '')
                    try:
                        halt_info['price'] = float(price_str)
                    except:
                        halt_info['price'] = 0
            
            return halt_info if 'symbol' in halt_info else None
            
        except Exception as e:
            self.log.crash(f"[TIER2-HALTS] Error parsing description: {e}")
            return None
            
    def _save_active_halts(self):
        """Save active halts to active_halts.json"""
        try:
            self.fm.save_active_halts(self.active_halts)
        except Exception as e:
            self.log.crash(f"[TIER2-HALTS] Error saving active halts: {e}")