"""Click-based CLI entry point for CodeDrift."""

import os
import sys
from pathlib import Path

import click

from .db import CodeDriftDB
from . import formatter
from . import analytics
from .indexer import index_project
from .search import search
from .resolver import resolve
from .overview import overview
from .differ import DiffLedger
from .git_utils import install_post_commit_hook

_DRIFT_DIR = ".codecodedrift"
_DB_NAME = "index.db"

_ledger = DiffLedger()


def _get_db(project_dir: str) -> CodeDriftDB:
    db_path = Path(project_dir) / _DRIFT_DIR / _DB_NAME
    return CodeDriftDB(db_path).connect()


@click.group()
def main():
    """CodeDrift — eliminate token waste in AI coding agents."""
    pass


# ── init ─────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=".", help="Project root to index.")
@click.option("--quiet", is_flag=True)
def init(path: str, quiet: bool):
    """Index a project (full scan, < 3 seconds for 500 files)."""
    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        stats = index_project(project_dir, db, incremental=False, quiet=quiet)
        analytics.log_index_event(db, incremental=False, stats=stats)
        if not quiet:
            click.echo(
                f"Indexed {stats['files_indexed']} files, "
                f"{stats['symbols']} symbols in {stats['elapsed']:.2f}s  "
                f"({stats['files_skipped']} skipped)"
            )
    finally:
        db.close()


# ── update ────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=".", help="Project root.")
@click.option("--quiet", is_flag=True)
def update(path: str, quiet: bool):
    """Re-index only changed files (incremental, < 0.5s typical)."""
    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        stats = index_project(project_dir, db, incremental=True, quiet=quiet)
        analytics.log_index_event(db, incremental=True, stats=stats)
        if not quiet:
            click.echo(
                f"Updated: {stats['files_indexed']} changed, "
                f"{stats['files_skipped']} unchanged, "
                f"{stats['elapsed']:.2f}s"
            )
    finally:
        db.close()


