"""Token savings ledger — estimates tokens saved by CodeDrift vs naive file reads."""

from dataclasses import dataclass
from pathlib import Path

# ~4 chars per token is a widely-used rough approximation for code
_CHARS_PER_TOKEN = 4


def _tokens(text: str) -> int:
    return max(0, len(text) // _CHARS_PER_TOKEN)


def file_tokens(path: str) -> int:
    """Estimate the token count of a file by reading its raw character count."""
    try:
        return _tokens(Path(path).read_text(errors="replace"))
    except OSError:
        return 0


@dataclass
class _Record:
    tool: str
    output_tokens: int
    naive_tokens: int

    @property
    def saved(self) -> int:
        return max(0, self.naive_tokens - self.output_tokens)


class TokenSavingsLedger:
    """Accumulates token savings across the MCP session."""

    def __init__(self):
        self._records: list[_Record] = []

    @property
    def session_saved(self) -> int:
        return sum(r.saved for r in self._records)

    def record(self, tool: str, output: str, naive_tokens: int) -> int:
        """Register a tool call and return tokens saved for this call."""
        rec = _Record(tool, _tokens(output), naive_tokens)
        self._records.append(rec)
        return rec.saved

    def format_footer(self, saved: int) -> str:
        return (
            f"\n\n[CodeDrift · ~{saved:,} tokens saved this call"
            f" · session total: ~{self.session_saved:,}]"
        )
