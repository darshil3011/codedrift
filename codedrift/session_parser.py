"""Parse Claude Code JSONL session logs to extract task and context."""

import json
from pathlib import Path
from typing import Optional


def _project_log_dir(project_dir: str) -> Optional[Path]:
    """
    Map a project directory to its Claude Code log folder.

    Claude Code stores logs at:
      ~/.claude/projects/<slug>/
    where <slug> is the project path with '/' replaced by '-'.
    """
    slug = str(Path(project_dir).resolve()).replace("/", "-")
    log_dir = Path.home() / ".claude" / "projects" / slug
    return log_dir if log_dir.is_dir() else None


def find_latest_session(project_dir: str) -> Optional[Path]:
    """Return the most-recently modified JSONL file for this project, or None."""
    log_dir = _project_log_dir(project_dir)
    if not log_dir:
        return None
    files = sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def parse_session(jsonl_path: str) -> dict:
    """
    Extract task description and accessed context from a JSONL session file.

    Returns:
        task_text:       str   — first human-authored user message
        files_read:      list  — file paths from Read tool calls
        symbols_resolved: list — symbol names from codedrift_resolve calls
        session_id:      str | None
    """
    task_text = ""
    files_read: list[str] = []
    symbols_resolved: list[str] = []
    session_id: Optional[str] = None
    first_user_found = False

    for raw in Path(jsonl_path).read_text(errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Capture session_id from any record that has it
        if not session_id:
            session_id = rec.get("sessionId")

        rec_type = rec.get("type")

        # First genuine user message (not a tool result) → task description
        if rec_type == "user" and not rec.get("toolUseResult") and not first_user_found:
            content = rec.get("message", {}).get("content", "")
            if isinstance(content, str):
                task_text = content.strip()
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        task_text = block.get("text", "").strip()
                        break
            if task_text:
                first_user_found = True

        # Assistant messages: scan tool_use blocks
        if rec_type == "assistant":
            content = rec.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name", "")
                inp = block.get("input", {})

                if tool_name == "Read":
                    fp = inp.get("file_path", "")
                    if fp:
                        files_read.append(fp)

                elif tool_name == "codedrift_resolve":
                    sym = inp.get("symbol", "")
                    if sym:
                        symbols_resolved.append(sym)

                elif tool_name == "codedrift_read":
                    fp = inp.get("file", "")
                    if fp:
                        files_read.append(fp)

    return {
        "task_text": task_text,
        "files_read": list(dict.fromkeys(files_read)),       # deduplicated, order preserved
        "symbols_resolved": list(dict.fromkeys(symbols_resolved)),
        "session_id": session_id,
    }
