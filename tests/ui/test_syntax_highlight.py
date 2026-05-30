import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPlainTextEdit
from ui.syntax_highlight import SqlHighlighter, SQL_KEYWORDS


class TestSqlHighlighter:
    def _make_editor(self, qtbot, text: str):
        editor = QPlainTextEdit()
        qtbot.addWidget(editor)
        editor.setPlainText(text)
        hl = SqlHighlighter(editor.document())
        hl.rehighlight()
        return editor, hl

    def _get_formats(self, editor):
        block = editor.document().firstBlock()
        layout = block.layout()
        return list(layout.formats()) if layout else []

    def test_highlights_keyword(self, qtbot):
        editor, _ = self._make_editor(qtbot, "SELECT * FROM users")
        formats = self._get_formats(editor)
        keywords_found = []
        text = editor.toPlainText()
        for f in formats:
            t = text[f.start:f.start + f.length]
            if f.format.foreground().color() == QColor("#0000FF"):
                keywords_found.append(t)
        assert "SELECT" in keywords_found
        assert "FROM" in keywords_found

    def test_highlights_string(self, qtbot):
        editor, _ = self._make_editor(qtbot, "WHERE name = 'Alice'")
        formats = self._get_formats(editor)
        strings_found = []
        text = editor.toPlainText()
        for f in formats:
            t = text[f.start:f.start + f.length]
            if f.format.foreground().color() == QColor("#008000"):
                strings_found.append(t)
        assert "'Alice'" in strings_found

    def test_highlights_number(self, qtbot):
        editor, _ = self._make_editor(qtbot, "LIMIT 42")
        formats = self._get_formats(editor)
        numbers_found = []
        text = editor.toPlainText()
        for f in formats:
            t = text[f.start:f.start + f.length]
            if f.format.foreground().color() == QColor("#FF0000"):
                numbers_found.append(t)
        assert "42" in numbers_found

    def test_highlights_comment(self, qtbot):
        editor, _ = self._make_editor(qtbot, "SELECT 1 -- comment")
        formats = self._get_formats(editor)
        comments_found = []
        text = editor.toPlainText()
        for f in formats:
            t = text[f.start:f.start + f.length]
            if f.format.foreground().color() == QColor("#808080") and f.format.fontItalic():
                comments_found.append(t)
        assert "-- comment" in comments_found

    def test_keywords_are_uppercase(self):
        for kw in SQL_KEYWORDS:
            assert kw == kw.upper(), f"Keyword '{kw}' is not uppercase"
