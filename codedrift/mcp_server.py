"""MCP server — exposes CodeDrift tools to Claude Code and other agents."""

from pathlib import Path

from .db import CodeDriftDB
from .differ import DiffLedger
from . import formatter
from .search import search
from .resolver import resolve
from .overview import overview
from .savings import TokenSavingsLedger, file_tokens
from .memory import SessionMemory

_DRIFT_DIR = ".codecodedrift"
_DB_NAME = "index.db"

_ledger = DiffLedger()
_savings = TokenSavingsLedger()
_memory: "SessionMemory | None" = None  # initialised lazily per project_dir


def _get_memory(db) -> "SessionMemory":
    global _memory
    if _memory is None:
        _memory = SessionMemory(db)
    else:
        _memory.db = db
    return _memory


def _get_db(project_dir: str) -> CodeDriftDB:
    db_path = Path(project_dir) / _DRIFT_DIR / _DB_NAME
    if not db_path.exists():
        raise RuntimeError(
            f"No CodeDrift index found at {db_path}. Run: codedrift init --path {project_dir}"
        )
    return CodeDriftDB(db_path).connect()


def run_mcp_server(project_dir: str):
    """Start the MCP server (blocking). Requires mcp package."""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp import types
    except ImportError as exc:
        raise RuntimeError("Install MCP support: pip install codedrift[mcp]") from exc

    server = Server("codedrift")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="codedrift_search",
                description=(
                    "Search the codebase by keywords using FTS5 full-text search. "
                    "Use BEFORE Grep or Glob. Matches symbol names, signatures, "
                    "file paths, and call-site context lines. "
                    "Input: natural language query (e.g. 'auth token 401 unauthorized')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language search terms"},
                        "limit": {"type": "integer", "default": 15},
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="codedrift_resolve",
                description=(
                    "Full context for a specific symbol: source code, every caller, "
                    "every importer, related tests, and git history. "
                    "Use INSTEAD of reading full files. "
                    "Input: exact or partial symbol name from codedrift_search results."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Symbol name to resolve"},
                    },
                    "required": ["symbol"],
                },
            ),
            types.Tool(
                name="codedrift_overview",
                description=(
                    "Project structural map: modules, file counts, symbol counts, "
                    "entry points, and test summary (~300 tokens). "
                    "Use when you have no idea where to start."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            types.Tool(
                name="codedrift_read",
                description=(
                    "Smart file read. Returns full content on first access; "
                    "returns only the unified diff on re-reads within the same session. "
                    "Use INSTEAD of the native Read tool."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "File path (relative to project root)"},
                    },
                    "required": ["file"],
                },
            ),
            types.Tool(
                name="codedrift_memory",
                description=(
                    "Check if a similar task was completed in a past session. "
                    "Call this FIRST, before any search or resolve. "
                    "If a match is found, use the returned context set directly — "
                    "skip search and resolve entirely. "
                    "Input: the user's current question or task description."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Current task or question"},
                        "threshold": {
                            "type": "number",
                            "default": 0.40,
                            "description": "Minimum similarity score (0-1) to accept a match",
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        db = _get_db(project_dir)
        try:
            if name == "codedrift_search":
                query = arguments["query"]
                limit = int(arguments.get("limit", 15))
                results = search(db, query, limit=limit)
                text = formatter.format_search(results, query)
                unique_files = {r.file for r in results}
                naive = sum(file_tokens(str(Path(project_dir) / f)) for f in unique_files)
                saved = _savings.record("codedrift_search", text, naive)
                text += _savings.format_footer(saved)

            elif name == "codedrift_resolve":
                symbol = arguments["symbol"]
                result = resolve(db, symbol, project_dir)
                text = formatter.format_resolve(result)
                naive = file_tokens(str(Path(project_dir) / result.file)) if result.file else 0
                saved = _savings.record("codedrift_resolve", text, naive)
                text += _savings.format_footer(saved)

            elif name == "codedrift_overview":
                text = formatter.format_overview(overview(db, project_dir))
                naive = sum(file_tokens(str(Path(project_dir) / f)) for f in db.list_files())
                saved = _savings.record("codedrift_overview", text, naive)
                text += _savings.format_footer(saved)

            elif name == "codedrift_read":
                file_path = arguments["file"]
                full_path = str(Path(project_dir) / file_path)
                _ledger.next_turn()
                text = _ledger.read_file(full_path)
                naive = file_tokens(full_path)
                saved = _savings.record("codedrift_read", text, naive)
                text += _savings.format_footer(saved)

            elif name == "codedrift_memory":
                query = arguments["query"]
                threshold = float(arguments.get("threshold", 0.40))
                try:
                    mem = _get_memory(db)
                    match = mem.recall(query, threshold=threshold)
                except RuntimeError as exc:
                    match = None
                    text = str(exc)
                else:
                    if match:
                        lines = [
                            f"[Memory match — similarity {match['similarity']:.2f}]",
                            f"Past task: {match['task_text']}",
                            "",
                            f"Files ({len(match['context_files'])}):",
                        ]
                        for f in match["context_files"]:
                            lines.append(f"  {f}")
                        if match["context_symbols"]:
                            lines.append(f"\nSymbols ({len(match['context_symbols'])}):")
                            for s in match["context_symbols"]:
                                lines.append(f"  {s}")
                        text = "\n".join(lines)
                    else:
                        text = "No memory match found. Proceed with codedrift_search."

            else:
                text = f"Unknown tool: {name}"
        finally:
            db.close()

        return [types.TextContent(type="text", text=text)]

    import asyncio

    async def _serve():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_serve())
