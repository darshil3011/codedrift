"""SQLite + FTS5 database layer for CodeDrift."""

import sqlite3
import time
from pathlib import Path
from typing import Any, List, Optional


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    signature TEXT,
    language TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    symbol_name TEXT NOT NULL,
    caller_file TEXT NOT NULL,
    line INTEGER NOT NULL,
    context TEXT,
    full_name TEXT
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    symbol_name TEXT NOT NULL,
    file TEXT NOT NULL,
    import_line TEXT
);

CREATE TABLE IF NOT EXISTS file_meta (
    file TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    last_indexed REAL,
    language TEXT,
    line_count INTEGER
);

CREATE TABLE IF NOT EXISTS git_info (
    file TEXT PRIMARY KEY,
    last_modified TEXT,
    last_commit_hash TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name,
    kind,
    file,
    signature,
    content=symbols,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, kind, file, signature)
    VALUES (new.id, new.name, new.kind, new.file, new.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, kind, file, signature)
    VALUES ('delete', old.id, old.name, old.kind, old.file, old.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, kind, file, signature)
    VALUES ('delete', old.id, old.name, old.kind, old.file, old.signature);
    INSERT INTO symbols_fts(rowid, name, kind, file, signature)
    VALUES (new.id, new.name, new.kind, new.file, new.signature);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS calls_fts USING fts5(
    symbol_name,
    caller_file,
    context,
    content=calls,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS calls_ai AFTER INSERT ON calls BEGIN
    INSERT INTO calls_fts(rowid, symbol_name, caller_file, context)
    VALUES (new.id, new.symbol_name, new.caller_file, new.context);
END;

CREATE TRIGGER IF NOT EXISTS calls_ad AFTER DELETE ON calls BEGIN
    INSERT INTO calls_fts(calls_fts, rowid, symbol_name, caller_file, context)
    VALUES ('delete', old.id, old.symbol_name, old.caller_file, old.context);
END;

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file);
CREATE INDEX IF NOT EXISTS idx_calls_name   ON calls(symbol_name);
CREATE INDEX IF NOT EXISTS idx_imports_name ON imports(symbol_name);
"""


class CodeDriftDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()
        return self

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    # ── schema ───────────────────────────────────────────────────────────────

    def _apply_schema(self):
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── low-level query ───────────────────────────────────────────────────────

    def execute(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        cur = self._conn.execute(sql, params)
        return cur.fetchall()

    # ── hash / staleness ─────────────────────────────────────────────────────

    def is_stale(self, filepath: str, content_hash: str) -> bool:
        rows = self.execute(
            "SELECT content_hash FROM file_meta WHERE file = ?", (filepath,)
        )
        if not rows:
            return True
        return rows[0]["content_hash"] != content_hash

    # ── per-file atomic upsert ────────────────────────────────────────────────

    def upsert_file(
        self,
        filepath: str,
        content_hash: str,
        language: str,
        line_count: int,
        symbols,
        calls,
        imports,
    ):
        conn = self._conn
        with conn:
            # Remove stale data for this file
            conn.execute("DELETE FROM symbols WHERE file = ?", (filepath,))
            conn.execute("DELETE FROM calls WHERE caller_file = ?", (filepath,))
            conn.execute("DELETE FROM imports WHERE file = ?", (filepath,))

            # Insert new symbols
            conn.executemany(
                "INSERT INTO symbols (name, kind, file, start_line, end_line, signature, language) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (s.name, s.kind, s.file, s.start_line, s.end_line, s.signature, s.language)
                    for s in symbols
                ],
            )

            # Insert call sites
            conn.executemany(
                "INSERT INTO calls (symbol_name, caller_file, line, context, full_name) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (c.symbol_name, c.caller_file, c.line, c.context, c.full_name)
                    for c in calls
                ],
            )

            # Insert imports
            conn.executemany(
                "INSERT INTO imports (symbol_name, file, import_line) VALUES (?, ?, ?)",
                [(i.symbol_name, i.file, i.import_line) for i in imports],
            )

            # Update file metadata
            conn.execute(
                "INSERT OR REPLACE INTO file_meta (file, content_hash, last_indexed, language, line_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (filepath, content_hash, time.time(), language, line_count),
            )

    def remove_file(self, filepath: str):
        with self._conn:
            self._conn.execute("DELETE FROM symbols WHERE file = ?", (filepath,))
            self._conn.execute("DELETE FROM calls WHERE caller_file = ?", (filepath,))
            self._conn.execute("DELETE FROM imports WHERE file = ?", (filepath,))
            self._conn.execute("DELETE FROM file_meta WHERE file = ?", (filepath,))
            self._conn.execute("DELETE FROM git_info WHERE file = ?", (filepath,))

    def upsert_git_info(self, filepath: str, last_modified: str, last_commit_hash: str):
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO git_info (file, last_modified, last_commit_hash) "
                "VALUES (?, ?, ?)",
                (filepath, last_modified, last_commit_hash),
            )

    # ── FTS5 search ──────────────────────────────────────────────────────────

    def search_symbols(self, fts_query: str, limit: int = 15) -> List[sqlite3.Row]:
        return self.execute(
            """
            SELECT s.id, s.name, s.kind, s.file, s.start_line, s.end_line,
                   s.signature, s.language, bm25(symbols_fts) AS rank
            FROM symbols_fts
            JOIN symbols s ON s.id = symbols_fts.rowid
            WHERE symbols_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        )

    def search_calls(self, fts_query: str, limit: int = 15) -> List[sqlite3.Row]:
        return self.execute(
            """
            SELECT c.id, c.symbol_name, c.caller_file, c.line, c.context,
                   c.full_name, bm25(calls_fts) AS rank
            FROM calls_fts
            JOIN calls c ON c.id = calls_fts.rowid
            WHERE calls_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        )

    # ── resolve ───────────────────────────────────────────────────────────────

    def get_symbol(self, name: str) -> List[sqlite3.Row]:
        return self.execute(
            "SELECT * FROM symbols WHERE name = ? ORDER BY file, start_line", (name,)
        )

    def get_symbol_ilike(self, name: str) -> List[sqlite3.Row]:
        return self.execute(
            "SELECT * FROM symbols WHERE name LIKE ? ORDER BY file, start_line",
            (f"%{name}%",),
        )

    def get_callers(self, symbol_name: str) -> List[sqlite3.Row]:
        return self.execute(
            "SELECT * FROM calls WHERE symbol_name = ? ORDER BY caller_file, line",
            (symbol_name,),
        )

    def get_importers(self, symbol_name: str) -> List[sqlite3.Row]:
        return self.execute(
            "SELECT * FROM imports WHERE symbol_name = ? ORDER BY file",
            (symbol_name,),
        )

    def get_git_info(self, filepath: str) -> Optional[sqlite3.Row]:
        rows = self.execute("SELECT * FROM git_info WHERE file = ?", (filepath,))
        return rows[0] if rows else None

    # ── stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        (file_count,) = self._conn.execute("SELECT COUNT(*) FROM file_meta").fetchone()
        (symbol_count,) = self._conn.execute("SELECT COUNT(*) FROM symbols").fetchone()
        lang_rows = self._conn.execute(
            "SELECT language, COUNT(*) as n FROM file_meta GROUP BY language ORDER BY n DESC"
        ).fetchall()
        return {
            "files": file_count,
            "symbols": symbol_count,
            "languages": {r["language"]: r["n"] for r in lang_rows},
        }

    def module_summary(self) -> List[sqlite3.Row]:
        """Per-directory file and symbol counts for overview."""
        return self.execute(
            """
            SELECT
                COALESCE(
                    CASE WHEN instr(s.file, '/') > 0
                         THEN substr(s.file, 1, instr(s.file, '/') - 1)
                         ELSE '.'
                    END, '.'
                ) AS module,
                COUNT(DISTINCT s.file) AS file_count,
                COUNT(*) AS symbol_count
            FROM symbols s
            GROUP BY module
            ORDER BY file_count DESC
            """
        )

    def list_files(self) -> List[str]:
        rows = self.execute("SELECT file FROM file_meta ORDER BY file")
        return [r["file"] for r in rows]
