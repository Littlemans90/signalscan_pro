# core/logger.py

import logging
import os
from datetime import datetime

class Logger:
    """
    Centralized logging system for SignalScan PRO
    Creates separate log files for different components
    """
    
    def __init__(self):
        self.LOGS_DIR = "logs"
        self.loggers = {}
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(self.LOGS_DIR):
            os.makedirs(self.LOGS_DIR)
        
        # Set up default loggers
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Set up loggers for different components"""
        date_str = datetime.now().strftime('%Y%m%d')
        
        # Define log files
        log_files = {
            'scanner': f"scanner_debug_{date_str}.log",
            'news': f"news_debug_{date_str}.log",
            'halt': f"halt_debug_{date_str}.log",
            'crash': f"crash_log_{date_str}.log"
        }
        
        # Create logger for each component
        for name, filename in log_files.items():
            logger = logging.getLogger(name)
            logger.setLevel(logging.DEBUG)
            
            # File handler
            file_path = os.path.join(self.LOGS_DIR, filename)
            file_handler = logging.FileHandler(file_path)
            file_handler.setLevel(logging.DEBUG)
            
            # Format
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # Add handler
            logger.addHandler(file_handler)
            
            self.loggers[name] = logger
            print(f"[LOGGER] Logging {name} to: {file_path}")
    
    def get_logger(self, name: str):
        """Get logger by name"""
        return self.loggers.get(name, self.loggers.get('scanner'))
    
    def log_crash(self, error: Exception, context: str = ""):
        """Log crash to dedicated crash log"""
        crash_logger = self.loggers.get('crash')
        if crash_logger:
            crash_logger.error(f"CRASH - {context}: {str(error)}", exc_info=True)


# Singleton instance
logger_system = Logger()