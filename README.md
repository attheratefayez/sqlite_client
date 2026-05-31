# SQLite Client

A PyQt6-based desktop SQLite database client with a tabbed interface, SQL query editor with syntax highlighting, table data browser with pagination and deferred inline editing, batch delete, export, dark/light theme, app-state persistence, and an extensible chat assistant. All database operations and chat-agent calls run asynchronously on background threads to keep the UI responsive.

## Features

- **Database connection management** — Open existing `.db`/`.sqlite` files or create new databases with a file picker or recent files list
- **Schema browser** — Tree view of tables (with column names, types, primary keys, nullable, default values) and views
- **SQL query editor** — Multi-tab editor with SQL syntax highlighting and `Ctrl+Enter` execution
- **Query results** — Tabular results display with row count and execution time, exportable
- **Data browser** — Paginated table browsing with adjustable page size (10–1000), search/filter across all columns, deferred inline cell editing via **Commit Changes** button, add row, batch delete with confirmation
- **Export** — Export tables or query results to CSV, JSON, or SQL INSERT statements
- **Dark/Light mode** — Toggle via View menu, persisted across sessions
- **App-state persistence** — Last-opened database, recent files list, and theme preference saved via `QSettings`
- **Chat assistant** — Collapsible dock panel on the right side for natural-language queries about your database. Agent runs on its own background thread. Currently ships with a `DemoAgent` (placeholder); designed for easy integration with LangChain or other LLM frameworks.
- **Non-blocking operations** — All database reads, writes, and chat-agent calls execute on dedicated worker threads so the GUI never freezes
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
├── main.py                  # Entry point — parses CLI args, creates QApplication
├── app.py                   # QApplication factory (no hardcoded theme)
├── pyproject.toml           # Project metadata, deps, tool config
├── README.md
├── core/
│   ├── __init__.py
│   ├── database.py          # DatabaseConnection — sqlite3 wrapper, schema introspection, WAL mode
│   ├── query_executor.py    # QueryExecutor — SQL execution with timing, error handling, is_select detection
│   ├── worker.py            # DatabaseWorker — QObject on a QThread for non-blocking DB operations
│   └── export.py            # Export to CSV, JSON, and SQL INSERT format
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # MainWindow — QMainWindow, splitter layout, worker thread lifecycle, menu
│   ├── schema_browser.py    # SchemaBrowser — QTreeWidget of tables, views, columns
│   ├── query_editor.py      # QueryEditorWidget — multi-tab SQL editor with per-tab results
│   ├── results_view.py      # ResultsView — QTableView for query results, info bar (rows + duration)
│   ├── data_browser.py      # DataBrowser — paginated table view, deferred edits, Commit Changes button
│   ├── connection_dialog.py # ConnectionDialog — open / create database dialog
│   ├── export_dialog.py     # ExportDialog — format picker and save dialog
│   └── syntax_highlight.py  # SqlHighlighter — QSyntaxHighlighter for SQL keywords, strings, numbers
├── resources/
│   ├── __init__.py
│   └── style.py             # LIGHT_THEME, DARK_THEME, and THEMES dict with comprehensive QSS
└── tests/
    ├── __init__.py
    ├── chat/
    │   ├── __init__.py
    │   ├── test_agent.py            # 4 tests
    │   ├── test_chat_panel.py       # 4 tests
    │   └── test_worker.py           # 2 tests
    ├── core/
    │   ├── __init__.py
    │   ├── test_database.py       # 14 tests
    │   ├── test_query_executor.py # 16 tests
    │   └── test_export.py         # 9 tests
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

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       MainWindow (QMainWindow)                          │
│  ┌──────────────┬────────────────────────────────┬──────────────────┐   │
│  │              │                                │                  │   │
│  │  Schema      │     QTabWidget (right tabs)    │  Chat Dock       │   │
│  │  Browser     │  ┌───────────────────────┐    │  (QDockWidget)   │   │
│  │  (QTree-     │  │  QueryEditorWidget    │    │  ┌────────────┐  │   │
│  │   Widget)    │  │  ┌────┐ ┌────┐ ┌────┐│    │  │ You: ...   │  │   │
│  │              │  │  │SQL │ │SQL │ │SQL ││    │  │ Agent: ... │  │   │
│  │  emits       │  │  │ #1 │ │ #2 │ │ #3 ││    │  │            │  │   │
│  │  *_selected  │  │  └────┘ └────┘ └────┘│    │  ├────────────┤  │   │
│  │              │  ├───────────────────────┤    │  │ [Input]    │  │   │
│  │              │  │  DataBrowser (per     │    │  │ [Send]     │  │   │
│  │              │  │  table)               │    │  └────────────┘  │   │
│  │              │  │  ┌─────────────────┐  │    │                  │   │
│  │              │  │  │ QTableView      │  │    │  Collapsible    │   │
│  │              │  │  │ [✔][id][name]   │  │    │  via X button   │   │
│  │              │  │  │ [☑][ 1][Alice]  │  │    │  or View > Chat │   │
│  │              │  │  └─────────────────┘  │    │                  │   │
│  │              │  └───────────────────────┘    │                  │   │
│  └──────────────┴────────────────────────────────┴──────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Status Bar:  Connected: /path/to/database.db                    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                         │
                         │ Signals (cross-thread via queued connections)
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────┐  ┌──────────────────────┐  │
│  │         Worker Thread #1                 │  │  Worker Thread #2   │  │
│  │  ┌─────────────────────────────────┐    │  │  ┌────────────────┐  │  │
│  │  │     DatabaseWorker (QObject)    │    │  │  │ ChatWorker     │  │  │
│  │  │  ┌──────────────────┐           │    │  │  │ (QObject)      │  │  │
│  │  │  │ DatabaseConnection│           │    │  │  │                │  │  │
│  │  │  │ (sqlite3, WAL)   │           │    │  │  │ Slots:         │  │  │
│  │  │  └──────────────────┘           │    │  │  │ - send_message │  │  │
│  │  │  ┌──────────────────┐           │    │  │  │                │  │  │
│  │  │  │ QueryExecutor    │           │    │  │  │ Signals:       │  │  │
│  │  │  └──────────────────┘           │    │  │  │ - response_    │  │  │
│  │  │                                │    │  │  │   received(msg, │  │  │
│  │  │  Slots:                        │    │  │  │   reply)        │  │  │
│  │  │  - request_query(sql)          │    │  │  └────────────────┘  │  │
│  │  │  - request_data_page(...)      │    │  └──────────────────────┘  │  │
│  │  │  - request_commit(...)         │    │                            │  │
│  │  │  - request_add_row(...)        │    │                            │  │
│  │  │  - request_delete_rows(...)    │    │                            │  │
│  │  │                                │    │                            │  │
│  │  │  Signals:                      │    │                            │  │
│  │  │  - query_finished(QueryResult) │    │                            │  │
│  │  │  - data_page_finished(...)     │    │                            │  │
│  │  │  - edits_committed(table)      │    │                            │  │
│  │  │  - row_added(table)            │    │                            │  │
│  │  │  - rows_deleted(table)         │    │                            │  │
│  │  │  - error(msg)                  │    │                            │  │
│  │  └─────────────────────────────────┘    │                            │
│  └─────────────────────────────────────────┘  └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

