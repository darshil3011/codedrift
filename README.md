# CodeDrift

Your coding agent spends 90% of its tokens finding code, not writing it.

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
already saw.

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
```

---

## Requirements

- Python 3.10+
- `git` on PATH
- Claude Code CLI

## Supported languages

Python, JavaScript, TypeScript, Go, Rust