# ── search ────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--path", default=".", help="Project root.")
@click.option("--limit", default=15, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def search_cmd(query, path, limit, as_json):
    """Search codebase by keywords (FTS5). PRIMARY COMMAND."""
    q = " ".join(query)
    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        results = search(db, q, limit=limit)
        click.echo(formatter.format_search(results, q, as_json=as_json))
    finally:
        db.close()


main.add_command(search_cmd, name="search")


# ── resolve ───────────────────────────────────────────────────────────────────

@main.command()
@click.argument("symbol")
@click.option("--path", default=".", help="Project root.")
@click.option("--json", "as_json", is_flag=True)
def resolve_cmd(symbol, path, as_json):
    """Full context for a symbol: source, callers, tests, git."""
    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        result = resolve(db, symbol, project_dir)
        click.echo(formatter.format_resolve(result, as_json=as_json))
    finally:
        db.close()


main.add_command(resolve_cmd, name="resolve")


# ── overview ──────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=".", help="Project root.")
@click.option("--json", "as_json", is_flag=True)
def overview_cmd(path, as_json):
    """Project structural map: modules, files, entry points."""
    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        text = overview(db, project_dir)
        click.echo(formatter.format_overview(text, as_json=as_json))
    finally:
        db.close()


main.add_command(overview_cmd, name="overview")


# ── status ────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=".", help="Project root.")
@click.option("--json", "as_json", is_flag=True)
def status(path, as_json):
    """Show index statistics."""
    project_dir = str(Path(path).resolve())
    db_path = Path(project_dir) / _DRIFT_DIR / _DB_NAME
    if not db_path.exists():
        click.echo("No index found. Run: codedrift init")
        sys.exit(1)
    db = _get_db(project_dir)
    try:
        stats = db.stats()
        click.echo(formatter.format_status(stats, str(db_path), as_json=as_json))
    finally:
        db.close()


# ── read (diff ledger) ────────────────────────────────────────────────────────

@main.command()
@click.argument("file")
@click.option("--path", default=".", help="Project root.")
def read(file, path):
    """Smart file read: full on first read, diff on re-reads."""
    project_dir = str(Path(path).resolve())
    full_path = str(Path(project_dir) / file)
    _ledger.next_turn()
    click.echo(_ledger.read_file(full_path))


# ── install-hook ──────────────────────────────────────────────────────────────

@main.command("install-hook")
@click.option("--path", default=".", help="Git repo root.")
def install_hook(path):
    """Install git post-commit hook to auto-update index."""
    project_dir = str(Path(path).resolve())
    try:
        hook_path = install_post_commit_hook(project_dir)
        click.echo(f"Hook installed: {hook_path}")
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── install-skill ─────────────────────────────────────────────────────────────

@main.command("install-skill")
@click.option("--path", default=".", help="Project root (CLAUDE.md is written here).")
def install_skill(path):
    """Append CodeDrift tool-priority rules to CLAUDE.md."""
    from .skill import generate_skill_file
    out = generate_skill_file(path)
    click.echo(f"Rules written to: {out}")


# ── redact ───────────────────────────────────────────────────────────────────

@main.group()
def redact():
    """PII redaction: prevent secrets from reaching the LLM."""
    pass


@redact.command("enable")
@click.option("--path", default=".", help="Project root.")
def redact_enable(path):
    """Enable PII redaction for this project."""
    from .redactor import load_config, save_config
    project_dir = str(Path(path).resolve())
    cfg = load_config(project_dir)
    cfg.enabled = True
    save_config(project_dir, cfg)
    click.echo("PII redaction enabled.")


@redact.command("disable")
@click.option("--path", default=".", help="Project root.")
def redact_disable(path):
    """Disable PII redaction."""
    from .redactor import load_config, save_config
    project_dir = str(Path(path).resolve())
    cfg = load_config(project_dir)
    cfg.enabled = False
    save_config(project_dir, cfg)
    click.echo("PII redaction disabled.")


@redact.command("status")
@click.option("--path", default=".", help="Project root.")
def redact_status(path):
    """Show current redaction configuration."""
    from .redactor import load_config
    project_dir = str(Path(path).resolve())
    cfg = load_config(project_dir)
    click.echo(f"Enabled:         {cfg.enabled}")
    click.echo(f"Entity types:    {', '.join(cfg.entity_types)}")
    click.echo(f"Allow patterns:  {', '.join(cfg.allow_patterns) or '(none)'}")
    click.echo(f"Env passthrough: {', '.join(cfg.env_passthrough_keys)}")


@redact.command("allow")
@click.argument("pattern")
@click.option("--path", default=".", help="Project root.")
def redact_allow(pattern, path):
    """Add a regex pattern to the allow-list (never redacted)."""
    from .redactor import load_config, save_config
    project_dir = str(Path(path).resolve())
    cfg = load_config(project_dir)
    if pattern not in cfg.allow_patterns:
        cfg.allow_patterns.append(pattern)
        save_config(project_dir, cfg)
    click.echo(f"Allow-listed: {pattern}")


@redact.command("ignore")
@click.argument("entity_type")
@click.option("--path", default=".", help="Project root.")
def redact_ignore(entity_type, path):
    """Stop redacting an entity type (e.g. private_person)."""
    from .redactor import load_config, save_config
    project_dir = str(Path(path).resolve())
    cfg = load_config(project_dir)
    if entity_type in cfg.entity_types:
        cfg.entity_types.remove(entity_type)
        save_config(project_dir, cfg)
    click.echo(f"Ignored: {entity_type}")


@redact.command("watch")
@click.argument("entity_type")
@click.option("--path", default=".", help="Project root.")
def redact_watch(entity_type, path):
    """Add an entity type back to detection."""
    from .redactor import load_config, save_config
    project_dir = str(Path(path).resolve())
    cfg = load_config(project_dir)
    if entity_type not in cfg.entity_types:
        cfg.entity_types.append(entity_type)
        save_config(project_dir, cfg)
    click.echo(f"Watching: {entity_type}")


# ── memory ───────────────────────────────────────────────────────────────────

@main.group()
def memory():
    """Session memory: store and recall proven context sets across sessions."""
    pass


@memory.command("record")
@click.option("--path", default=".", help="Project root.")
@click.option("--session", default=None, help="Path to a specific JSONL file (defaults to latest).")
@click.option("--outcome", default="success", show_default=True, help="success or error.")
def memory_record(path, session, outcome):
    """Parse the last session log and store its context in memory."""
    from .memory import SessionMemory
    from .session_parser import find_latest_session, parse_session

    project_dir = str(Path(path).resolve())
    jsonl_path = session or find_latest_session(project_dir)
    if not jsonl_path:
        click.echo("No session log found for this project.", err=True)
        sys.exit(1)

    parsed = parse_session(str(jsonl_path))
    if not parsed["task_text"]:
        click.echo("Could not extract a task description from the session log.", err=True)
        sys.exit(1)

    db = _get_db(project_dir)
    try:
        mem = SessionMemory(db)
        row_id = mem.record(
            task_text=parsed["task_text"],
            context_files=parsed["files_read"],
            context_symbols=parsed["symbols_resolved"],
            outcome=outcome,
            session_id=parsed["session_id"],
        )
    finally:
        db.close()

    task_preview = parsed["task_text"][:80]
    click.echo(f'Recorded session #{row_id}: "{task_preview}"')
    click.echo(f"  files: {len(parsed['files_read'])}  symbols: {len(parsed['symbols_resolved'])}")


@memory.command("recall")
@click.argument("query", nargs=-1, required=True)
@click.option("--path", default=".", help="Project root.")
@click.option("--threshold", default=0.40, show_default=True, type=float)
@click.option("--verbose", "-v", is_flag=True, help="Show all sessions with their scores.")
def memory_recall(query, path, threshold, verbose):
    """Find the closest past session for a given query."""
    from .memory import SessionMemory

    q = " ".join(query)
    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        mem = SessionMemory(db)
        if verbose:
            candidates = mem.recall_all(q)
        else:
            match = mem.recall(q, threshold=threshold)
    finally:
        db.close()

    if verbose:
        if not candidates:
            click.echo("No sessions stored.")
            return
        click.echo(f"All sessions ranked by similarity to: \"{q}\"")
        click.echo(f"{'Score':>6}  {'Task'}")
        click.echo("-" * 60)
        for c in candidates:
            marker = " *" if c["similarity"] >= threshold else ""
            click.echo(f"  {c['similarity']:.4f}{marker}  {c['task_text'][:70]}")
        return

    if not match:
        click.echo(f'No match above {threshold} for: "{q}"')
        click.echo(f'Tip: run with --verbose to see actual scores.')
        return

    click.echo(f"Match (similarity={match['similarity']:.2f}):")
    click.echo(f"  Task: {match['task_text']}")
    click.echo(f"  Files ({len(match['context_files'])}):")
    for f in match["context_files"]:
        click.echo(f"    {f}")
    if match["context_symbols"]:
        click.echo(f"  Symbols ({len(match['context_symbols'])}):")
        for s in match["context_symbols"]:
            click.echo(f"    {s}")


@memory.command("list")
@click.option("--path", default=".", help="Project root.")
def memory_list(path):
    """Show all stored sessions."""
    import datetime
    import json as _json

    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        rows = db.list_session_memory()
    finally:
        db.close()

    if not rows:
        click.echo("No sessions stored.")
        return

    for row in rows:
        ts = datetime.datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M")
        n_files = len(_json.loads(row["context_files"]))
        n_syms = len(_json.loads(row["context_symbols"]))
        click.echo(
            f"#{row['id']:>3}  {ts}  [{row['outcome']}]  "
            f"files={n_files}  syms={n_syms}  "
            f"{row['task_text'][:70]}"
        )


@memory.command("clear")
@click.option("--path", default=".", help="Project root.")
@click.confirmation_option(prompt="Clear all stored session memory?")
def memory_clear(path):
    """Delete all stored session memory."""
    project_dir = str(Path(path).resolve())
    db = _get_db(project_dir)
    try:
        db.clear_session_memory()
    finally:
        db.close()
    click.echo("Session memory cleared.")


# ── serve ─────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=".", help="Project root.")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8421, show_default=True)
def serve(path: str, host: str, port: int):
    """Start the analytics dashboard API server."""
    try:
        import uvicorn
        from .api import app, init_api
    except ImportError:
        click.echo("Dashboard support requires: pip install codedrift[dashboard]", err=True)
        sys.exit(1)
    project_dir = str(Path(path).resolve())
    db_path = Path(project_dir) / _DRIFT_DIR / _DB_NAME
    if not db_path.exists():
        click.echo("No index found. Run: codedrift init", err=True)
        sys.exit(1)
    init_api(db_path)
    click.echo(f"Dashboard API → http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


# ── mcp ───────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=".", help="Project root.")
def mcp(path):
    """Start the MCP server for Claude Code / agent integration."""
    try:
        from .mcp_server import run_mcp_server
    except ImportError:
        click.echo("MCP support requires: pip install codedrift[mcp]", err=True)
        sys.exit(1)
    project_dir = str(Path(path).resolve())
    run_mcp_server(project_dir)