#### Query Execution
```
User types SQL → Ctrl+Enter
  └─► QueryEditor emits execute_query_requested(sql)
       └─► MainWindow relays to DatabaseWorker.request_query(sql) [queued]
            └─► Worker thread executes via QueryExecutor
                 └─► Worker emits query_finished(QueryResult) [queued]
                      └─► QueryEditor receives → populates ResultsView
```

#### Data Browser Page Load
```
User opens table / navigates / searches
  └─► DataBrowser emits load_page_requested(table, page, size, search)
       └─► Worker.request_data_page(...)
            └─► Worker thread: COUNT(*) + SELECT with LIMIT/OFFSET
                 └─► Worker emits data_page_finished(table, cols, rows, total)
                      └─► DataBrowser._on_data_page_loaded → updates DataTableModel
```

#### Chat Message Flow
```
User types message → presses Enter / clicks Send
  └─► ChatPanel emits message_sent(text)
       └─► MainWindow relays to ChatWorker.send_message(text) [queued]
            └─► Chat Worker thread: agent.answer(text)
                 └─► Worker emits response_received(user_msg, reply) [queued]
                      └─► ChatPanel.append_reply → shown in history
```

#### Inline Edit Flow
```
User edits a cell
  └─► DataTableModel emits data_changed(row, col)
       └─► DataBrowser.record_edit → stores (pk, col) → new_value in _pending_edits
            └─► "Commit Changes" button becomes enabled

User clicks "Commit Changes"
  └─► DataBrowser emits commit_requested(table, columns, pending_edits)
       └─► Worker.request_commit(table, columns, pending)
            └─► Worker thread: UPDATE each edit + COMMIT
                 └─► Worker emits edits_committed(table_name)
                      └─► DataBrowser._on_action_done → _request_page() → reloads data
                           └─► _on_data_page_loaded → clears _pending_edits, disables Commit button
```

### Key Design Decisions

- **sqlite3 + QThread** — Uses the `sqlite3` module directly (not `QSqlDatabase`) for full control over PRAGMAs, parameterised queries, and `check_same_thread=False` for cross-thread access.
- **`check_same_thread=False`** — The `DatabaseConnection` opens SQLite with `check_same_thread=False` so the connection can be created on any thread and used from the worker thread.
- **Model/View pattern** — `QAbstractTableModel` subclasses (`DataTableModel`, `ResultTableModel`) separate data from presentation widgets.
- **Parameterised queries** — All user-influenced SQL uses `?` placeholders to prevent SQL injection.
- **PRAGMA quoting** — PRAGMA statements use string formatting with double-quoting (`_quote()`) since SQLite does not support `?` placeholders in PRAGMAs.
- **Deferred inline edits** — Cell edits are collected in `_pending_edits` and batch-committed in a single transaction when the user clicks **Commit Changes**. Unsaved-change prompts on navigation.
- **Async worker** — All heavy DB operations run on a `DatabaseWorker` on a dedicated `QThread`. The worker owns its own `DatabaseConnection` to the same file. Schema/introspection queries remain synchronous on the main-thread connection.
- **State persistence** — `QSettings` persists dark mode preference, recent files list, and last-opened database path.
- **Feature branch workflow** — All changes go on feature branches, then fast-forward merged into `main`.
- **Extensible agent architecture** — `ChatAgent` is an abstract base class; `DemoAgent` provides a placeholder. Swap in a LangChain-powered agent by implementing the `answer(message) -> str` interface.
- **Non-blocking chat** — The `ChatWorker` runs on its own `QThread` (separate from the database worker), so agent calls never block the UI or database operations.
- **Collapsible chat panel** — Uses `QDockWidget` on the right side of `MainWindow`. The user can close it (via X or **View > Chat** toggle) without losing state.

## Development

```bash
# Install with development dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/core/test_database.py -v

# Run with coverage
uv run pytest --cov=core --cov=ui
```
