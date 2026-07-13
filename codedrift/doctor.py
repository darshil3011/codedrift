"""codedrift doctor — verify a project is actually wired up for Claude Code.

Having a fresh index on disk says nothing about whether Claude Code will ever
call CodeDrift's MCP tools: that also requires `claude mcp add` to have been
run for this exact project path, and CLAUDE.md to carry the current
tool-priority rules. This module checks all of that directly rather than
assuming it.
"""

import json
import time
from pathlib import Path

from .git_utils import _run, is_git_repo

_DRIFT_DIR = ".codecodedrift"
_DB_NAME = "index.db"


def _claude_config_path() -> Path:
    return Path.home() / ".claude.json"


def check_index(project_dir: str) -> tuple[bool, str]:
    db_path = Path(project_dir) / _DRIFT_DIR / _DB_NAME
    if not db_path.exists():
        return False, "no index found — run: codedrift init"
    age_hours = (time.time() - db_path.stat().st_mtime) / 3600
    return True, f"index present at {db_path} (last written {age_hours:.1f}h ago)"


def check_mcp_registration(project_dir: str) -> tuple[bool, str]:
    cfg_path = _claude_config_path()
    if not cfg_path.exists():
        return False, f"{cfg_path} not found — is Claude Code installed?"
    try:
        data = json.loads(cfg_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"could not read {cfg_path}: {exc}"

    root = str(Path(project_dir).resolve())
    entry = data.get("projects", {}).get(root, {}).get("mcpServers", {}).get("codedrift")
    if entry is None:
        return False, (
            f"codedrift is NOT registered as an MCP server for {root}. Run:\n"
            f"    claude mcp add --scope local codedrift -- codedrift mcp"
        )

    args = entry.get("args", [])
    if "mcp" not in args:
        return False, (
            f"codedrift is registered for {root} but missing the 'mcp' subcommand "
            f"(args={args!r}) — Claude will just print CLI help instead of starting "
            f"the server. Re-run:\n"
            f"    claude mcp add --scope local codedrift -- codedrift mcp"
        )
    return True, f"registered correctly for {root}"


def check_skill_file(project_dir: str) -> tuple[bool, str]:
    claude_md = Path(project_dir) / "CLAUDE.md"
    if not claude_md.exists():
        return False, "no CLAUDE.md found — run: codedrift install-skill"

    from .skill import _SKILL_CONTENT

    text = claude_md.read_text(errors="replace")
    if _SKILL_CONTENT.strip() in text:
        return True, "CLAUDE.md has current tool-priority rules"
    if "codedrift_search" in text:
        return False, (
            "CLAUDE.md has CodeDrift rules but they look outdated or hand-edited — "
            "run: codedrift install-skill"
        )
    return False, "no CodeDrift rules in CLAUDE.md — run: codedrift install-skill"


def check_git_hook(project_dir: str) -> tuple[bool, str]:
    if not is_git_repo(project_dir):
        return True, "not a git repo — auto-update hook not applicable"
    git_dir = _run(["git", "rev-parse", "--git-dir"], project_dir)
    if not git_dir:
        return False, "could not determine the git directory"
    hook_path = Path(project_dir) / git_dir / "hooks" / "post-commit"
    if not hook_path.exists() or "codedrift update" not in hook_path.read_text(errors="replace"):
        return False, "no auto-update hook — run: codedrift install-hook"
    return True, f"auto-update hook installed at {hook_path}"


def run_doctor(project_dir: str) -> list[tuple[str, bool, str]]:
    """Run every check and return (name, passed, detail) triples."""
    return [
        ("Index", *check_index(project_dir)),
        ("MCP registration", *check_mcp_registration(project_dir)),
        ("CLAUDE.md rules", *check_skill_file(project_dir)),
        ("Git auto-update hook", *check_git_hook(project_dir)),
    ]
