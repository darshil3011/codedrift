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


def _find_project_root(start: str = ".") -> Path | None:
    """Walk up from `start` until we find .codecodedrift/index.db."""
    p = Path(start).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / _DRIFT_DIR / _DB_NAME).exists():
            return candidate
    return None


def _find_repo_root(start: str = ".") -> Path | None:
    """Walk up from `start` until we find a `.git` entry (dir or worktree file)."""
    p = Path(start).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _resolve_existing_root(path: str | None) -> Path:
    """Resolve which project's index to use.

    An explicit --path always wins. Otherwise search upward from the current
    directory for an already-initialized project, so running a command from a
    subdirectory finds the real index instead of silently operating on (or
    creating) an unrelated one there. Fails loudly if nothing is found —
    never falls back to creating a stray index.
    """
    if path is not None:
        return Path(path).resolve()
    root = _find_project_root()
    if root is None:
        click.echo("No .codecodedrift/index.db found. Run: codedrift init", err=True)
        sys.exit(1)
    return root


def _resolve_index_root(path: str | None) -> Path:
    """Resolve where a fresh or refreshed index should live.

    An explicit --path always wins. Otherwise: reuse an already-initialized
    ancestor if one exists (so `init`/`update` re-run from a subdirectory
    target the same index rather than fragmenting it); else use the nearest
    git repo root, so the index defaults to the project root instead of
    wherever the command happened to be run from; else fall back to cwd.
    """
    if path is not None:
        return Path(path).resolve()
    existing = _find_project_root()
    if existing is not None:
        return existing
    repo_root = _find_repo_root()
    if repo_root is not None:
        return repo_root
    return Path(".").resolve()


def _get_db(project_dir: str, create: bool = False) -> CodeDriftDB:
    db_path = Path(project_dir) / _DRIFT_DIR / _DB_NAME
    if not create and not db_path.exists():
        click.echo("No .codecodedrift/index.db found. Run: codedrift init", err=True)
        sys.exit(1)
    return CodeDriftDB(db_path).connect()


@click.group()
def main():
    """CodeDrift — eliminate token waste in AI coding agents."""
    pass


# ── init ─────────────────────────────────────────────────────────────────────

@main.command()
@click.option(
    "--path",
    default=None,
    help="Project root to index (auto-detected via an existing index or the "
    "nearest git repo root if omitted).",
)
@click.option("--quiet", is_flag=True)
def init(path: str | None, quiet: bool):
    """Index a project (full scan, < 3 seconds for 500 files)."""
    cwd = Path(".").resolve()
    resolved = _resolve_index_root(path)
    project_dir = str(resolved)
    if path is None and resolved != cwd and not quiet:
        click.echo(f"Project root detected: {project_dir}")
    db = _get_db(project_dir, create=True)
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
@click.option(
    "--path",
    default=None,
    help="Project root (auto-detected via an existing index or the nearest "
    "git repo root if omitted).",
)
@click.option("--quiet", is_flag=True)
def update(path: str | None, quiet: bool):
    """Re-index only changed files (incremental, < 0.5s typical)."""
    project_dir = str(_resolve_index_root(path))
    db = _get_db(project_dir, create=True)
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
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.option("--limit", default=15, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def search_cmd(query, path, limit, as_json):
    """Search codebase by keywords (FTS5). PRIMARY COMMAND."""
    q = " ".join(query)
    project_dir = str(_resolve_existing_root(path))
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
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.option("--json", "as_json", is_flag=True)
def resolve_cmd(symbol, path, as_json):
    """Full context for a symbol: source, callers, tests, git."""
    project_dir = str(_resolve_existing_root(path))
    db = _get_db(project_dir)
    try:
        result = resolve(db, symbol, project_dir)
        click.echo(formatter.format_resolve(result, as_json=as_json))
    finally:
        db.close()


main.add_command(resolve_cmd, name="resolve")


# ── overview ──────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.option("--json", "as_json", is_flag=True)
def overview_cmd(path, as_json):
    """Project structural map: modules, files, entry points."""
    project_dir = str(_resolve_existing_root(path))
    db = _get_db(project_dir)
    try:
        text = overview(db, project_dir)
        click.echo(formatter.format_overview(text, as_json=as_json))
    finally:
        db.close()


main.add_command(overview_cmd, name="overview")


# ── status ────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.option("--json", "as_json", is_flag=True)
def status(path, as_json):
    """Show index statistics."""
    project_dir = str(_resolve_existing_root(path))
    db_path = Path(project_dir) / _DRIFT_DIR / _DB_NAME
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
    """Write or refresh CodeDrift tool-priority rules in CLAUDE.md."""
    from .skill import generate_skill_file
    out, status = generate_skill_file(path)
    messages = {
        "created": f"Rules written to: {out}",
        "updated": f"Rules were out of date — refreshed in place: {out}",
        "unchanged": f"Rules already up to date: {out}",
    }
    click.echo(messages[status])


# ── redact ───────────────────────────────────────────────────────────────────

@main.group()
def redact():
    """PII redaction: prevent secrets from reaching the LLM."""
    pass


@redact.command("enable")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def redact_enable(path):
    """Enable PII redaction for this project."""
    from .redactor import load_config, save_config
    project_dir = str(_resolve_existing_root(path))
    cfg = load_config(project_dir)
    cfg.enabled = True
    save_config(project_dir, cfg)
    click.echo("PII redaction enabled.")


@redact.command("disable")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def redact_disable(path):
    """Disable PII redaction."""
    from .redactor import load_config, save_config
    project_dir = str(_resolve_existing_root(path))
    cfg = load_config(project_dir)
    cfg.enabled = False
    save_config(project_dir, cfg)
    click.echo("PII redaction disabled.")


@redact.command("status")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def redact_status(path):
    """Show current redaction configuration."""
    from .redactor import load_config
    project_dir = str(_resolve_existing_root(path))
    cfg = load_config(project_dir)
    click.echo(f"Enabled:         {cfg.enabled}")
    click.echo(f"Entity types:    {', '.join(cfg.entity_types)}")
    click.echo(f"Allow patterns:  {', '.join(cfg.allow_patterns) or '(none)'}")
    click.echo(f"Env passthrough: {', '.join(cfg.env_passthrough_keys)}")


@redact.command("allow")
@click.argument("pattern")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def redact_allow(pattern, path):
    """Add a regex pattern to the allow-list (never redacted)."""
    from .redactor import load_config, save_config
    project_dir = str(_resolve_existing_root(path))
    cfg = load_config(project_dir)
    if pattern not in cfg.allow_patterns:
        cfg.allow_patterns.append(pattern)
        save_config(project_dir, cfg)
    click.echo(f"Allow-listed: {pattern}")


@redact.command("ignore")
@click.argument("entity_type")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def redact_ignore(entity_type, path):
    """Stop redacting an entity type (e.g. private_person)."""
    from .redactor import load_config, save_config
    project_dir = str(_resolve_existing_root(path))
    cfg = load_config(project_dir)
    if entity_type in cfg.entity_types:
        cfg.entity_types.remove(entity_type)
        save_config(project_dir, cfg)
    click.echo(f"Ignored: {entity_type}")


@redact.command("watch")
@click.argument("entity_type")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def redact_watch(entity_type, path):
    """Add an entity type back to detection."""
    from .redactor import load_config, save_config
    project_dir = str(_resolve_existing_root(path))
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
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.option("--threshold", default=0.40, show_default=True, type=float)
@click.option("--verbose", "-v", is_flag=True, help="Show all sessions with their scores.")
def memory_recall(query, path, threshold, verbose):
    """Find the closest past session for a given query."""
    from .memory import SessionMemory

    q = " ".join(query)
    project_dir = str(_resolve_existing_root(path))
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
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def memory_list(path):
    """Show all stored sessions."""
    import datetime
    import json as _json

    project_dir = str(_resolve_existing_root(path))
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
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.confirmation_option(prompt="Clear all stored session memory?")
def memory_clear(path):
    """Delete all stored session memory."""
    project_dir = str(_resolve_existing_root(path))
    db = _get_db(project_dir)
    try:
        db.clear_session_memory()
    finally:
        db.close()
    click.echo("Session memory cleared.")


# ── dashboard ─────────────────────────────────────────────────────────────────

@main.command("dashboard")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8421, show_default=True)
@click.option("--no-browser", is_flag=True, help="Don't open the browser automatically.")
def dashboard_cmd(path: str | None, host: str, port: int, no_browser: bool):
    """Start the analytics dashboard (API + UI). Auto-detects project root."""
    try:
        import uvicorn
        from .api import app, init_api
    except ImportError:
        click.echo("Dashboard support requires: pip install codedrift[dashboard]", err=True)
        sys.exit(1)
    root = Path(path).resolve() if path else _find_project_root()
    if not root:
        click.echo("No .codecodedrift/index.db found. Run: codedrift init", err=True)
        sys.exit(1)
    init_api(root / _DRIFT_DIR / _DB_NAME)
    url = f"http://{host}:{port}"
    click.echo(f"CodeDrift Dashboard → {url}")
    if not no_browser:
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port)


