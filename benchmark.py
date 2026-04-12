#!/usr/bin/env python3
"""
Analyse Claude Code session logs to measure token usage per query.

Shows new tokens added each turn, which tools were used, and cumulative
context growth — so you can compare MCP-assisted vs native tool queries.

Usage:
    python benchmark.py                     # most recent session
    python benchmark.py --session <id>      # specific session id
    python benchmark.py --project <path>    # sessions for a project dir
    python benchmark.py --list              # list available sessions
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
CODEDRIFT_TOOLS = {"codedrift_search", "codedrift_resolve", "codedrift_overview", "codedrift_read"}
NATIVE_TOOLS    = {"Read", "Grep", "Glob", "Bash", "Write", "Edit"}


def projects_dir_for(project_path: str) -> Path:
    """Convert an absolute path to its ~/.claude/projects/<slug> folder."""
    slug = project_path.replace("/", "-").lstrip("-")
    return PROJECTS_DIR / slug


def list_sessions(project_path: str | None = None):
    """Print available sessions sorted by modification time (newest first)."""
    dirs = [projects_dir_for(project_path)] if project_path else list(PROJECTS_DIR.iterdir())
    rows = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.jsonl"):
            rows.append((f.stat().st_mtime, f))
    rows.sort(reverse=True)
    print(f"{'Session ID':<40}  {'Project':<35}  {'Modified'}")
    print("─" * 95)
    for mtime, f in rows[:30]:
        from datetime import datetime
        ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{f.stem:<40}  {f.parent.name:<35}  {ts}")


def load_session(session_file: Path) -> list[dict]:
    entries = []
    with open(session_file) as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def parse_turns(entries: list[dict]) -> list[dict]:
    """
    Group entries into (user_message, assistant_response) turn pairs.
    Each turn captures: user text, tools used, token usage.
    """
    turns = []
    current_user = None

    for entry in entries:
        t = entry.get("type")

        if t == "user":
            content = entry.get("message", {}).get("content", [])
            if isinstance(content, str):
                current_user = content[:120].replace("\n", " ")
            elif isinstance(content, list):
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                tool_results = [c for c in content if c.get("type") == "tool_result"]
                if texts:
                    current_user = " ".join(texts)[:120].replace("\n", " ")
                elif tool_results:
                    current_user = f"[tool result ×{len(tool_results)}]"

        elif t == "assistant":
            msg     = entry.get("message", {})
            usage   = msg.get("usage", {})
            content = msg.get("content", [])

            if not usage:
                continue

            tools_used = [
                c.get("name", c.get("type", "?"))
                for c in content
                if c.get("type") == "tool_use"
            ]

            new_tokens  = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            cache_read  = usage.get("cache_read_input_tokens", 0)
            total_ctx   = new_tokens + cache_read
            out_tokens  = usage.get("output_tokens", 0)

            turns.append({
                "user":       current_user or "(no user message)",
                "tools":      tools_used,
                "new_tokens": new_tokens,
                "cache_read": cache_read,
                "total_ctx":  total_ctx,
                "out_tokens": out_tokens,
            })
            current_user = None

    return turns


def tag_tools(tools: list[str]) -> str:
    if not tools:
        return "—"
    tagged = []
    for t in tools:
        if t in CODEDRIFT_TOOLS:
            tagged.append(f"[drift]{t}[/drift]")
        else:
            tagged.append(t)
    return ", ".join(tagged)


def print_report(turns: list[dict], session_id: str):
    if not turns:
        print("No assistant turns found in this session.")
        return

    # ANSI colours
    CYAN  = "\033[96m"
    GREEN = "\033[92m"
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    print(f"\n{BOLD}Session: {session_id}{RESET}\n")
    print(f"{'#':>3}  {'New tokens':>11}  {'Cache read':>11}  {'Total ctx':>10}  {'Out':>6}  Tools / Query")
    print("─" * 110)

    total_new = total_cache = total_ctx = total_out = 0

    for i, turn in enumerate(turns, 1):
        tools_str = ", ".join(turn["tools"]) if turn["tools"] else "—"
        query_preview = turn["user"][:55]

        # Highlight codedrift tools
        display_tools = []
        has_drift = False
        for t in turn["tools"]:
            if t in CODEDRIFT_TOOLS:
                display_tools.append(f"{GREEN}{t}{RESET}")
                has_drift = True
            elif t in NATIVE_TOOLS:
                display_tools.append(f"{CYAN}{t}{RESET}")
            else:
                display_tools.append(t)
        tools_display = ", ".join(display_tools) if display_tools else "—"

        print(
            f"{i:>3}  {turn['new_tokens']:>11,}  {turn['cache_read']:>11,}  "
            f"{turn['total_ctx']:>10,}  {turn['out_tokens']:>6,}  "
            f"{tools_display}  |  {query_preview}"
        )

        total_new   += turn["new_tokens"]
        total_cache += turn["cache_read"]
        total_ctx   += turn["total_ctx"]
        total_out   += turn["out_tokens"]

    print("─" * 110)
    print(f"{'TOTAL':>3}  {total_new:>11,}  {total_cache:>11,}  {total_ctx:>10,}  {total_out:>6,}")

    drift_turns  = [t for t in turns if any(x in CODEDRIFT_TOOLS for x in t["tools"])]
    native_turns = [t for t in turns if any(x in NATIVE_TOOLS    for x in t["tools"]) and
                                         not any(x in CODEDRIFT_TOOLS for x in t["tools"])]

    if drift_turns or native_turns:
        print()
        if drift_turns:
            avg_new = sum(t["new_tokens"] for t in drift_turns) / len(drift_turns)
            print(f"{GREEN}CodeDrift turns:{RESET}  {len(drift_turns):>3}  avg new tokens: {avg_new:,.0f}")
        if native_turns:
            avg_new = sum(t["new_tokens"] for t in native_turns) / len(native_turns)
            print(f"{CYAN}Native tool turns:{RESET}{len(native_turns):>3}  avg new tokens: {avg_new:,.0f}")

    print()
    print("Legend:")
    print(f"  New tokens  = input_tokens + cache_creation  (tokens Claude processed fresh this turn)")
    print(f"  Cache read  = tokens replayed from prompt cache (cheap but still in context window)")
    print(f"  Total ctx   = full context size Claude saw")


def find_session_file(session_id: str) -> Path | None:
    for d in PROJECTS_DIR.iterdir():
        if not d.is_dir():
            continue
        f = d / f"{session_id}.jsonl"
        if f.exists():
            return f
    return None


def latest_session(project_path: str | None = None) -> Path | None:
    dirs = [projects_dir_for(project_path)] if project_path else list(PROJECTS_DIR.iterdir())
    best = None
    best_mtime = 0
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.jsonl"):
            m = f.stat().st_mtime
            if m > best_mtime:
                best_mtime = m
                best = f
    return best


def main():
    parser = argparse.ArgumentParser(description="Analyse Claude Code session token usage")
    parser.add_argument("--session",  help="Session ID to analyse")
    parser.add_argument("--project",  help="Project directory (e.g. /home/darshil/Desktop/codedrift)")
    parser.add_argument("--list",     action="store_true", help="List available sessions")
    args = parser.parse_args()

    if args.list:
        list_sessions(args.project)
        return

    if args.session:
        session_file = find_session_file(args.session)
        if not session_file:
            sys.exit(f"Session {args.session} not found.")
    else:
        project = args.project
        session_file = latest_session(project)
        if not session_file:
            sys.exit("No sessions found.")
        print(f"Using most recent session: {session_file.stem}")

    entries = load_session(session_file)
    turns   = parse_turns(entries)
    print_report(turns, session_file.stem)


if __name__ == "__main__":
    main()
