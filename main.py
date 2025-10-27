"""
SignalScan PRO - Main Entry Point
US Stock Market Momentum & Volatility Scanner
"""

import sys
import signal
import time
from core.file_manager import FileManager
from core.logger import Logger
from config.settings import SETTINGS
from config.api_keys import validate_api_keys
from scanners import (
    Tier1YFinance,
    AlpacaValidator,
    TradierCategorizer,
    NewsAggregator,
    HaltMonitor
)


class SignalScanPRO:
    def __init__(self):
        # Initialize core systems
        self.file_manager = FileManager()
        self.logger = Logger()
        
        # Initialize scanners
        self.tier1 = None
        self.tier2 = None
        self.tier3 = None
        self.news = None
        self.halts = None
        
    def start(self):
        """Start SignalScan PRO"""
        print("=" * 60)
        print("SignalScan PRO - US Stock Market Scanner")
        print("=" * 60)
        print()
        
        # Phase 1: Foundation
        print("[INIT] Starting SignalScan PRO...\n")
        
        print("[FILE-MANAGER] Initializing data directories...")
        self.file_manager.init_directories()
        
        print("\n[LOGGER] Setting up logging system...")
        self.logger.scanner("[INIT] SignalScan PRO starting...")
        
        print("\n[CONFIG] Loading channel rules...")
        for channel in SETTINGS['channels']:
            print(f"  ✓ {channel['name']}")
        
        print("\n[API-KEYS] Checking API credentials...")
        if not validate_api_keys():
            print("[ERROR] Missing required API keys. Check .env file.")
            sys.exit(1)
        print("[API-KEYS] ✓ All required API keys loaded")
        
        print("\n" + "=" * 60)
        print("PHASE 1 STATUS: Foundation Complete ✓")
        print("=" * 60)
        print()
        print("✓ File system initialized")
        print("✓ Configuration loaded")
        print("✓ Logging system active")
        print("✓ API keys verified")
        
        # Phase 2: Data Pipeline
        print("\n" + "=" * 60)
        print("PHASE 2: Starting Data Pipeline")
        print("=" * 60)
        print()
        
        # Start Tier 1: yFinance Prefilter
        print("[TIER1] Starting yFinance prefilter (every 2 hours)...")
        self.tier1 = Tier1YFinance(self.file_manager, self.logger)
        self.tier1.start()
        
        # Start Tier 2: Alpaca Validator
        print("[TIER2] Starting Alpaca validator (WebSocket - always open)...")
        self.tier2 = AlpacaValidator(self.file_manager, self.logger)
        self.tier2.start()
        
        # Start Tier 3: Tradier Categorizer
        print("[TIER3] Starting Tradier categorizer (WebSocket - always open)...")
        self.tier3 = TradierCategorizer(self.file_manager, self.logger)
        self.tier3.start()
        
        # Start News Aggregator
        print("[NEWS] Starting news aggregator (Alpaca WS + rotating secondary)...")
        self.news = NewsAggregator(self.file_manager, self.logger)
        self.news.start()
        
        # Start Halt Monitor
        print("[HALTS] Starting halt monitor (every 2.5 minutes)...")
        self.halts = HaltMonitor(self.file_manager, self.logger)
        self.halts.start()
        
        print("\n" + "=" * 60)
        print("PHASE 2 STATUS: Data Pipeline Active ✓")
        print("=" * 60)
        print()
        print("✓ Tier 1: yFinance prefilter running")
        print("✓ Tier 2: Alpaca validator connected")
        print("✓ Tier 3: Tradier categorizer connected")
        print("✓ News aggregation active")
        print("✓ Halt monitoring active")
        print()
        print("Scanner is now running. Press Ctrl+C to stop.")
        print("=" * 60)
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self):
        """Stop all scanners"""
        print("\n\n[SHUTDOWN] Stopping SignalScan PRO...")
        
        if self.tier1:
            self.tier1.stop()
            
        if self.tier2:
            self.tier2.stop()
            
        if self.tier3:
            self.tier3.stop()
            
        if self.news:
            self.news.stop()
            
        if self.halts:
            self.halts.stop()
            
        print("[SHUTDOWN] ✓ All scanners stopped")
        print("=" * 60)


if __name__ == '__main__':
    scanner = SignalScanPRO()
    scanner.start()
