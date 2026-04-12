"""FTS5 search engine — primary entry point for agent queries."""

from dataclasses import dataclass, field
from typing import List

from .db import CodeDriftDB


@dataclass
class SearchResult:
    name: str
    kind: str
    file: str
    start_line: int
    end_line: int
    signature: str
    language: str
    rank: float
    call_context: str = ""      # matching call-site line (if found via calls_fts)
    call_line: int = 0


def _build_fts_query(query: str) -> str:
    """
    Convert a natural-language query into an FTS5 MATCH expression.

    Numbers are quoted (exact); words get a prefix wildcard.
    Example: "auth token 401" → 'auth* OR token* OR "401"'
    """
    words = query.strip().split()
    if not words:
        return ""
    terms = []
    for w in words:
        # strip punctuation that would break FTS5 syntax
        clean = w.strip(".,;:!?\"'()[]{}").lower()
        if not clean:
            continue
        if clean.isdigit():
            terms.append(f'"{clean}"')
        else:
            terms.append(f"{clean}*")
    return " OR ".join(terms)


def search(db: CodeDriftDB, query: str, limit: int = 15) -> List[SearchResult]:
    """
    Fuzzy search across all symbols and call sites using FTS5.

    Merges symbol matches (names, signatures, file paths) with call-site
    matches (catches string literals, error codes, etc.).
    """
    fts_query = _build_fts_query(query)
    if not fts_query:
        return []

    results: dict[tuple, SearchResult] = {}  # keyed by (file, name, start_line)

    # ── symbol search ────────────────────────────────────────────────────────
    try:
        sym_rows = db.search_symbols(fts_query, limit)
    except Exception:
        sym_rows = []

    for row in sym_rows:
        key = (row["file"], row["name"], row["start_line"])
        results[key] = SearchResult(
            name=row["name"],
            kind=row["kind"],
            file=row["file"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            signature=row["signature"] or "",
            language=row["language"],
            rank=row["rank"],
        )

    # ── call-site search ─────────────────────────────────────────────────────
    try:
        call_rows = db.search_calls(fts_query, limit)
    except Exception:
        call_rows = []

    for row in call_rows:
        sym_name = row["symbol_name"]
        # Try to find the definition of this symbol to attach the call context
        sym_defs = db.get_symbol(sym_name)
        if sym_defs:
            defn = sym_defs[0]
            key = (defn["file"], defn["name"], defn["start_line"])
            if key not in results:
                results[key] = SearchResult(
                    name=defn["name"],
                    kind=defn["kind"],
                    file=defn["file"],
                    start_line=defn["start_line"],
                    end_line=defn["end_line"],
                    signature=defn["signature"] or "",
                    language=defn["language"],
                    rank=row["rank"],
                    call_context=row["context"] or "",
                    call_line=row["line"],
                )
            elif not results[key].call_context:
                results[key].call_context = row["context"] or ""
                results[key].call_line = row["line"]
        else:
            # No definition found — still surface the call site
            key = (row["caller_file"], sym_name, row["line"])
            if key not in results:
                results[key] = SearchResult(
                    name=sym_name,
                    kind="call",
                    file=row["caller_file"],
                    start_line=row["line"],
                    end_line=row["line"],
                    signature=row["context"] or "",
                    language="",
                    rank=row["rank"],
                    call_context=row["context"] or "",
                    call_line=row["line"],
                )

    # Sort by BM25 rank (lower = better in SQLite BM25)
    sorted_results = sorted(results.values(), key=lambda r: r.rank)
    return sorted_results[:limit]
