"""Small SQLite adapter for local development and contract tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


class SQLiteDatabase:
    def __init__(self, path: str | Path = "healsync.local.db") -> None:
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")

    def initialize(self, schema_path: str | Path | None = None) -> None:
        schema = Path(schema_path) if schema_path else Path(__file__).with_name("schema.sql")
        self.connection.executescript(schema.read_text(encoding="utf-8"))
        self.connection.commit()

    def execute(self, sql: str, parameters: Iterable[object] = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, tuple(parameters))

    def executescript(self, sql: str) -> None:
        self.connection.executescript(sql)
        self.connection.commit()

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteDatabase":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.connection.rollback()
        self.close()
