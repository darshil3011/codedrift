"""Write CodeDrift tool-priority rules into CLAUDE.md."""

import re
from pathlib import Path

_START = "<!-- codedrift:skill:start -->"
_END = "<!-- codedrift:skill:end -->"

_SKILL_BODY = """\
# CodeDrift — Scope-Aware Code Intelligence

## Overview

CodeDrift indexes your codebase into a SQLite+FTS5 database and exposes four
MCP tools that replace expensive Glob/Grep/Read chains with targeted, ranked
lookups. Use CodeDrift tools **before** native file-read tools.

## Tool priority (use in this order)

0. `codedrift_memory <question>` — BEFORE EVERYTHING. Check if this task was
   solved before. If a match is returned, use that context set directly and
   skip steps 1–2 entirely.

1. `codedrift_search <keywords>` — FIRST CHOICE. FTS5 fuzzy search across all
   symbol names, signatures, file paths, and call-site context lines.
   Use instead of Grep or Glob.

2. `codedrift_resolve <symbol>` — Full context for a symbol: source code,
   every caller, every importer, related tests, git history.
   Use instead of reading full files.

3. `codedrift_overview` — Project structural map (modules, entry points, test
   summary). Use when you have no idea where to start.

4. `codedrift_read <file>` — Smart file read: full content on first access,
   unified diff on re-reads. Use instead of the native Read tool.

## Rules

- ALWAYS call `codedrift_memory` first, before any other tool.
- ALWAYS try `codedrift_search` before Grep or Glob.
- ALWAYS try `codedrift_resolve` before reading full files.
- After editing files, run `codedrift update` to refresh the index.
- After a `codedrift_search`, pick the most relevant symbol names and call
  `codedrift_resolve` on each one — do NOT read the full file first.

## MCP server registration

```bash
claude mcp add --scope local codedrift -- codedrift mcp
```
"""

_SKILL_CONTENT = f"{_START}\n{_SKILL_BODY}{_END}\n"

_BLOCK_RE = re.compile(re.escape(_START) + r".*?" + re.escape(_END) + r"\n?", re.DOTALL)


def generate_skill_file(output_dir: str) -> tuple[Path, str]:
    """Install or refresh CodeDrift's rules in CLAUDE.md.

    The rules are wrapped in `<!-- codedrift:skill:start/end -->` markers so a
    stale block from an older version of this function can be found and
    replaced in place, rather than silently skipped or duplicated.

    Returns (path, status) where status is "created", "updated", or "unchanged".
    """
    out = Path(output_dir) / "CLAUDE.md"
    existing = out.read_text() if out.exists() else ""

    match = _BLOCK_RE.search(existing)
    if match is None:
        separator = "\n\n---\n\n" if existing.strip() else ""
        out.write_text(existing + separator + _SKILL_CONTENT)
        return out, "created"

    if match.group(0).strip() == _SKILL_CONTENT.strip():
        return out, "unchanged"

    updated = existing[: match.start()] + _SKILL_CONTENT + existing[match.end():]
    out.write_text(updated)
    return out, "updated"
