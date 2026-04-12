"""Click-based CLI entry point for CodeDrift."""

import os
import sys
from pathlib import Path

import click

from .db import CodeDriftDB
from . import formatter
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
