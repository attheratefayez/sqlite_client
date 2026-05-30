import pytest
import tempfile
import pathlib
from PyQt6.QtCore import Qt
from ui.connection_dialog import ConnectionDialog


@pytest.fixture
def dialog(qtbot):
    dlg = ConnectionDialog(recent_files=[])
    qtbot.addWidget(dlg)
    return dlg


class TestConnectionDialog:
    def test_title(self, dialog):
        assert dialog.windowTitle() == "Open Database"

    def test_recent_files_populated(self, qtbot):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        dlg = ConnectionDialog(recent_files=[tmp.name])
        qtbot.addWidget(dlg)
        assert dlg._recent_list.count() == 1
        pathlib.Path(tmp.name).unlink(missing_ok=True)

    def test_recent_files_skips_missing(self, qtbot):
        dlg = ConnectionDialog(recent_files=["/nonexistent/file.db"])
        qtbot.addWidget(dlg)
        assert dlg._recent_list.count() == 0

    def test_close_button_rejects(self, dialog, qtbot):
        dialog.reject()
        assert dialog.selected_path is None
