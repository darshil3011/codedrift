from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Symbol:
    name: str
    kind: str           # "function" | "class" | "method" | "variable"
    file: str           # relative path
    start_line: int
    end_line: int
    signature: str      # first line / declaration
    language: str = ""


@dataclass
class CallSite:
    symbol_name: str    # the function being called
    caller_file: str
    line: int
    context: str        # the actual line of code
    full_name: str = "" # "module.func" or just "func"


@dataclass
class ImportRef:
    symbol_name: str    # symbol being imported
    file: str
    import_line: str    # "from auth.jwt import validate_token"


# ── tree-sitter API compatibility shim (0.24 ↔ 0.25+) ────────────────────────
#
# tree-sitter 0.25 changed every Node/Tree attribute from a property to a
# method call (root_node(), kind(), start_position(), …) and dropped node.text.
# _TSNode/_TSTree wrap the new API to expose the old property-based interface
# so all language adapters continue to work without modification.

class _TSNode:
    """Wraps a tree-sitter ≥0.25 Node to expose the ≤0.24 property API."""

    def __init__(self, node, source: bytes):
        self._n = node
        self._src = source

    @property
    def type(self) -> str:
        return self._n.kind()

    @property
    def start_point(self):
        p = self._n.start_position()
        return (p.row, p.column)

    @property
    def end_point(self):
        p = self._n.end_position()
        return (p.row, p.column)

    @property
    def text(self) -> bytes:
        br = self._n.byte_range()
        return self._src[br.start:br.end]

    @property
    def children(self) -> list:
        count = self._n.child_count()
        return [_TSNode(self._n.child(i), self._src) for i in range(count)]

    @property
    def parent(self):
        p = self._n.parent()
        return _TSNode(p, self._src) if p is not None else None

    def child_by_field_name(self, name: str):
        n = self._n.child_by_field_name(name)
        return _TSNode(n, self._src) if n is not None else None

    def child(self, i: int):
        n = self._n.child(i)
        return _TSNode(n, self._src) if n is not None else None

    def __eq__(self, other):
        if isinstance(other, _TSNode):
            return (self._n.start_byte() == other._n.start_byte() and
                    self._n.end_byte() == other._n.end_byte())
        return NotImplemented

    def __hash__(self):
        return hash((self._n.start_byte(), self._n.end_byte()))


class _TSTree:
    """Wraps a tree-sitter ≥0.25 Tree to expose the ≤0.24 property API."""

    def __init__(self, tree, source: bytes):
        self._t = tree
        self._src = source

    @property
    def root_node(self) -> _TSNode:
        return _TSNode(self._t.root_node(), self._src)


def _wrap_tree(raw_tree, source: bytes):
    """Wrap raw_tree in _TSTree when the ≥0.25 API is detected."""
    if callable(getattr(raw_tree, "root_node", None)):
        return _TSTree(raw_tree, source)
    return raw_tree  # old API — pass through unchanged


# ── Language adapter base class ───────────────────────────────────────────────

class LanguageAdapter:
    """Base class for language-specific AST extraction."""

    language_name: str = ""
    file_extensions: tuple = ()
    function_node_types: tuple = ()
    class_node_types: tuple = ()
    import_node_types: tuple = ()
    call_node_types: tuple = ()

    def _get_parser(self):
        from tree_sitter_language_pack import get_parser
        return get_parser(self.language_name)

    def parse(self, source: bytes):
        parser = self._get_parser()
        # tree-sitter >= 0.25 renamed parse(bytes) → parse_bytes(bytes)
        parse_fn = getattr(parser, "parse_bytes", parser.parse)
        return _wrap_tree(parse_fn(source), source)

    def _node_text(self, node, source_lines: List[str]) -> str:
        return source_lines[node.start_point[0]] if source_lines else ""

    def _node_lines(self, node, source_lines: List[str]) -> List[str]:
        return source_lines[node.start_point[0]: node.end_point[0] + 1]

    def extract_symbols(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        """Extract all functions and classes from the AST."""
        symbols: List[Symbol] = []
        symbols.extend(self.extract_functions(tree, source_lines, filepath))
        symbols.extend(self.extract_classes(tree, source_lines, filepath))
        return symbols

    def extract_functions(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        raise NotImplementedError

    def extract_classes(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        raise NotImplementedError

    def extract_imports(self, tree, source_lines: List[str], filepath: str) -> List[ImportRef]:
        raise NotImplementedError

    def extract_calls(self, tree, source_lines: List[str], filepath: str) -> List[CallSite]:
        raise NotImplementedError

    def is_test_file(self, filepath: str) -> bool:
        return False

    # ── shared tree-walking helpers ──────────────────────────────────────────

    def _walk(self, node, node_types: tuple):
        """Yield all descendant nodes of the given types."""
        if node.type in node_types:
            yield node
        for child in node.children:
            yield from self._walk(child, node_types)
