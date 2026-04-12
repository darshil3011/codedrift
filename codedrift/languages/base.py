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
        return self._get_parser().parse(source)

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
