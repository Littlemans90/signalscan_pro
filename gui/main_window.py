"""
SignalScan PRO - Main GUI Window (PyQt5)
Professional stock scanner interface with real-time data updates
Trading Channels: Live-only from Tier3 signals
News & Halts: Vault system (persistent storage + live updates)
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QStatusBar, QHeaderView, QFrame
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QPixmap
from datetime import datetime
import pytz
import json
import os


class MainWindow(QMainWindow):
    """Main application window for SignalScan PRO"""
    
    def __init__(self, file_manager, logger, tier1=None):
        super().__init__()
        self.fm = file_manager
        self.tier1 = tier1
        self.log = logger
        self.log.scanner("[GUI-DEBUG] MainWindow.__init__ started")
        
        # Window setup - Made wider to fit all tabs
        self.setWindowTitle("SignalScan PRO - US Stock Market Scanner")
        self.setGeometry(50, 50, 2000, 950)
        
        # Initialize UI
        self._init_ui()
        
        # Set up vault refresh timer (update every 5 seconds for news/halts)
        self.vault_refresh_timer = QTimer()
        self.vault_refresh_timer.timeout.connect(self._refresh_vaults)
        self.vault_refresh_timer.start(5000)  # 5000ms = 5 seconds
        
    def _init_ui(self):
        """Initialize the user interface"""
        self.log.scanner("[GUI-DEBUG] _init_ui started")
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Top status bar
        self.status_panel = self._create_status_panel()
        main_layout.addWidget(self.status_panel)
        
        # Tab widget for channels
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setUsesScrollButtons(False)  # Disable scroll buttons to show all tabs
        self.tabs.setElideMode(Qt.ElideNone)   # Don't truncate tab text
        self.tabs.tabBar().setExpanding(True)  # Make tabs expand to fill width
        self.tabs.tabBar().setDrawBase(False)  # Remove base line for cleaner look
        main_layout.addWidget(self.tabs)
        
        # Create channel tabs
        self.pregap_table = self._create_channel_tab("PreGap", [
            "Symbol", "Price", "% Change", "Gap %", "Volume", "RVOL", "Float", "Time"
        ])
        self.tabs.addTab(self.pregap_table, "🚀 PreGap")
        
        self.hod_table = self._create_channel_tab("HOD", [
            "Symbol", "Price", "% Change", "HOD", "Volume", "RVOL", "Float", "Time"
        ])
        self.tabs.addTab(self.hod_table, "📈 HOD")
        
        self.runup_table = self._create_channel_tab("RunUP", [
            "Symbol", "Price", "% Change", "5min %", "Volume", "RVOL", "Float", "Time"
        ])
        self.tabs.addTab(self.runup_table, "⚡ RunUP")
        
        self.rvsl_table = self._create_channel_tab("Reversal", [
            "Symbol", "Price", "% Change", "Gap %", "Volume", "RVOL", "Time"
        ])
        self.tabs.addTab(self.rvsl_table, "🔄 Reversal")
        
        self.news_table = self._create_channel_tab("Breaking News", [
            "Symbol", "Price", "% Change", "Headline", "Age", "Time"
        ])
        self.tabs.addTab(self.news_table, "📰 News")
        
        self.halt_table = self._create_channel_tab("Halts", [
            "Symbol", "Status", "Halt Time", "Resume Time", "Reason", "Price"
        ])
        self.tabs.addTab(self.halt_table, "🛑 Halts")
        
        # Bottom status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("SignalScan PRO initialized - waiting for data...")
        
        # Apply dark theme styling
        self._apply_stylesheet()
        
    def _create_status_panel(self):
        """Create top status panel"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        panel.setLayout(layout)
        
        # Top row: Title (left), Market Status (center), Buttons (far right)
        top_row = QHBoxLayout()
        
        # Left section: Logo + Title + Times
        left_section = QHBoxLayout()
        
        # Logo
        logo_label = QLabel()
        logo_paths = [
            "logo.jpeg",
            "logo.jpg",
            "logo.png",
            "assets/logo.jpeg",
            "assets/logo.png"
        ]
        
        logo_loaded = False
        for logo_path in logo_paths:
            if os.path.exists(logo_path):
                try:
                    logo_pixmap = QPixmap(logo_path)
                    if not logo_pixmap.isNull():
                        logo_pixmap = logo_pixmap.scaled(45, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        logo_label.setPixmap(logo_pixmap)
                        logo_label.setStyleSheet("margin-right: 12px;")
                        left_section.addWidget(logo_label)
                        logo_loaded = True
                        self.log.scanner(f"[GUI] Logo loaded from: {logo_path}")
                        break
                except Exception as e:
                    self.log.crash(f"[GUI] Error loading logo from {logo_path}: {e}")
        
        if not logo_loaded:
            self.log.scanner("[GUI] No logo found - continuing without logo")
        
        title = QLabel("SignalScan PRO")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00ff00; margin-right: 20px;")
        left_section.addWidget(title)
        
        # Times container (next to title)
        times_container = QVBoxLayout()
        times_container.setSpacing(2)
        
        self.local_time_label = QLabel()
        self.local_time_label.setStyleSheet("font-size: 12px; padding: 2px;")
        times_container.addWidget(self.local_time_label)
        
        self.nyc_time_label = QLabel()
        self.nyc_time_label.setStyleSheet("font-size: 12px; padding: 2px;")
        times_container.addWidget(self.nyc_time_label)
        
        left_section.addLayout(times_container)
        
        top_row.addLayout(left_section)
        
        top_row.addStretch()
        
        # Center: Market Session
        self.market_session = QLabel("Market: CLOSED")
        self.market_session.setStyleSheet("font-weight: bold; padding: 5px; font-size: 16px;")
        top_row.addWidget(self.market_session)
        
        top_row.addStretch()
        
        # Right section: Control buttons
        buttons_container = QHBoxLayout()
        buttons_container.setSpacing(10)
        
        # NEWS button
        news_btn = QPushButton("📰 NEWS")
        news_btn.setMinimumHeight(35)
        news_btn.setStyleSheet("""
            QPushButton {
                background-color: #0969da;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1158c7;
            }
            QPushButton:pressed {
                background-color: #0550ae;
            }
        """)
        news_btn.clicked.connect(self._on_news_clicked)
        buttons_container.addWidget(news_btn)
        
        # UPDATE button
        update_btn = QPushButton("🔄 UPDATE")
        update_btn.setMinimumHeight(35)
        update_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:pressed {
                background-color: #1a7f37;
            }
        """)
        update_btn.clicked.connect(self._on_update_clicked)
        buttons_container.addWidget(update_btn)
        
        # KIOSK button
        kiosk_btn = QPushButton("🖥️ KIOSK")
        kiosk_btn.setMinimumHeight(35)
        kiosk_btn.setStyleSheet("""
            QPushButton {
                background-color: #6e7681;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #8b949e;
            }
            QPushButton:pressed {
                background-color: #6e7681;
            }
        """)
        kiosk_btn.clicked.connect(self._on_kiosk_clicked)
        buttons_container.addWidget(kiosk_btn)
        
        top_row.addLayout(buttons_container)
        
        layout.addLayout(top_row)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #30363d;")
        layout.addWidget(separator)
        
        # Bottom row: Market Indices (horizontal layout)
        indices_row = QHBoxLayout()
        
        self.sp500_label = QLabel("S&P 500: --")
        self.sp500_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px; margin-right: 20px;")
        indices_row.addWidget(self.sp500_label)
        
        self.nasdaq_label = QLabel("NASDAQ: --")
        self.nasdaq_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px; margin-right: 20px;")
        indices_row.addWidget(self.nasdaq_label)
        
        self.dow_label = QLabel("DOW: --")
        self.dow_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px;")
        indices_row.addWidget(self.dow_label)
        
        indices_row.addStretch()
        
        layout.addLayout(indices_row)
        
        # Update time immediately
        self._update_time()
        
        # Time update timer
        time_timer = QTimer(self)
        time_timer.timeout.connect(self._update_time)
        time_timer.start(1000)
        
        # Indices update timer (every 5 seconds)
        indices_timer = QTimer(self)
        indices_timer.timeout.connect(self._update_indices)
        indices_timer.start(30000)
        
        panel.setStyleSheet("background-color: #1e1e1e; padding: 10px;")
        return panel
    
    # =========================================================================
    # LIVE DATA FEED SLOTS - Receive real-time updates from scanners
    # =========================================================================
    
    @pyqtSlot(dict)
    def on_pregap_update(self, stock_data):
        """Receive PreGap channel update (LIVE ONLY)"""
        self._add_or_update_stock(self.pregap_table, stock_data, [
            'symbol', 'price', 'change_pct', 'gap_pct', 'volume', 'rvol', 'float', 'timestamp'
        ])
    
    @pyqtSlot(dict)
    def on_hod_update(self, stock_data):
        """Receive HOD channel update (LIVE ONLY)"""
        self._add_or_update_stock(self.hod_table, stock_data, [
            'symbol', 'price', 'change_pct', 'hod_price', 'volume', 'rvol', 'float', 'timestamp'
        ])
    
    @pyqtSlot(dict)
    def on_runup_update(self, stock_data):
        """Receive RunUP channel update (LIVE ONLY)"""
        self._add_or_update_stock(self.runup_table, stock_data, [
            'symbol', 'price', 'change_pct', 'change_5min', 'volume', 'rvol', 'float', 'timestamp'
        ])
    
    @pyqtSlot(dict)
    def on_reversal_update(self, stock_data):
        """Receive Reversal channel update (LIVE ONLY)"""
        self._add_or_update_stock(self.rvsl_table, stock_data, [
            'symbol', 'price', 'change_pct', 'gap_pct', 'volume', 'rvol', 'timestamp'
        ])
    
    @pyqtSlot(dict)
    def on_news_update(self, news_data):
        """Receive News update (VAULT + LIVE)"""
        symbol = news_data.get('symbol', 'N/A')
        headline = news_data.get('headline', 'No headline')
        
        # Check if this exact headline already exists to avoid duplicates
        for i in range(self.news_table.rowCount()):
            if (self.news_table.item(i, 0) and 
                self.news_table.item(i, 3) and
                self.news_table.item(i, 0).text() == symbol and
                self.news_table.item(i, 3).text() == headline):
                return  # Already exists, skip
        
        # Add new row at the top
        row = 0
        self.news_table.insertRow(row)
        
        # Symbol
        symbol_item = QTableWidgetItem(symbol)
        symbol_item.setFont(QFont("Arial", 10, QFont.Bold))
        self.news_table.setItem(row, 0, symbol_item)
        
        # Price
        price = news_data.get('price', 0.0)
        self.news_table.setItem(row, 1, QTableWidgetItem(f"${price:.2f}" if isinstance(price, (int, float)) and price > 0 else "--"))
        
        # % Change
        change = news_data.get('change_pct', 0.0)
        change_item = QTableWidgetItem(f"{change:+.2f}%" if isinstance(change, (int, float)) and change != 0 else "--")
        if isinstance(change, (int, float)):
            if change > 0:
                change_item.setForeground(QColor(0, 255, 0))
            elif change < 0:
                change_item.setForeground(QColor(255, 0, 0))
        self.news_table.setItem(row, 2, change_item)
        
        # Headline
        self.news_table.setItem(row, 3, QTableWidgetItem(headline))
        
        # Age
        age = news_data.get('age', 'N/A')
        self.news_table.setItem(row, 4, QTableWidgetItem(str(age)))
        
        # Timestamp
        timestamp = news_data.get('timestamp', 'N/A')
        self.news_table.setItem(row, 5, QTableWidgetItem(str(timestamp)))
    
    @pyqtSlot(dict)
    def on_halt_update(self, halt_data):
        """Receive Halt update (VAULT + LIVE)"""
        symbol = halt_data.get('symbol', 'N/A')
        
        # Find if symbol already exists
        row = -1
        for i in range(self.halt_table.rowCount()):
            if self.halt_table.item(i, 0) and self.halt_table.item(i, 0).text() == symbol:
                row = i
                break
        
        # Add new row if not found
        if row == -1:
            row = self.halt_table.rowCount()
            self.halt_table.insertRow(row)
        
        # Symbol
        symbol_item = QTableWidgetItem(symbol)
        symbol_item.setFont(QFont("Arial", 11, QFont.Bold))
        self.halt_table.setItem(row, 0, symbol_item)
        
        # Status
        status = halt_data.get('status', 'Unknown')
        status_item = QTableWidgetItem(status)
        if status == "HALTED":
            status_item.setForeground(QColor(255, 0, 0))
            status_item.setFont(QFont("Arial", 10, QFont.Bold))
        elif status == "RESUMED":
            status_item.setForeground(QColor(0, 255, 0))
            status_item.setFont(QFont("Arial", 10, QFont.Bold))
        self.halt_table.setItem(row, 1, status_item)
        
        # Halt time, Resume time, Reason, Price
        self.halt_table.setItem(row, 2, QTableWidgetItem(str(halt_data.get('halt_time', 'N/A'))))
        self.halt_table.setItem(row, 3, QTableWidgetItem(str(halt_data.get('resume_time', 'N/A'))))
        self.halt_table.setItem(row, 4, QTableWidgetItem(str(halt_data.get('reason', 'N/A'))))
        
        price = halt_data.get('price', 'N/A')
        self.halt_table.setItem(row, 5, QTableWidgetItem(f"${price:.2f}" if isinstance(price, (int, float)) else str(price)))
    
    def _add_or_update_stock(self, table, stock_data, columns):
        """Add or update a stock in a table (for live trading channels)"""
        symbol = stock_data.get('symbol', 'N/A')
        
        # Find if symbol already exists
        row = -1
        for i in range(table.rowCount()):
            if table.item(i, 0) and table.item(i, 0).text() == symbol:
                row = i
                break
        
        # Add new row if not found
        if row == -1:
            row = table.rowCount()
            table.insertRow(row)
        
        # Update each column
        for col_idx, col_name in enumerate(columns):
            value = stock_data.get(col_name, 'N/A')
            
            # Format the value
            if col_name == 'symbol':
                item = QTableWidgetItem(str(value))
                item.setFont(QFont("Arial", 10, QFont.Bold))
            elif col_name == 'price' and isinstance(value, (int, float)):
                item = QTableWidgetItem(f"${value:.2f}")
            elif 'pct' in col_name or 'change' in col_name:
                if isinstance(value, (int, float)):
                    item = QTableWidgetItem(f"{value:+.2f}%")
                    if value > 0:
                        item.setForeground(QColor(0, 255, 0))
                    elif value < 0:
                        item.setForeground(QColor(255, 0, 0))
                else:
                    item = QTableWidgetItem(str(value))
            elif col_name == 'volume' and isinstance(value, (int, float)):
                item = QTableWidgetItem(f"{int(value):,}")
            elif col_name == 'float' and isinstance(value, (int, float)):
                item = QTableWidgetItem(f"{value/1e6:.1f}M")
            elif isinstance(value, float):
                item = QTableWidgetItem(f"{value:.2f}")
            else:
                item = QTableWidgetItem(str(value))
            
            table.setItem(row, col_idx, item)
    
    # =========================================================================
    # VAULT SYSTEM - News & Halts persistent storage
    # =========================================================================
    
    def connect_scanner_signals(self, tier3, news, halts):
        """Connect scanner signals to GUI slots for live updates"""
        self.log.scanner("[GUI-DEBUG] Entering connect_scanner_signals function")
        self.log.scanner(f"[GUI-DEBUG] tier3={tier3}, news={news}, halts={halts}")
        self.log.scanner("[GUI] Connecting live data feeds...")

        # Connect Tier3 channel signals (LIVE ONLY)
        if tier3 and hasattr(tier3, 'pregap_signal'):
            tier3.pregap_signal.connect(self.on_pregap_update)
            self.log.scanner("[GUI] OK PreGap feed connected (LIVE)")
        
        if tier3 and hasattr(tier3, 'hod_signal'):
            tier3.hod_signal.connect(self.on_hod_update)
            self.log.scanner("[GUI] OK HOD feed connected (LIVE)")
        
        if tier3 and hasattr(tier3, 'runup_signal'):
            tier3.runup_signal.connect(self.on_runup_update)
            self.log.scanner("[GUI] OK RunUP feed connected (LIVE)")
        
        if tier3 and hasattr(tier3, 'reversal_signal'):
            tier3.reversal_signal.connect(self.on_reversal_update)
            self.log.scanner("[GUI] OK Reversal feed connected (LIVE)")
        
        # Connect News signal (VAULT + LIVE)
        if news and hasattr(news, 'news_signal'):
            news.news_signal.connect(self.on_news_update)
            self.log.scanner("[GUI] OK News feed connected (VAULT + LIVE)")
        
        # Connect Halt signal (VAULT + LIVE)
        if halts and hasattr(halts, 'halt_signal'):
            halts.halt_signal.connect(self.on_halt_update)
            self.log.scanner("[GUI] OK Halt feed connected (VAULT + LIVE)")
        
        # Load existing news and halts from vault on startup
        self._load_existing_news()
        self._load_existing_halts()
    
    def _load_existing_news(self):
        """Load news vault on startup"""
        try:
            self.log.scanner("[GUI] Loading news vault...")
            self._refresh_news_vault()
        except Exception as e:
            self.log.crash(f"[GUI] Error loading news vault: {e}")
    
    def _load_existing_halts(self):
        """Load halt vault on startup"""
        try:
            self.log.scanner("[GUI] Loading halt vault...")
            self._refresh_halt_vault()
        except Exception as e:
            self.log.crash(f"[GUI] Error loading halt vault: {e}")
    
    def _refresh_vaults(self):
        """Auto-refresh vaults every 5 seconds"""
        self._refresh_news_vault()
        self._refresh_halt_vault()
    
    def _refresh_news_vault(self):
        """Refresh news table from vault files (bkgnews.json + news.json), with breaking news age filter."""
        try:
            self.log.scanner("=" * 80)
            self.log.scanner("[GUI-DEBUG] _refresh_news_vault() CALLED")
            self.log.scanner("=" * 80)
            
            self.news_table.setRowCount(0)

            # Load breaking news (bkgnews.json)
            bkgnews = self.fm.load_bkgnews()
            self.log.scanner(f"[GUI-DEBUG] Loaded bkgnews: {len(bkgnews)} items")
            
            # Load general news (news.json)
            news = self.fm.load_news()
            self.log.scanner(f"[GUI-DEBUG] Loaded news: {len(news)} items")

            # Combine all news
            all_news = {}
            all_news.update(bkgnews)
            all_news.update(news)
            self.log.scanner(f"[GUI-DEBUG] Combined news: {len(all_news)} items")

            # Sort by timestamp (newest first)
            sorted_news = sorted(
                all_news.items(),
                key=lambda x: x[1].get('timestamp', ''),
                reverse=True
            )

            from datetime import timezone
            now = datetime.now(timezone.utc)
            self.log.scanner(f"[GUI-DEBUG] Current time (UTC): {now}")
            
            shown = 0
            filtered_breaking = 0
            filtered_general = 0
            
            for news_id, news_item in sorted_news:
                # Calculate age
                try:
                    timestamp = datetime.fromisoformat(news_item['timestamp'].replace('Z', '+00:00'))
                    age_hours = (now - timestamp).total_seconds() / 3600
                    age_str = f"{int(age_hours)}h" if age_hours < 24 else f"{int(age_hours/24)}d"
                    self.log.scanner(f"[GUI-DEBUG] {news_item.get('symbol')}: age={age_hours:.2f}h, category={news_item.get('category')}")
                except Exception as e:
                    self.log.scanner(f"[GUI-DEBUG] ERROR calculating age for {news_id}: {e}")
                    age_hours = 999
                    age_str = "N/A"

                # Only show breaking news ≤2hr, general news ≤72hr
                category = news_item.get('category', '')
                if category == 'breaking' and age_hours > 2:
                    filtered_breaking += 1
                    self.log.scanner(f"[GUI-DEBUG] FILTERED OUT (breaking too old): {news_item.get('symbol')} - {age_hours:.2f}h")
                    continue
                if category == 'general' and age_hours > 72:
                    filtered_general += 1
                    self.log.scanner(f"[GUI-DEBUG] FILTERED OUT (general too old): {news_item.get('symbol')} - {age_hours:.2f}h")
                    continue

                self.log.scanner(f"[GUI-DEBUG] SHOWING: {news_item.get('symbol')} - {news_item.get('headline')[:50]}")
                
                gui_data = {
                    'symbol': news_item.get('symbol', 'N/A'),
                    'price': 0.0,
                    'change_pct': 0.0,
                    'headline': news_item.get('headline', 'No headline'),
                    'age': age_str,
                    'timestamp': news_item.get('timestamp', 'N/A')
                }
                self.on_news_update(gui_data)
                shown += 1

            self.log.scanner(f"[GUI-DEBUG] SUMMARY: shown={shown}, filtered_breaking={filtered_breaking}, filtered_general={filtered_general}")
            self.log.scanner(f"[GUI] OK News vault loaded: {shown} fresh items")

        except Exception as e:
            self.log.scanner(f"[GUI-DEBUG] EXCEPTION in _refresh_news_vault: {e}")
            import traceback
            self.log.scanner(traceback.format_exc())
            self.log.crash(f"[GUI] Error refreshing news vault: {e}")
    
    def _refresh_halt_vault(self):
        """Refresh halt table from vault files (active_halts.json + halts.json)"""
        try:
            # Clear existing table
            self.halt_table.setRowCount(0)
            
            # Load active halts
            active_halts = self.fm.load_active_halts()
            
            # Load historical halts
            historical_halts = self.fm.load_halts()
            
            # Combine all halts
            all_halts = {}
            all_halts.update(active_halts)
            all_halts.update(historical_halts)
            
            # Populate table
            for halt_id, halt_data in all_halts.items():
                self.on_halt_update(halt_data)
            
            if len(all_halts) > 0:
                self.log.scanner(f"[GUI] OK Halt vault refreshed: {len(all_halts)} items")
            
        except Exception as e:
            self.log.crash(f"[GUI] Error refreshing halt vault: {e}")
    
    # =========================================================================
    # Button Handlers
    # =========================================================================
    
    def _on_news_clicked(self):
        """Handle NEWS button click"""
        self.log.scanner("[GUI] NEWS button clicked")
        # Switch to News tab (index 4)
        self.tabs.setCurrentIndex(4)
        self.status_bar.showMessage("Switched to News channel")
    
    def _on_update_clicked(self):
        """Handle UPDATE button click - force Tier1 scan and refresh vaults"""
        self.log.scanner("[GUI] UPDATE button clicked - forcing Tier1 prefilter scan and refreshing vaults")
        if self.tier1:
            self.tier1.force_scan()
        self._refresh_news_vault()
        self._refresh_halt_vault()
        self._update_indices()
        self.status_bar.showMessage("Tier1 prefilter scan + News & Halt vaults refreshed")
    
    def _on_kiosk_clicked(self):
        """Handle KIOSK button click"""
        self.log.scanner("[GUI] KIOSK mode activated")
        # Toggle fullscreen mode
        if self.isFullScreen():
            self.showNormal()
            self.status_bar.showMessage("Exited Kiosk mode")
        else:
            self.showFullScreen()
            self.status_bar.showMessage("Entered Kiosk mode (press ESC to exit)")
        
    def _create_channel_tab(self, channel_name, columns):
        """Create a table widget for a channel"""
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        
        # Table styling
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        
        # Auto-resize columns
        header = table.horizontalHeader()
        for i in range(len(columns)):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        return table
        
    def _update_time(self):
        """Update the time display (12-hour format, no date)"""
        # Local time
        local_time = datetime.now()
        local_tz_name = local_time.astimezone().tzinfo.tzname(local_time)
        self.local_time_label.setText(f"Local: {local_time.strftime('%I:%M:%S %p')} {local_tz_name}")
        
        # NYC time (ET)
        nyc_tz = pytz.timezone('America/New_York')
        nyc_time = datetime.now(nyc_tz)
        self.nyc_time_label.setText(f"NYC:   {nyc_time.strftime('%I:%M:%S %p')} ET")
        
        # Update market session based on NYC time
        hour = nyc_time.hour
        minute = nyc_time.minute
        
        if 4 <= hour < 9 or (hour == 9 and minute < 30):
            self.market_session.setText("Market: PREMARKET")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #ffaa00; font-size: 16px;")
        elif (hour == 9 and minute >= 30) or (9 < hour < 16):
            self.market_session.setText("Market: OPEN")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #00ff00; font-size: 16px;")
        elif 16 <= hour < 20:
            self.market_session.setText("Market: AFTERHOURS")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #ffaa00; font-size: 16px;")
        else:
            self.market_session.setText("Market: CLOSED")
            self.market_session.setStyleSheet("font-weight: bold; padding: 5px; color: #ff0000; font-size: 16px;")
    
    def _update_indices(self):
        """Update market indices (S&P 500, NASDAQ, DOW)"""
        try:
            import yfinance as yf
            
            # S&P 500 (SPY ETF as proxy)
            spy = yf.Ticker("SPY")
            spy_price = spy.info.get('regularMarketPrice', spy.info.get('currentPrice', 0))
            spy_change = spy.info.get('regularMarketChangePercent', 0)
            
            # NASDAQ (QQQ ETF as proxy)
            qqq = yf.Ticker("QQQ")
            qqq_price = qqq.info.get('regularMarketPrice', qqq.info.get('currentPrice', 0))
            qqq_change = qqq.info.get('regularMarketChangePercent', 0)
            
            # DOW (DIA ETF as proxy)
            dia = yf.Ticker("DIA")
            dia_price = dia.info.get('regularMarketPrice', dia.info.get('currentPrice', 0))
            dia_change = dia.info.get('regularMarketChangePercent', 0)
            
            # Update S&P 500
            sp500_color = "#00ff00" if spy_change >= 0 else "#ff0000"
            self.sp500_label.setText(f"S&P 500: ${spy_price:.2f} ({spy_change:+.2f}%)")
            self.sp500_label.setStyleSheet(f"font-size: 13px; font-weight: bold; padding: 5px; margin-right: 20px; color: {sp500_color};")
            
            # Update NASDAQ
            nasdaq_color = "#00ff00" if qqq_change >= 0 else "#ff0000"
            self.nasdaq_label.setText(f"NASDAQ: ${qqq_price:.2f} ({qqq_change:+.2f}%)")
            self.nasdaq_label.setStyleSheet(f"font-size: 13px; font-weight: bold; padding: 5px; margin-right: 20px; color: {nasdaq_color};")
            
            # Update DOW
            dow_color = "#00ff00" if dia_change >= 0 else "#ff0000"
            self.dow_label.setText(f"DOW: ${dia_price:.2f} ({dia_change:+.2f}%)")
            self.dow_label.setStyleSheet(f"font-size: 13px; font-weight: bold; padding: 5px; color: {dow_color};")
            
        except Exception as e:
            self.log.crash(f"[GUI] Error updating indices: {e}")
    
    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
            self.status_bar.showMessage("Exited Kiosk mode")
            
    def _apply_stylesheet(self):
        """Apply dark theme stylesheet to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
            }
            QWidget {
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                background-color: #161b22;
            }
            QTabBar {
                qproperty-expanding: true;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                background-color: #161b22;
                color: #8b949e;
                padding: 10px 50px;
                margin-right: 8px;
                border: 1px solid #30363d;
                border-bottom: none;
                font-size: 14px;
                min-width: 150px;
                min-height: 38px;
            }
            QTabBar::tab:selected {
                background-color: #0d1117;
                color: #58a6ff;
                font-weight: bold;
            }
            QTableWidget {
                background-color: #0d1117;
                alternate-background-color: #161b22;
                gridline-color: #30363d;
                border: 1px solid #30363d;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #c9d1d9;
                padding: 8px;
                border: 1px solid #30363d;
                font-weight: bold;
            }
            QStatusBar {
                background-color: #161b22;
                color: #8b949e;
                border-top: 1px solid #30363d;
            }
        """)