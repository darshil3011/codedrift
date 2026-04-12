"""Output formatting for search, resolve, and overview results."""

import json
from typing import List

from .search import SearchResult
from .resolver import ResolveResult


# ── Search ────────────────────────────────────────────────────────────────────

def format_search(results: List[SearchResult], query: str, as_json: bool = False) -> str:
    if as_json:
        return json.dumps([_result_to_dict(r) for r in results], indent=2)

    if not results:
        return f'No results for "{query}"'

    header = f'══ CodeDrift search: "{query}" ({len(results)} results) ══\n'
    # Group by file
    by_file: dict[str, list[SearchResult]] = {}
    for r in results:
        by_file.setdefault(r.file, []).append(r)

    lines = [header]
    for filepath, items in by_file.items():
        lines.append(filepath)
        for r in items:
            sig = r.signature.strip() if r.signature else r.name
            lines.append(f"  {sig:<60}  :{r.start_line}  {r.kind}")
            if r.call_context:
                lines.append(f"    └─ line {r.call_line}: {r.call_context.strip()}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _result_to_dict(r: SearchResult) -> dict:
    return {
        "name": r.name,
        "kind": r.kind,
        "file": r.file,
        "start_line": r.start_line,
        "end_line": r.end_line,
        "signature": r.signature,
        "language": r.language,
        "call_context": r.call_context,
        "call_line": r.call_line,
    }


# ── Resolve ───────────────────────────────────────────────────────────────────

def format_resolve(result: ResolveResult, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_resolve_to_dict(result), indent=2)

    if result.kind == "unknown":
        return f'Symbol "{result.name}" not found in index.'

    lines = [f"══ {result.name} ({result.kind}) ══"]
    lines.append(f"File:      {result.file}:{result.start_line}-{result.end_line}")
    lines.append(f"Language:  {result.language}")

    if result.git_commit_hash:
        lines.append(f"Last edit: {result.git_last_modified}  [{result.git_commit_hash[:8]}]")

    lines.append("")
    lines.append("── Source ──")
    lines.append(result.source_code or "(source unavailable)")
    lines.append("")

    if result.callers:
        lines.append(f"── Called by ({len(result.callers)}) ──")
        for c in result.callers[:10]:
            lines.append(f"  {c.file}:{c.line}  {c.context.strip()}")
        if len(result.callers) > 10:
            lines.append(f"  … and {len(result.callers) - 10} more")
        lines.append("")

    if result.tests:
        lines.append(f"── Tests ({len(result.tests)}) ──")
        for t in result.tests[:5]:
            lines.append(f"  {t.file}:{t.line}  [{t.enclosing_test}]  {t.context.strip()}")
        lines.append("")

    if result.importers:
        lines.append(f"── Imported by ({len(result.importers)}) ──")
        for f in result.importers[:8]:
            lines.append(f"  {f}")
        lines.append("")

    if result.candidates:
        lines.append(f"── Multiple definitions found ({len(result.candidates)}) ──")
        lines.append("  Showing first. Use 'codedrift resolve <file>:<symbol>' to pick one.")
        for c in result.candidates:
            lines.append(f"  {c['file']}:{c['start_line']}  {c['name']}  ({c['kind']})")
        lines.append("")

    return "\n".join(lines).rstrip()


def _resolve_to_dict(r: ResolveResult) -> dict:
    return {
        "name": r.name,
        "kind": r.kind,
        "file": r.file,
        "start_line": r.start_line,
        "end_line": r.end_line,
        "signature": r.signature,
        "language": r.language,
        "source_code": r.source_code,
        "callers": [{"file": c.file, "line": c.line, "context": c.context} for c in r.callers],
        "tests": [{"file": t.file, "line": t.line, "context": t.context, "test": t.enclosing_test} for t in r.tests],
        "importers": r.importers,
        "git_last_modified": r.git_last_modified,
        "git_commit_hash": r.git_commit_hash,
    }


# ── Overview ──────────────────────────────────────────────────────────────────

def format_overview(text: str, as_json: bool = False) -> str:
    if as_json:
        return json.dumps({"overview": text})
    return f"══ Project Overview ══\n\n{text}"


# ── Status ────────────────────────────────────────────────────────────────────

def format_status(stats: dict, db_path: str, as_json: bool = False) -> str:
    if as_json:
        return json.dumps({"db": db_path, **stats})
    langs = ", ".join(f"{k}({v})" for k, v in stats.get("languages", {}).items())
    return (
        f"Index: {db_path}\n"
        f"Files:   {stats['files']}\n"
        f"Symbols: {stats['symbols']}\n"
        f"Languages: {langs or 'none'}"
    )
