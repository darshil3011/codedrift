# CodeDrift

Your coding agent spends 90% of its tokens finding code, not writing it. Reduce your token usage by 50x with CodeDrift !

<p align="center">
  <img src="assets/comparison.svg" alt="Token usage: without vs with CodeDrift" width="680"/>
</p>

> Numbers are typical for a mid-size Python codebase session. Run `benchmark.py` against your own sessions to measure exactly.


Every prompt triggers the same loop — grep, glob, read a file, realize it's
wrong, read another, try again. A single question burns 60K tokens and 23
tool calls before the real work starts.

CodeDrift replaces that loop. It parses your codebase with
[tree-sitter](https://tree-sitter.github.io), extracts every function, class,
import, and call site, and stores them in a local index with full-text search.
When your agent needs code, it queries the index — and gets back the exact
definition, every caller, related tests, and git history. Within a session, it
tracks what the agent has already seen — re-reads return only the lines that
changed, not the entire file again.

This isn't compression. It's elimination. The agent never reads files it
doesn't need, never greps through irrelevant matches, never re-reads what it
already saw, and never pays full price for a file it edited — re-reads return
only the unified diff against what the agent already has in context.

No LLM involved in indexing — tree-sitter is a deterministic AST parser, so
the index is fast, free to build, and requires zero maintenance.


---

## Quick setup

```bash
# 1. Install
pip install "git+https://github.com/darshil3011/codedrift[mcp]"

# 2. Index your project
cd /path/to/your/project
codedrift init

# 3. Register MCP server with Claude Code
claude mcp add --scope local codedrift -- codedrift mcp

# 4. Write tool-priority rules to CLAUDE.md
codedrift install-skill

# 5. Start a new Claude Code session — done
```

> Add `.codecodedrift/` to your `.gitignore`.

---

## Keep the index fresh

**Auto-update on every git commit (recommended):**

```bash
codedrift install-hook
```

**Or manually after changes:**

```bash
codedrift update
```

---

## MCP tools

| Tool | Replaces | Description |
|---|---|---|
| `codedrift_search` | Grep, Glob | FTS5 search across symbol names, signatures, file paths, call sites |
| `codedrift_resolve` | Read (full file) | Source code + callers + importers + tests + git history for one symbol |
| `codedrift_overview` | Reading multiple files | Module map, entry points, test summary (~300 tokens) |
| `codedrift_read` | Read | Full file on first access; unified diff on re-reads |

---

## Session-aware reads — zero re-read waste

`codedrift_read` tracks every file the agent reads during a session. The first access returns the full file; every subsequent access returns either a one-line "unchanged" notice or a unified diff of only the lines that changed. The design treats the LLM's context window as the cache — since the full file is already there from the first read, re-reads only need to transmit the delta.

---

## Cross-session memory

CodeDrift can remember which files and symbols were useful for a given task and surface them again when a similar task comes up in a future session.

After finishing a session, record it:

```bash
codedrift memory record          # parses the latest Claude Code session log
codedrift memory record --outcome error  # mark it as a failed attempt
```

Before starting work on something similar, check for a past match:

```bash
codedrift memory recall "add authentication middleware"
```

If a past session scores above the similarity threshold (default 0.80), it returns the task description, the files that were read, and the symbols that were resolved — giving the agent a warm start instead of re-discovering context from scratch.

```bash
codedrift memory list            # show all stored sessions
codedrift memory clear           # wipe memory
```

Memory uses vector embeddings (`all-MiniLM-L6-v2`) stored locally in the project's SQLite index. It requires the optional `memory` extra:

```bash
pip install "codedrift[memory]"
```

---

## Measure token savings

```bash
python benchmark.py                          # analyse most recent session
python benchmark.py --list                   # list all sessions
python benchmark.py --project /path/to/repo  # sessions for a specific project
```

Reads Claude Code session logs directly — no API key required.

---

## CLI reference

```bash
codedrift init            # full index scan
codedrift update          # incremental re-index (changed files only)
codedrift search <query>  # FTS5 search from terminal
codedrift resolve <sym>   # full symbol context from terminal
codedrift overview        # project structural map
codedrift status          # index stats (files, symbols, languages)
codedrift install-hook    # git post-commit hook for auto-update
codedrift install-skill   # append tool-priority rules to CLAUDE.md
codedrift mcp             # start MCP server (used by claude mcp add)
codedrift memory record   # store last session's context in memory
codedrift memory recall   # find closest past session for a query
codedrift memory list     # show all stored sessions
codedrift memory clear    # wipe session memory
```

---

## Requirements

- Python 3.10+
- `git` on PATH
- Claude Code CLI

## Supported languages

Python, JavaScript, TypeScript, Go, Rust
