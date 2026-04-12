"""Indexer — walks the project, parses files, populates the SQLite index."""

import hashlib
import os
import time
from pathlib import Path
from typing import Optional

from .db import CodeDriftDB
from .git_utils import get_last_commit, is_git_repo
from .languages import get_adapter

_DEFAULT_IGNORE = {
    ".git", "node_modules", "__pycache__", "venv", ".venv", "env",
    ".env", ".codecodedrift", "dist", "build", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "target", ".idea", ".vscode",
}

_MAX_FILE_BYTES = 1_000_000  # 1 MB — skip very large files


def _load_driftignore(project_dir: str) -> set[str]:
    ignore_file = Path(project_dir) / ".driftignore"
    if not ignore_file.exists():
        return set()
    lines = ignore_file.read_text().splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _should_ignore(path: Path, ignore_dirs: set[str]) -> bool:
    for part in path.parts:
        if part in ignore_dirs:
            return True
    return False


def index_project(
    project_dir: str,
    db: CodeDriftDB,
    incremental: bool = False,
    quiet: bool = False,
) -> dict:
    """
    Walk project_dir, parse source files, populate db.

    Returns stats dict: {files_indexed, files_skipped, symbols, elapsed}.
    """
    project_path = Path(project_dir).resolve()
    ignore_dirs = _DEFAULT_IGNORE | _load_driftignore(project_dir)
    git = is_git_repo(project_dir)

    files_indexed = 0
    files_skipped = 0
    total_symbols = 0
    t0 = time.time()

    # Collect all indexable files
    for root, dirs, filenames in os.walk(project_path):
        # Prune ignored directories in-place
        dirs[:] = [
            d for d in dirs
            if d not in ignore_dirs and not d.startswith(".")
        ]
        for filename in filenames:
            abs_path = Path(root) / filename
            rel_path = str(abs_path.relative_to(project_path))

            adapter = get_adapter(filename)
            if adapter is None:
                continue

            if abs_path.stat().st_size > _MAX_FILE_BYTES:
                files_skipped += 1
                continue

            try:
                source = abs_path.read_bytes()
            except OSError:
                files_skipped += 1
                continue

            content_hash = _content_hash(source)

            if incremental and not db.is_stale(rel_path, content_hash):
                files_skipped += 1
                continue

            try:
                source_lines = source.decode("utf-8", errors="replace").splitlines()
                # JS/TS adapter has a parse_file that uses the correct grammar
                if hasattr(adapter, "parse_file"):
                    tree = adapter.parse_file(source, rel_path)
                else:
                    tree = adapter.parse(source)

                symbols = adapter.extract_symbols(tree, source_lines, rel_path)
                calls = adapter.extract_calls(tree, source_lines, rel_path)
                imports = adapter.extract_imports(tree, source_lines, rel_path)
            except Exception:
                files_skipped += 1
                continue

            db.upsert_file(
                filepath=rel_path,
                content_hash=content_hash,
                language=adapter.language_name,
                line_count=len(source_lines),
                symbols=symbols,
                calls=calls,
                imports=imports,
            )

            if git:
                commit_hash, last_modified = get_last_commit(rel_path, project_dir)
                if commit_hash:
                    db.upsert_git_info(rel_path, last_modified, commit_hash)

            total_symbols += len(symbols)
            files_indexed += 1

    # Remove files from index that no longer exist on disk
    for indexed_file in db.list_files():
        if not (project_path / indexed_file).exists():
            db.remove_file(indexed_file)

    elapsed = time.time() - t0
    return {
        "files_indexed": files_indexed,
        "files_skipped": files_skipped,
        "symbols": total_symbols,
        "elapsed": elapsed,
    }
