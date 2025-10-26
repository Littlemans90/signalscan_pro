# main.py

"""
SignalScan PRO - Main Entry Point
US Stock Market Momentum & Volatility Scanner
"""

import sys
from core.file_manager import file_manager
from core.logger import logger_system
from config.settings import settings
from config.api_keys import api_keys

def print_banner():
    """Print startup banner"""
    print("=" * 60)
    print("SignalScan PRO - US Stock Market Scanner")
    print("=" * 60)
    print()

def initialize_system():
    """Initialize all core systems"""
    print("[INIT] Starting SignalScan PRO...")
    print()
    
    # Initialize file system
    print("[FILE-MANAGER] Initializing data directories...")
    # file_manager is already initialized on import
    print()
    
    # Initialize logging
    print("[LOGGER] Setting up logging system...")
    # logger_system is already initialized on import
    print()
    
    # Load configuration
    print("[CONFIG] Loading channel rules...")
    channels = [
        settings.PREGAP,
        settings.HOD,
        settings.BREAKING_NEWS,
        settings.HALT,
        settings.NEWS_FILTER
    ]
    for channel in channels:
        status = "✓" if channel['enabled'] else "✗"
        print(f"  {status} {channel['display_name']}")
    print()
    
    # Validate API keys
    print("[API-KEYS] Checking API credentials...")
    if not api_keys.validate():
        print()
        print("=" * 60)
        print("SETUP REQUIRED")
        print("=" * 60)
        print()
        print("Please add your API keys to the .env file:")
        print("1. Copy .env.example to .env")
        print("2. Add your Alpaca and Tradier credentials")
        print("3. Run this script again")
        print()
        return False
    print()
    
    return True

def run_phase_1_test():
    """Phase 1: Verify foundation is working"""
    print("=" * 60)
    print("PHASE 1 STATUS: Foundation Complete ✓")
    print("=" * 60)
    print()
    print("✓ File system initialized")
    print("✓ Configuration loaded")
    print("✓ Logging system active")
    print("✓ API keys verified")
    print()
    print("NEXT PHASE: Data Pipeline (Tier 1-3)")
    print("  → Tier 1: yFinance prefilter")
    print("  → Tier 2: Alpaca WebSocket validation")
    print("  → Tier 3: Tradier WebSocket categorization")
    print()
    print("=" * 60)

def main():
    """Main entry point"""
    try:
        print_banner()
        
        if not initialize_system():
            sys.exit(1)
        
        # Phase 1: Just test initialization
        run_phase_1_test()
        
        # Phase 2+ will be added later:
        # - Data pipeline
        # - Channel detection
        # - UI rendering
        # - Alert system
        
    except KeyboardInterrupt:
        print()
        print("[SHUTDOWN] User interrupted - shutting down gracefully...")
        sys.exit(0)
    
    except Exception as e:
        print()
        print("[ERROR] Fatal error occurred:")
        print(f"  {str(e)}")
        logger_system.log_crash(e, "main")
        sys.exit(1)


if __name__ == "__main__":
    main()