# ── api (API-only server) ─────────────────────────────────────────────────────

@main.command("api")
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8421, show_default=True)
def api_cmd(path: str | None, host: str, port: int):
    """Start the analytics API server only (no UI, no browser). Auto-detects project root."""
    try:
        import uvicorn
        from .api import app, init_api
    except ImportError:
        click.echo("Dashboard support requires: pip install codedrift[dashboard]", err=True)
        sys.exit(1)
    root = Path(path).resolve() if path else _find_project_root()
    if not root:
        click.echo("No .codecodedrift/index.db found. Run: codedrift init", err=True)
        sys.exit(1)
    init_api(root / _DRIFT_DIR / _DB_NAME)
    click.echo(f"CodeDrift API → http://{host}:{port}/api")
    uvicorn.run(app, host=host, port=port)


# ── mcp ───────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def mcp(path):
    """Start the MCP server for Claude Code / agent integration."""
    try:
        from .mcp_server import run_mcp_server
    except ImportError:
        click.echo("MCP support requires: pip install codedrift[mcp]", err=True)
        sys.exit(1)
    project_dir = str(_resolve_existing_root(path))
    run_mcp_server(project_dir)


# ── doctor ────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--path", default=None, help="Project root (auto-detected if omitted).")
def doctor(path):
    """Diagnose whether this project is actually wired up for Claude Code.

    Checks the index, MCP registration in ~/.claude.json, CLAUDE.md's
    tool-priority rules, and the git auto-update hook — independently of
    whether the index itself looks healthy, since none of those are implied
    by `codedrift init` having been run.
    """
    from .doctor import run_doctor

    if path is not None:
        project_dir = str(Path(path).resolve())
    else:
        project_dir = str(_find_project_root() or _find_repo_root() or Path(".").resolve())

    click.echo(f"══ CodeDrift doctor: {project_dir} ══\n")
    all_ok = True
    for name, ok, detail in run_doctor(project_dir):
        marker = "ok" if ok else "FAIL"
        click.echo(f"[{marker:>4}] {name}: {detail}")
        all_ok = all_ok and ok

    click.echo()
    if all_ok:
        click.echo("Everything looks wired up correctly.")
    else:
        click.echo("Some checks failed — see the commands above.")
        sys.exit(1)
