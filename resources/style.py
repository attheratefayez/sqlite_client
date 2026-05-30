"""Application stylesheet for the SQLite Client.

Defines the Qt stylesheet string :data:`STYLESHEET` used to theme the
entire application.
"""

STYLESHEET = """
QMainWindow {
    background-color: #f5f5f5;
}

QTreeWidget {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    alternate-background-color: #fafafa;
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

QLineEdit {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px 8px;
    background-color: #ffffff;
}

QLineEdit:focus {
    border-color: #0078d4;
}

QSpinBox {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px;
    background-color: #ffffff;
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
}

QMenuBar {
    background-color: #f5f5f5;
    border-bottom: 1px solid #d0d0d0;
}

QMenuBar::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
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
}

QSplitter::handle {
    background-color: #d0d0d0;
    width: 2px;
}
"""
