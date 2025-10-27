"""
SignalScan PRO - Tier 1: yFinance Prefilter
Loads master_registry.json, filters US stocks by volume/price
Saves to data/prefilter.json
Runs every 2 hours
"""

import json
import yfinance as yf
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Event  # ← ADDED


class Tier1YFinance:
    def __init__(self, file_manager, logger):
        self.file_manager = file_manager
        self.log = logger
        self.master_registry_path = Path('master_registry.json')
        self.scan_interval = 7200  # 2 hours in seconds
        
        # Threading support
        self.stop_event = Event()  # ← ADDED
        self.thread = None  # ← ADDED
        
    def load_master_tickers(self):
        """Load all tickers from master_registry.json"""
        try:
            if not self.master_registry_path.exists():
                self.log.crash(f"[TIER1-YFINANCE] master_registry.json not found")
                return []
            
            with open(self.master_registry_path, 'r') as f:
                data = json.load(f)
            
            # Extract ticker symbols from the "tickers" object
            tickers = list(data.get('tickers', {}).keys())
            self.log.scanner(f"[TIER1-YFINANCE] Loaded {len(tickers)} tickers from master_registry.json")
            return tickers
            
        except Exception as e:
            self.log.crash(f"[TIER1-YFINANCE] Error loading master_registry.json: {e}")
            return []
    
    def filter_tickers(self, tickers):
        """
        Filter tickers by:
        - Volume > 5M (average daily volume)
        - Price > $.75
        - Price < $17.00
        """
        filtered = []
        total = len(tickers)
        
        self.log.scanner(f"[TIER1-YFINANCE] Starting filter on {total} tickers...")
        
        # Process in batches to avoid rate limits
        batch_size = 100
        for i in range(0, total, batch_size):
            batch = tickers[i:i+batch_size]
            
            for symbol in batch:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    # Get current price
                    price = info.get('currentPrice') or info.get('regularMarketPrice')
                    if not price:
                        continue
                    
                    # Get average volume
                    volume = info.get('averageVolume') or info.get('averageVolume10days')
                    if not volume:
                        continue
                    
                    # Apply filters
                    if volume > 5_000_000 and .75 < price < 17.00:
                        filtered.append(symbol)
                        self.log.scanner(f"[TIER1-YFINANCE] ✓ {symbol}: ${price:.2f}, Vol: {volume:,}")
                
                except Exception as e:
                    # Skip problematic tickers silently
                    continue
            
            # Progress update
            processed = min(i + batch_size, total)
            self.log.scanner(f"[TIER1-YFINANCE] Progress: {processed}/{total} ({len(filtered)} passed)")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
        
        self.log.scanner(f"[TIER1-YFINANCE] ✓ Filtered: {len(filtered)}/{total} tickers passed")
        return filtered
    
    def run_scan(self):
        """Run single scan cycle"""
        self.log.scanner("[TIER1-YFINANCE] Starting prefilter scan...")
        
        # Load tickers
        tickers = self.load_master_tickers()
        if not tickers:
            self.log.crash("[TIER1-YFINANCE] No tickers to scan")
            return
        
        # Filter tickers
        filtered = self.filter_tickers(tickers)
        
        # Save to prefilter.json
        self.file_manager.save_prefilter(filtered)
        self.log.scanner(f"[TIER1-YFINANCE] ✓ Saved {len(filtered)} symbols to prefilter.json")
    
    def start(self):
        """Start prefilter scanner (runs every 2 hours)"""
        self.log.scanner("[TIER1-YFINANCE] Starting prefilter scanner (every 2 hours)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        """Background thread loop"""
        while not self.stop_event.is_set():
            try:
                self.run_scan()
            
                # Wait 2 hours
                self.log.scanner(f"[TIER1-YFINANCE] Next scan in 2 hours...")
                time.sleep(self.scan_interval)
            
            except Exception as e:
                self.log.crash(f"[TIER1-YFINANCE] Error in scan loop: {e}")
                time.sleep(60)  # Wait 1 minute on error

    def stop(self):
        """Stop the scanner"""
        self.log.scanner("[TIER1-YFINANCE] Stopping prefilter scanner")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)