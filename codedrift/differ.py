"""Diff ledger — session-scoped smart file reads."""

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _SeenFile:
    content_hash: str
    turn: int
    content: str


class DiffLedger:
    """
    Tracks files read during a session.

    First read → full content.
    Re-read (unchanged) → one-line notice.
    Re-read (changed) → unified diff only.
    """

    def __init__(self):
        self._seen: dict[str, _SeenFile] = {}
        self._turn: int = 0

    def next_turn(self):
        """Advance the turn counter (call once per agent message)."""
        self._turn += 1

    def read_file(self, filepath: str) -> str:
        """Return file content or diff, depending on session state."""
        path = Path(filepath)
        if not path.exists():
            return f"[ERROR: {filepath} not found]"

        try:
            content = path.read_text(errors="replace")
        except OSError as exc:
            return f"[ERROR: cannot read {filepath}: {exc}]"

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        if filepath not in self._seen:
            self._seen[filepath] = _SeenFile(content_hash, self._turn, content)
            return content

        prev = self._seen[filepath]

        if content_hash == prev.content_hash:
            return f"[{filepath}: unchanged since turn {prev.turn}]"

        diff_lines = list(difflib.unified_diff(
            prev.content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"{filepath} (turn {prev.turn})",
            tofile=f"{filepath} (current)",
            n=3,
        ))
        self._seen[filepath] = _SeenFile(content_hash, self._turn, content)
        return f"[{filepath}: changed since turn {prev.turn}]\n{''.join(diff_lines)}"

    def reset(self):
        self._seen.clear()
        self._turn = 0
