from __future__ import annotations

import sqlite3
from pathlib import Path
from time import perf_counter
from typing import Any

from .config import ConfigError
from .sqlguard import SqlRejected, ensure_limit

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}
_DENIED_FUNCTIONS = {"load_extension", "fts3_tokenizer", "writefile", "readfile", "edit"}


class ReadOnlyDatabase:
    def __init__(self, path: str | Path, timeout_s: float = 5.0, max_rows: int = 100):
        self.path = Path(path)
        if not self.path.is_file():
            raise ConfigError(f"Немає бази: {self.path}")
        self.timeout_s = timeout_s
        self.max_rows = max_rows
        self.uri = f"file:{self.path.resolve().as_posix()}?mode=ro"

    @staticmethod
    def _authorize(action: int, arg1, arg2, database, source) -> int:
        if action == sqlite3.SQLITE_FUNCTION:
            # Розташування назви функції в аргументах різниться між збірками SQLite.
            name = next((a for a in (arg1, arg2) if isinstance(a, str)), "")
            return sqlite3.SQLITE_DENY if name.lower() in _DENIED_FUNCTIONS else sqlite3.SQLITE_OK
        return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY

    def _connect(self, guarded: bool = True) -> sqlite3.Connection:
        connection = sqlite3.connect(self.uri, uri=True)
        connection.execute("PRAGMA query_only = ON")
        if guarded:
            connection.set_authorizer(self._authorize)
        return connection

    def execute(self, sql: str) -> dict[str, Any]:
        """Виконує запит і повертає результат або помилку як дані, без винятків нагору."""
        started = perf_counter()
        try:
            shown, added = ensure_limit(sql, self.max_rows)
            # Виконуємо з LIMIT на 1 більше, інакше не видно, що рядки були відрізані.
            prepared, _ = ensure_limit(sql, self.max_rows + 1)
        except SqlRejected as exc:
            return {"ok": False, "error": str(exc), "sql": sql, "elapsed_s": perf_counter() - started}

        connection = None
        try:
            connection = self._connect()
            deadline = perf_counter() + self.timeout_s
            connection.set_progress_handler(lambda: 1 if perf_counter() > deadline else 0, 1000)
            cursor = connection.execute(prepared)
            columns = [description[0] for description in cursor.description] if cursor.description else []
            fetched = cursor.fetchmany(self.max_rows + 1)
            truncated = len(fetched) > self.max_rows
            rows = [list(row) for row in fetched[: self.max_rows]]
            return {
                "ok": True,
                "sql": shown,
                "limit_added": added,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
                "elapsed_s": perf_counter() - started,
            }
        except sqlite3.Error as exc:
            return {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "sql": shown,
                "elapsed_s": perf_counter() - started,
            }
        finally:
            if connection is not None:
                connection.close()

    def tables(self) -> list[str]:
        connection = self._connect(guarded=False)
        try:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            return [row[0] for row in rows]
        finally:
            connection.close()

    def schema(self, table: str | None = None) -> str:
        available = self.tables()
        if table is not None:
            if table not in available:
                raise KeyError(f"невідома таблиця {table!r}; доступні: {', '.join(available)}")
            selected = [table]
        else:
            selected = available

        connection = self._connect(guarded=False)
        try:
            blocks = []
            for name in selected:
                columns = connection.execute(f'PRAGMA table_info("{name}")').fetchall()
                definition = ", ".join(
                    f"{column[1]} {column[2] or ''}{' NOT NULL' if column[3] else ''}".strip()
                    for column in columns
                )
                block = [f"{name}({definition})"]
                primary = [column[1] for column in columns if column[5]]
                if primary:
                    block.append("  PK: " + ", ".join(primary))
                for foreign in connection.execute(f'PRAGMA foreign_key_list("{name}")').fetchall():
                    block.append(f"  FK: {foreign[3]} -> {foreign[2]}.{foreign[4]}")
                blocks.append("\n".join(block))
            return "\n\n".join(blocks)
        finally:
            connection.close()
