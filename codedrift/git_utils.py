"""Git utilities — log, blame, hook installation."""

import subprocess
from pathlib import Path
from typing import Optional


def _run(cmd: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_last_commit(filepath: str, project_dir: str) -> tuple[str, str]:
    """Return (commit_hash, author_date) for the last commit touching filepath."""
    out = _run(
        ["git", "log", "-1", "--format=%H %ai", "--", filepath],
        cwd=project_dir,
    )
    if not out:
        return "", ""
    parts = out.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def get_changed_files(project_dir: str) -> list[str]:
    """Return files changed since HEAD (staged + unstaged + untracked)."""
    out = _run(["git", "diff", "--name-only", "HEAD"], cwd=project_dir)
    return [f for f in out.splitlines() if f]


def is_git_repo(project_dir: str) -> bool:
    out = _run(["git", "rev-parse", "--git-dir"], cwd=project_dir)
    return bool(out)


def install_post_commit_hook(project_dir: str) -> Path:
    git_dir = _run(["git", "rev-parse", "--git-dir"], cwd=project_dir)
    if not git_dir:
        raise RuntimeError(f"{project_dir} is not a git repository")
    hook_path = Path(project_dir) / git_dir / "hooks" / "post-commit"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("#!/bin/sh\ncodedrift update --quiet\n")
    hook_path.chmod(0o755)
    return hook_path
