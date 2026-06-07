"""Application stylesheets for the SQLite Client.

Provides light and dark theme stylesheet strings.
"""

LIGHT_THEME = """
QMainWindow, QDialog {
    background-color: #f5f5f5;
}

QTreeWidget, QTreeView {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    alternate-background-color: #fafafa;
}

QTreeView::item:hover, QTreeWidget::item:hover {
    background-color: #e8f0fe;
}

QTreeView::item:selected, QTreeWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QTableView {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    alternate-background-color: #fafafa;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
    gridline-color: #e0e0e0;
}

QTableView::item:hover {
    background-color: #e8f0fe;
}

QHeaderView::section {
    background-color: #e8e8e8;
    padding: 4px;
    border: 1px solid #d0d0d0;
    font-weight: bold;
}

QHeaderView::section:hover {
    background-color: #d8d8d8;
}

QPushButton {
    background-color: #0078d4;
    color: #ffffff;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #106ebe;
}

QPushButton:pressed {
    background-color: #005a9e;
}

QPushButton:disabled {
    background-color: #cccccc;
    color: #888888;
}

QDialogButtonBox QPushButton {
    min-height: 24px;
    padding: 4px 16px;
}

QLineEdit {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px 8px;
    background-color: #ffffff;
    color: #333333;
}

QLineEdit:focus {
    border-color: #0078d4;
}

QSpinBox {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px;
    background-color: #ffffff;
    color: #333333;
}

QTabWidget::pane {
    border: 1px solid #d0d0d0;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #e8e8e8;
    padding: 6px 16px;
    border: 1px solid #d0d0d0;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #333333;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    border-bottom-color: #ffffff;
}

QTabBar::tab:hover:!selected {
    background-color: #f0f0f0;
}

QStatusBar {
    background-color: #e8e8e8;
    border-top: 1px solid #d0d0d0;
    color: #333333;
}

QMenuBar {
    background-color: #f5f5f5;
    border-bottom: 1px solid #d0d0d0;
    color: #333333;
}

QMenuBar::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    color: #333333;
}

QMenu::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QLabel {
    color: #333333;
}

QCheckBox {
    spacing: 6px;
    color: #333333;
}

QSplitter::handle {
    background-color: #d0d0d0;
    width: 2px;
}

QListWidget {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    color: #333333;
}

QListWidget::item:hover {
    background-color: #e8f0fe;
}

QListWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QDockWidget {
    color: #333333;
}

QDockWidget::title {
    background-color: #e8e8e8;
    padding: 6px;
    color: #333333;
}

QTextEdit {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #d0d0d0;
}
"""

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1e1e1e;
}

QTreeWidget, QTreeView {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    alternate-background-color: #2d2d2d;
    color: #cccccc;
}

QTreeView::item:hover, QTreeWidget::item:hover {
    background-color: #2a2d2e;
}

QTreeView::item:selected, QTreeWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QTableView {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    alternate-background-color: #2d2d2d;
    selection-background-color: #094771;
    selection-color: #ffffff;
    gridline-color: #3c3c3c;
    color: #cccccc;
}

QTableView::item:hover {
    background-color: #2a2d2e;
}

QHeaderView::section {
    background-color: #333333;
    padding: 4px;
    border: 1px solid #3c3c3c;
    font-weight: bold;
    color: #cccccc;
}

QHeaderView::section:hover {
    background-color: #404040;
}

QPushButton {
    background-color: #0e639c;
    color: #ffffff;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #1177bb;
}

QPushButton:pressed {
    background-color: #094771;
}

QPushButton:disabled {
    background-color: #333333;
    color: #666666;
}

QDialogButtonBox QPushButton {
    min-height: 24px;
    padding: 4px 16px;
}

QLineEdit {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px 8px;
    background-color: #3c3c3c;
    color: #cccccc;
}

QLineEdit:focus {
    border-color: #0e639c;
}

QSpinBox {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px;
    background-color: #3c3c3c;
    color: #cccccc;
}

QTabWidget::pane {
    border: 1px solid #3c3c3c;
    background-color: #252526;
}

QTabBar::tab {
    background-color: #2d2d2d;
    padding: 6px 16px;
    border: 1px solid #3c3c3c;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #999999;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-bottom-color: #1e1e1e;
    color: #ffffff;
}

QTabBar::tab:hover:!selected {
    background-color: #383838;
    color: #cccccc;
}

QStatusBar {
    background-color: #007acc;
    border-top: 1px solid #3c3c3c;
    color: #ffffff;
}

QMenuBar {
    background-color: #3c3c3c;
    border-bottom: 1px solid #3c3c3c;
    color: #cccccc;
}

QMenuBar::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QMenu {
    background-color: #2d2d2d;
    border: 1px solid #454545;
    color: #cccccc;
}

QMenu::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QLabel {
    color: #cccccc;
}

QCheckBox {
    spacing: 6px;
    color: #cccccc;
}

QSplitter::handle {
    background-color: #3c3c3c;
    width: 2px;
}

QListWidget {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    color: #cccccc;
}

QListWidget::item:hover {
    background-color: #2a2d2e;
}

QListWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QDockWidget {
    color: #cccccc;
    titlebar-close-icon: url(none);
}

QDockWidget::title {
    background-color: #2d2d2d;
    padding: 6px;
    color: #cccccc;
}

QTextEdit {
    background-color: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
}

QPlainTextEdit {
    background-color: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
}

QScrollBar::handle:vertical {
    background-color: #424242;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #555555;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
}

QScrollBar::handle:horizontal {
    background-color: #424242;
    border-radius: 4px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #555555;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

THEMES = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
}
