"""Analytics event logging and query layer."""

import json
import time
from typing import Any, Optional

from .db import CodeDriftDB


# ── write side ────────────────────────────────────────────────────────────────

def log_event(
    db: CodeDriftDB,
    event_type: str,
    duration_ms: Optional[float],
    metadata: dict[str, Any],
) -> int:
    return db.insert_analytics_event(
        event_type=event_type,
        timestamp=time.time(),
        duration_ms=duration_ms,
        metadata_json=json.dumps(metadata),
    )


def log_index_event(db: CodeDriftDB, incremental: bool, stats: dict) -> int:
    return log_event(
        db,
        event_type="update" if incremental else "init",
        duration_ms=stats.get("elapsed", 0) * 1000,
        metadata={
            "files_indexed": stats.get("files_indexed", 0),
            "files_skipped": stats.get("files_skipped", 0),
            "symbols": stats.get("symbols", 0),
            "incremental": incremental,
        },
    )


def log_tool_call(
    db: CodeDriftDB,
    tool_name: str,
    duration_ms: float,
    result_count: int,
    output_tokens: int,
    naive_tokens: int,
    tokens_saved: int,
    query: Optional[str] = None,
    matched_files: int = 0,
    grep_overhead: int = 0,
) -> int:
    metadata: dict[str, Any] = {
        "result_count": result_count,
        "output_tokens": output_tokens,
        "naive_tokens": naive_tokens,
        "tokens_saved": tokens_saved,
    }
    if query:
        metadata["query"] = query[:200]
    if matched_files:
        metadata["matched_files"] = matched_files
    if grep_overhead:
        metadata["grep_overhead"] = grep_overhead
    return log_event(db, tool_name, duration_ms, metadata)


# ── read side (used by api.py) ────────────────────────────────────────────────

def get_tool_summary(db: CodeDriftDB) -> list[dict]:
    """Call counts and total tokens saved grouped by event_type (tools only)."""
    rows = db.execute(
        """
        SELECT
            event_type AS tool,
            COUNT(*) AS call_count,
            COALESCE(SUM(CAST(json_extract(metadata, '$.tokens_saved') AS INTEGER)), 0)
                AS total_tokens_saved
        FROM analytics_events
        WHERE event_type NOT IN ('init', 'update')
        GROUP BY event_type
        ORDER BY call_count DESC
        """
    )
    return [dict(r) for r in rows]


def get_tool_timeline(db: CodeDriftDB, days: int = 30) -> list[dict]:
    """Daily call counts and tokens saved for the last N days (tools only)."""
    rows = db.execute(
        """
        SELECT
            date(timestamp, 'unixepoch') AS date,
            COUNT(*) AS call_count,
            COALESCE(SUM(CAST(json_extract(metadata, '$.tokens_saved') AS INTEGER)), 0)
                AS tokens_saved
        FROM analytics_events
        WHERE event_type NOT IN ('init', 'update')
          AND timestamp >= strftime('%s', 'now', ? )
        GROUP BY date
        ORDER BY date
        """,
        (f"-{days} days",),
    )
    return [dict(r) for r in rows]


def get_index_history(db: CodeDriftDB) -> list[dict]:
    """All init/update events, newest first."""
    rows = db.execute(
        """
        SELECT
            id, event_type, timestamp, duration_ms,
            CAST(json_extract(metadata, '$.files_indexed') AS INTEGER) AS files_indexed,
            CAST(json_extract(metadata, '$.files_skipped') AS INTEGER) AS files_skipped,
            CAST(json_extract(metadata, '$.symbols')       AS INTEGER) AS symbols,
            json_extract(metadata, '$.incremental') AS incremental
        FROM analytics_events
        WHERE event_type IN ('init', 'update')
        ORDER BY timestamp DESC
        """
    )
    return [dict(r) for r in rows]


