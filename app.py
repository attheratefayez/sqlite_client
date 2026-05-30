"""Application entry point for the SQLite Client.

Provides :func:`create_app` to initialise the QApplication with styles
and :func:`run` as the main entry point.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow
from resources.style import LIGHT_THEME


def create_app() -> QApplication:
    """Create and configure the QApplication instance.

    Sets the application name, organization name, and applies the
    initial light theme stylesheet. Theme is later managed from the
    main window.

    Returns:
        Configured QApplication instance.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("SQLite Client")
    app.setOrganizationName("sqlite-client")
    app.setStyleSheet(LIGHT_THEME)
    return app


def run() -> None:
    """Launch the SQLite Client application.

    Creates the application, shows the main window, and enters the
    Qt event loop.
    """
    app = create_app()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
