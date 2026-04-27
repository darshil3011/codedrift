<div align="center">

<pre>
 ██████╗ ██████╗ ██████╗ ███████╗██████╗ ██████╗ ██╗███████╗████████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██║██╔════╝╚══██╔══╝
██║     ██║   ██║██║  ██║█████╗  ██║  ██║██████╔╝██║█████╗     ██║   
██║     ██║   ██║██║  ██║██╔══╝  ██║  ██║██╔══██╗██║██╔══╝     ██║   
╚██████╗╚██████╔╝██████╔╝███████╗██████╔╝██║  ██║██║██║        ██║   
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝        ╚═╝  
</pre>

**Your coding agent spends 90% of its tokens finding code, not writing it.**  
Reduce token usage by **50x** with CodeDrift.

[![GitHub Stars](https://img.shields.io/github/stars/darshil3011/codedrift?style=for-the-badge&logo=github&color=gold&labelColor=1a1a2e&label=%E2%AD%90%20Star%20this%20repo)](https://github.com/darshil3011/codedrift/stargazers)&nbsp;
[![LinkedIn](https://img.shields.io/badge/LinkedIn-darshil3011-0a66c2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/darshil3011)

<br/>

[![Quick Setup](https://img.shields.io/badge/Quick_Setup-2ea44f?style=flat-square)](#quick-setup)&nbsp;
[![AST Token Reduction](https://img.shields.io/badge/AST_Token_Reduction-0969da?style=flat-square)](#ast-based-token-reduction)&nbsp;
[![Session-aware Reads](https://img.shields.io/badge/Session--aware_Reads-d29922?style=flat-square)](#session-aware-reads--zero-re-read-waste)&nbsp;
[![Cross-session Memory](https://img.shields.io/badge/Cross--session_Memory-8250df?style=flat-square)](#cross-session-memory)&nbsp;
[![PII Redaction](https://img.shields.io/badge/PII_Redaction-cf222e?style=flat-square)](#pii-redaction)

</div>

---

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

## AST-based token reduction

CodeDrift uses [tree-sitter](https://tree-sitter.github.io) to parse your codebase into a structured symbol index — functions, classes, imports, and call sites — rather than storing raw file text. When the agent queries for a symbol, it gets back only the relevant definition and its context, not an entire file.

This means the agent never pays for boilerplate it doesn't need. A 2,000-line module with one relevant function costs the same as a 10-line file — only the symbol travels over the wire.

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

If a past session scores above the similarity threshold (default 0.40), it returns the task description, the files that were read, and the symbols that were resolved — giving the agent a warm start instead of re-discovering context from scratch.

Use `--verbose` (or `-v`) to see all stored sessions ranked by similarity score, regardless of threshold — useful for tuning:

```bash
codedrift memory recall "add authentication middleware" --verbose
```

```bash
codedrift memory list            # show all stored sessions
codedrift memory clear           # wipe memory
```

Memory uses vector embeddings (`all-MiniLM-L6-v2`) stored locally in the project's SQLite index. It requires the optional `memory` extra:

```bash
pip install "codedrift[memory]"
```

---

## PII redaction

CodeDrift can strip sensitive values from file content before it reaches the LLM. It uses [openai/privacy-filter](https://huggingface.co/openai/privacy-filter) — a 1.5B parameter bidirectional token classifier that runs locally via ONNX. No data leaves your machine.

When enabled, `codedrift_read` passes each string literal's source line through the model. If PII is detected, only the string value is replaced in-place — the rest of the file is untouched.

**Before / after example:**

```python
# Before
def send_data():
    token   = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456"
    email   = "john.smith@company.com"
    db_pass = "super$ecret99"
    requests.post("https://api.example.com", headers={"Authorization": token})

# After
def send_data():
    token   = "[REDACTED:SECRET]"
    email   = "[REDACTED:EMAIL]"
    db_pass = "[REDACTED:SECRET]"
    requests.post("https://api.example.com", headers={"Authorization": token})
```

`.env` files are handled separately — all values are redacted line-by-line without running the model, except keys you explicitly allow through.

### Setup

```bash
pip install "codedrift[redact]"
codedrift redact enable
```

The model (~917 MB, ONNX q4) is downloaded from Hugging Face on first use and cached locally.

### What gets redacted

| Entity type | Examples | Redacted as |
|---|---|---|
| `secret` | API keys, passwords, tokens, private keys | `[REDACTED:SECRET]` |
| `private_email` | `john@company.com` | `[REDACTED:EMAIL]` |
| `account_number` | Bank account numbers, card numbers | `[REDACTED:ACCOUNT_NUMBER]` |
| `private_person` | Full names | `[REDACTED:PERSON]` |
| `private_phone` | Phone numbers | `[REDACTED:PHONE]` |
| `private_url` | Personal or authenticated URLs | `[REDACTED:URL]` |
| `private_address` | Street addresses | `[REDACTED:ADDRESS]` |
| `private_date` | Dates of birth, personal dates | `[REDACTED:DATE]` |

By default only `secret`, `private_email`, and `account_number` are active. Enable others with `codedrift redact watch <entity_type>`.

Interpolated strings (`f"..."`, JS template literals) are skipped — they contain variable references, not static values.

### Configuration

Config is stored in `.codecodedrift/redact.json`:

```json
{
  "enabled": true,
  "entity_types": ["secret", "private_email", "account_number"],
  "allow_patterns": ["test@example.com", "localhost"],
  "env_passthrough_keys": ["NODE_ENV", "PORT", "HOST", "DEBUG", "APP_ENV", "LOG_LEVEL"]
}
```

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | Master switch. `false` by default — no overhead until you opt in. |
| `entity_types` | list of strings | Which entity types to redact. Any subset of the 8 types above. |
| `allow_patterns` | list of regex strings | Values matching any pattern are never redacted, even if the model flags them. Useful for test fixtures and known-safe placeholders. |
| `env_passthrough_keys` | list of strings | `.env` keys whose values are passed through unchanged. Defaults cover common non-secret keys. |

### CLI

```bash
codedrift redact enable                   # turn on redaction for this project
codedrift redact disable                  # turn off
codedrift redact status                   # show current config
codedrift redact allow "test@example.com" # never redact this value
codedrift redact ignore private_person    # stop redacting names
codedrift redact watch private_person     # re-enable name redaction
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
