"""Write CodeDrift tool-priority rules into CLAUDE.md."""

from pathlib import Path

_SKILL_CONTENT = """\
# CodeDrift — Scope-Aware Code Intelligence

## Overview

CodeDrift indexes your codebase into a SQLite+FTS5 database and exposes four
MCP tools that replace expensive Glob/Grep/Read chains with targeted, ranked
lookups. Use CodeDrift tools **before** native file-read tools.

## Tool priority (use in this order)

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


def generate_skill_file(output_dir: str) -> Path:
    """Append CodeDrift rules to CLAUDE.md (creates it if absent)."""
    out = Path(output_dir) / "CLAUDE.md"
    existing = out.read_text() if out.exists() else ""
    if "codedrift_search" in existing:
        return out  # already installed
    separator = "\n\n---\n\n" if existing.strip() else ""
    out.write_text(existing + separator + _SKILL_CONTENT)
    return out
