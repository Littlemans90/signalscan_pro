"""
SignalScan PRO - Main Entry Point with GUI
US Stock Market Momentum & Volatility Scanner
"""

import sys
import os

# Add current directory to Python path so gui module can be found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
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
from gui.main_window import MainWindow


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
        
        # GUI
        self.app = None
        self.main_window = None
        
    def start(self):
        """Start SignalScan PRO with GUI"""
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
        
        # Phase 3: Launch GUI
        print("\n" + "=" * 60)
        print("PHASE 3: Launching GUI")
        print("=" * 60)
        print()
        
        print("[GUI] Starting PyQt5 interface...")
        self._launch_gui()
        
    def _launch_gui(self):
        """Launch the PyQt5 GUI and connect live data feeds"""
        self.app = QApplication(sys.argv)
        self.main_window = MainWindow(self.file_manager, self.logger)
        
        # Connect scanner signals to GUI for live updates
        print("[GUI] Connecting live data feeds...")
        self.main_window.connect_scanner_signals(self.tier3, self.news, self.halts)
        
        self.main_window.show()
        
        print("[GUI] ✓ GUI launched successfully")
        print("[GUI] ✓ Live data feeds connected")
        print("\n" + "=" * 60)
        print("SignalScan PRO is running!")
        print("=" * 60)
        print()
        print("📊 All channels receiving live data")
        print("🚀 PreGap | 📈 HOD | ⚡ RunUP | 🔄 Reversal")
        print("📰 News | 🛑 Halts")
        print()
        print("Press Ctrl+C to stop or use window controls")
        print("=" * 60)
        
        # Run the application event loop
        sys.exit(self.app.exec_())
        
    def stop(self):
        """Stop all scanners"""
        print("\n[SHUTDOWN] Stopping SignalScan PRO...")
        
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
            
        print("[SHUTDOWN] ✓ All systems stopped")


def main():
    """Main entry point"""
    scanner = SignalScanPRO()
    
    try:
        scanner.start()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Received interrupt signal")
        scanner.stop()
    except Exception as e:
        print(f"\n[ERROR] Fatal error: {e}")
        scanner.stop()
        raise


if __name__ == "__main__":
    main()