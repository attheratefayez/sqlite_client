"""Application entry point for the SQLite Client.

Provides :func:`create_app` to initialise the QApplication and
:func:`run` as the main entry point. Theme is applied by the
main window based on saved settings.
"""

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def create_app() -> QApplication:
    """Create and configure the QApplication instance.

    Sets the application name and organization name.
    The theme stylesheet is applied by the main window on startup.

    Returns:
        Configured QApplication instance.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("SQLite Client")
    app.setOrganizationName("sqlite-client")
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
