from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


SQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
    "DELETE", "CREATE", "TABLE", "DROP", "ALTER", "ADD", "COLUMN", "INDEX",
    "VIEW", "AS", "ON", "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE",
    "BETWEEN", "EXISTS", "UNION", "ALL", "DISTINCT", "ORDER", "BY", "ASC",
    "DESC", "GROUP", "HAVING", "LIMIT", "OFFSET", "JOIN", "LEFT", "RIGHT",
    "INNER", "OUTER", "CROSS", "FULL", "PRIMARY", "KEY", "FOREIGN", "REFERENCES",
    "CASCADE", "CONSTRAINT", "UNIQUE", "CHECK", "DEFAULT", "AUTOINCREMENT",
    "INTEGER", "TEXT", "REAL", "BLOB", "NUMERIC", "BOOLEAN", "DATE", "DATETIME",
    "IF", "THEN", "ELSE", "END", "CASE", "WHEN", "BEGIN", "COMMIT", "ROLLBACK",
    "TRANSACTION", "EXCEPT", "INTERSECT", "PRAGMA", "REPLACE", "TRIGGER",
    "TEMPORARY", "TEMP", "VACUUM", "ANALYZE", "REINDEX", "RENAME", "TO",
    "WITH", "RECURSIVE", "CAST", "TRUE", "FALSE",
]


class SqlHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#0000FF"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        self._keyword_format = keyword_format

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#008000"))
        self._string_format = string_format

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#FF0000"))
        self._number_format = number_format

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#808080"))
        comment_format.setFontItalic(True)
        self._comment_format = comment_format

        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        for word in SQL_KEYWORDS:
            pattern = QRegularExpression(
                f"\\b{word}\\b", QRegularExpression.PatternOption.CaseInsensitiveOption
            )
            self._rules.append((pattern, keyword_format))

        self._rules.append(
            (QRegularExpression(r"'[^']*'"), string_format)
        )
        self._rules.append(
            (QRegularExpression(r"\b\d+\.?\d*\b"), number_format)
        )
        self._rules.append(
            (QRegularExpression(r"--[^\n]*"), comment_format)
        )

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
