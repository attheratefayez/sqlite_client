# SQLite Client

A PyQt6-based desktop SQLite database client with a tabbed interface, SQL query editor with syntax highlighting, table data browser with inline editing, batch delete, and export to CSV/JSON/SQL.

## Features

- **Database connection management** — Open existing `.db`/`.sqlite` files or create new databases with a file picker or recent files list
- **Schema browser** — Tree view of tables (with column details, types, constraints) and views
- **SQL query editor** — Multi-tab editor with SQL syntax highlighting and `Ctrl+Enter` execution
- **Query results** — Tabular results display with row count and execution time
- **Data browser** — Paginated table browsing with adjustable page size, search/filter across columns, inline cell editing (auto-persisted via UPDATE), add row, and batch delete with confirmation
- **Export** — Export tables or query results to CSV, JSON, or SQL INSERT statements
- **Keyboard shortcuts** — `Ctrl+O` (open database), `Ctrl+W` (close database), `Ctrl+Q` (quit), `Ctrl+Enter` (execute query)

## Requirements

- Python 3.13+
- PyQt6 >= 6.5

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd sqlite_client

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate

# Install dependencies
uv sync --extra dev
```

## Usage

```bash
# Launch the application
uv run python main.py
```

### Running Tests

```bash
uv run pytest -v
```

## Project Structure

```
sqlite_client/
├── main.py                  # Entry point
├── app.py                   # QApplication setup and launch
├── pyproject.toml           # Project metadata and dependencies
├── README.md
├── core/
│   ├── __init__.py
│   ├── database.py          # DatabaseConnection — sqlite3 wrapper with schema introspection
│   ├── query_executor.py    # QueryExecutor — SQL execution with timing and error handling
│   └── export.py            # Export to CSV, JSON, SQL INSERT
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # MainWindow — QMainWindow with splitter layout
│   ├── schema_browser.py    # SchemaBrowser — QTreeWidget of tables, views, columns
│   ├── query_editor.py      # QueryEditorWidget — multi-tab SQL editor
│   ├── results_view.py      # ResultsView — QTableView for query results
│   ├── data_browser.py      # DataBrowser — paginated table view with inline editing
│   ├── connection_dialog.py # ConnectionDialog — open/create database dialog
│   ├── export_dialog.py     # ExportDialog — format picker and save dialog
│   └── syntax_highlight.py  # SqlHighlighter — QSyntaxHighlighter for SQL keywords
├── resources/
│   ├── __init__.py
│   └── style.py             # Application QSS stylesheet
└── tests/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── test_database.py      # 14 tests
    │   ├── test_query_executor.py # 16 tests
    │   └── test_export.py        # 9 tests
    └── ui/
        ├── __init__.py
        ├── test_main_window.py        # 11 tests
        ├── test_schema_browser.py     # 6 tests
        ├── test_query_editor.py       # 9 tests
        ├── test_results_view.py       # 10 tests
        ├── test_data_browser.py       # 16 tests
        ├── test_connection_dialog.py  # 4 tests
        └── test_syntax_highlight.py   # 5 tests
```

## Architecture

The application follows a layered architecture:

- **Core layer** (`core/`) — Business logic and data access, pure Python with no Qt dependencies in some modules
- **UI layer** (`ui/`) — PyQt6 widgets using Qt's Model/View architecture for data display
- **Tests** (`tests/`) — pytest and pytest-qt for both core logic and UI component testing

### Key Design Decisions

- **Model/View pattern** — `QAbstractTableModel` subclasses separate data from presentation
- **Parameterized queries** — All user-influenced SQL uses parameterized queries (via `?` placeholders) to prevent SQL injection
- **SQLite PRAGMA** — PRAGMA statements use string formatting with proper quoting (not parameter binding) since SQLite does not support `?` placeholders in PRAGMAs
- **Inline edit persistence** — Cell edits in the data browser auto-save via UPDATE using the primary key as the WHERE clause

## Development

```bash
# Install with development dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/core/test_database.py -v
```