def get_savings_summary(db: CodeDriftDB) -> dict:
    """Total tokens saved, breakdown by tool, and daily cumulative over time."""
    # total
    total_row = db.execute(
        """
        SELECT COALESCE(SUM(CAST(json_extract(metadata, '$.tokens_saved') AS INTEGER)), 0)
            AS total
        FROM analytics_events
        WHERE event_type NOT IN ('init', 'update')
        """
    )
    total = total_row[0]["total"] if total_row else 0

    # by tool
    by_tool_rows = db.execute(
        """
        SELECT
            event_type AS tool,
            COALESCE(SUM(CAST(json_extract(metadata, '$.tokens_saved') AS INTEGER)), 0)
                AS tokens_saved
        FROM analytics_events
        WHERE event_type NOT IN ('init', 'update')
        GROUP BY event_type
        ORDER BY tokens_saved DESC
        """
    )

    # daily for area chart
    daily_rows = db.execute(
        """
        SELECT
            date(timestamp, 'unixepoch') AS date,
            COALESCE(SUM(CAST(json_extract(metadata, '$.tokens_saved') AS INTEGER)), 0)
                AS daily_saved
        FROM analytics_events
        WHERE event_type NOT IN ('init', 'update')
        GROUP BY date
        ORDER BY date
        """
    )

    # build cumulative
    cumulative = 0
    over_time = []
    for row in daily_rows:
        cumulative += row["daily_saved"]
        over_time.append({"date": row["date"], "cumulative_saved": cumulative})

    return {
        "total_tokens_saved": total,
        "by_tool": [dict(r) for r in by_tool_rows],
        "over_time": over_time,
    }


def get_symbol_heatmap(db: CodeDriftDB, limit: int = 20) -> list[dict]:
    """Top N most-resolved symbols with their file and kind."""
    rows = db.execute(
        """
        SELECT
            json_extract(ae.metadata, '$.query') AS symbol,
            COUNT(*) AS call_count,
            s.file,
            s.kind
        FROM analytics_events ae
        LEFT JOIN symbols s ON s.name = json_extract(ae.metadata, '$.query')
        WHERE ae.event_type = 'codedrift_resolve'
          AND json_extract(ae.metadata, '$.query') IS NOT NULL
        GROUP BY symbol
        ORDER BY call_count DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows]


def get_memory_hit_rate(db: CodeDriftDB) -> dict:
    """Hit/miss breakdown for codedrift_memory calls."""
    rows = db.execute(
        """
        SELECT
            COUNT(*) AS total_calls,
            SUM(CASE WHEN CAST(json_extract(metadata, '$.tokens_saved') AS INTEGER) > 0
                     THEN 1 ELSE 0 END) AS hits
        FROM analytics_events
        WHERE event_type = 'codedrift_memory'
        """
    )
    if not rows:
        return {"total_calls": 0, "hits": 0, "misses": 0, "hit_rate_pct": 0.0}
    total = rows[0]["total_calls"] or 0
    hits = rows[0]["hits"] or 0
    misses = total - hits
    hit_rate = round((hits / total * 100), 1) if total else 0.0
    return {"total_calls": total, "hits": hits, "misses": misses, "hit_rate_pct": hit_rate}


def get_avg_response_size(db: CodeDriftDB) -> list[dict]:
    """Average output tokens per tool with a daily trend."""
    tools_rows = db.execute(
        """
        SELECT
            event_type AS tool,
            ROUND(AVG(CAST(json_extract(metadata, '$.output_tokens') AS REAL)), 1)
                AS avg_output_tokens
        FROM analytics_events
        WHERE event_type NOT IN ('init', 'update')
          AND json_extract(metadata, '$.output_tokens') IS NOT NULL
        GROUP BY event_type
        ORDER BY avg_output_tokens DESC
        """
    )

    results = []
    for tool_row in tools_rows:
        tool = tool_row["tool"]
        trend_rows = db.execute(
            """
            SELECT
                date(timestamp, 'unixepoch') AS date,
                ROUND(AVG(CAST(json_extract(metadata, '$.output_tokens') AS REAL)), 1) AS avg
            FROM analytics_events
            WHERE event_type = ?
              AND json_extract(metadata, '$.output_tokens') IS NOT NULL
              AND timestamp >= strftime('%s', 'now', '-30 days')
            GROUP BY date
            ORDER BY date
            """,
            (tool,),
        )
        results.append({
            "tool": tool,
            "avg_output_tokens": tool_row["avg_output_tokens"],
            "trend": [dict(r) for r in trend_rows],
        })
    return results
