"""Symbol resolution engine — deep context for a specific symbol."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .db import CodeDriftDB
from .languages import get_adapter


@dataclass
class CallerInfo:
    file: str
    line: int
    context: str
    enclosing_test: str = ""  # test function name if caller is in a test


@dataclass
class ResolveResult:
    name: str
    kind: str
    file: str
    start_line: int
    end_line: int
    signature: str
    language: str
    source_code: str
    callers: List[CallerInfo] = field(default_factory=list)
    importers: List[str] = field(default_factory=list)  # files that import this symbol
    tests: List[CallerInfo] = field(default_factory=list)
    git_last_modified: str = ""
    git_commit_hash: str = ""
    candidates: List[dict] = field(default_factory=list)  # set when ambiguous


def _read_lines(project_dir: str, filepath: str, start: int, end: int) -> str:
    """Read lines [start, end] (1-based) from a file."""
    full_path = Path(project_dir) / filepath
    if not full_path.exists():
        return ""
    try:
        lines = full_path.read_text(errors="replace").splitlines()
        return "\n".join(lines[start - 1: end])
    except OSError:
        return ""


def _find_enclosing_test(db: CodeDriftDB, caller_file: str, line: int) -> str:
    """Return the enclosing test function name for a call site, if any."""
    adapter = get_adapter(caller_file)
    if adapter is None or not adapter.is_test_file(caller_file):
        return ""
    # Find a symbol in caller_file where start_line <= line <= end_line
    # and kind == "function" and name starts with "test"
    rows = db.execute(
        """
        SELECT name FROM symbols
        WHERE file = ? AND start_line <= ? AND end_line >= ?
          AND (name LIKE 'test_%' OR name LIKE 'Test%')
        ORDER BY start_line DESC
        LIMIT 1
        """,
        (caller_file, line, line),
    )
    return rows[0]["name"] if rows else ""


def resolve(db: CodeDriftDB, symbol_name: str, project_dir: str) -> ResolveResult:
    """
    Full context for a specific symbol.

    Fallback chain:
    1. Exact match
    2. Case-insensitive match
    3. Partial (LIKE %name%) match → lists candidates
    """
    # ── 1. Exact match ────────────────────────────────────────────────────────
    rows = db.get_symbol(symbol_name)

    # ── 2. Case-insensitive ───────────────────────────────────────────────────
    if not rows:
        rows = db.execute(
            "SELECT * FROM symbols WHERE name LIKE ? ORDER BY file, start_line",
            (symbol_name,),
        )

    # ── 3. Partial match ─────────────────────────────────────────────────────
    if not rows:
        rows = db.get_symbol_ilike(symbol_name)

    if not rows:
        return ResolveResult(
            name=symbol_name, kind="unknown", file="", start_line=0, end_line=0,
            signature="", language="", source_code="",
        )

    # Ambiguous: multiple definitions — return candidates list
    if len(rows) > 1:
        candidates = [
            {"name": r["name"], "kind": r["kind"], "file": r["file"], "start_line": r["start_line"]}
            for r in rows
        ]
        defn = rows[0]  # default to first; caller can filter
    else:
        candidates = []
        defn = rows[0]

    source_code = _read_lines(project_dir, defn["file"], defn["start_line"], defn["end_line"])

    # ── callers ───────────────────────────────────────────────────────────────
    caller_rows = db.get_callers(defn["name"])
    callers: List[CallerInfo] = []
    tests: List[CallerInfo] = []
    for row in caller_rows:
        enc_test = _find_enclosing_test(db, row["caller_file"], row["line"])
        ci = CallerInfo(
            file=row["caller_file"],
            line=row["line"],
            context=row["context"] or "",
            enclosing_test=enc_test,
        )
        if enc_test:
            tests.append(ci)
        else:
            callers.append(ci)

    # ── importers ─────────────────────────────────────────────────────────────
    import_rows = db.get_importers(defn["name"])
    importers = list({r["file"] for r in import_rows})

    # ── git info ──────────────────────────────────────────────────────────────
    git_row = db.get_git_info(defn["file"])
    git_last_modified = git_row["last_modified"] if git_row else ""
    git_commit_hash = git_row["last_commit_hash"] if git_row else ""

    return ResolveResult(
        name=defn["name"],
        kind=defn["kind"],
        file=defn["file"],
        start_line=defn["start_line"],
        end_line=defn["end_line"],
        signature=defn["signature"] or "",
        language=defn["language"],
        source_code=source_code,
        callers=callers,
        importers=importers,
        tests=tests,
        git_last_modified=git_last_modified,
        git_commit_hash=git_commit_hash,
        candidates=candidates,
    )
