import os
from typing import List
from .base import LanguageAdapter, Symbol, CallSite, ImportRef

_FUNCTION_TYPES = (
    "function_declaration",
    "function",
    "arrow_function",
    "method_definition",
    "generator_function_declaration",
    "generator_function",
)

_CLASS_TYPES = ("class_declaration", "class")

_IMPORT_TYPES = ("import_statement",)

_CALL_TYPES = ("call_expression",)


class JavaScriptAdapter(LanguageAdapter):
    language_name = "javascript"
    file_extensions = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
    function_node_types = _FUNCTION_TYPES
    class_node_types = _CLASS_TYPES
    import_node_types = _IMPORT_TYPES
    call_node_types = _CALL_TYPES

    def _get_parser(self):
        from tree_sitter_language_pack import get_parser
        ext_map = {".ts": "typescript", ".tsx": "typescript"}
        # Default to javascript; use typescript grammar for .ts/.tsx
        return get_parser("javascript")

    def _parser_for(self, filepath: str):
        from tree_sitter_language_pack import get_parser
        ext = os.path.splitext(filepath)[1].lower()
        lang = "typescript" if ext in (".ts", ".tsx") else "javascript"
        return get_parser(lang)

    def parse_file(self, source: bytes, filepath: str):
        return self._parser_for(filepath).parse(source)

    def extract_functions(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.function_node_types):
            name = self._function_name(node)
            if not name:
                continue
            sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
            kind = "method" if node.type == "method_definition" else "function"
            symbols.append(Symbol(
                name=name,
                kind=kind,
                file=filepath,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=sig,
                language="javascript",
            ))
        return symbols

    def extract_classes(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.class_node_types):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
            symbols.append(Symbol(
                name=name_node.text.decode(),
                kind="class",
                file=filepath,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=sig,
                language="javascript",
            ))
        return symbols

    def extract_imports(self, tree, source_lines: List[str], filepath: str) -> List[ImportRef]:
        refs = []
        for node in self._walk(tree.root_node, self.import_node_types):
            line = source_lines[node.start_point[0]].strip() if source_lines else ""
            # ES6: import { a, b } from 'mod' or import DefaultExport from 'mod'
            for child in self._walk(node, ("identifier", "namespace_import")):
                refs.append(ImportRef(symbol_name=child.text.decode(), file=filepath, import_line=line))
        # CommonJS: const x = require('mod')
        for node in self._walk(tree.root_node, ("call_expression",)):
            fn = node.child_by_field_name("function")
            if fn and fn.text == b"require":
                # find the enclosing variable declaration
                line = source_lines[node.start_point[0]].strip() if source_lines else ""
                refs.append(ImportRef(symbol_name="require", file=filepath, import_line=line))
        return refs

    def extract_calls(self, tree, source_lines: List[str], filepath: str) -> List[CallSite]:
        sites = []
        for node in self._walk(tree.root_node, self.call_node_types):
            fn_node = node.child_by_field_name("function")
            if not fn_node:
                continue
            full_name = fn_node.text.decode()
            name = full_name.split(".")[-1]
            line_idx = node.start_point[0]
            context = source_lines[line_idx].rstrip() if source_lines else ""
            sites.append(CallSite(
                symbol_name=name,
                caller_file=filepath,
                line=line_idx + 1,
                context=context,
                full_name=full_name,
            ))
        return sites

    def is_test_file(self, filepath: str) -> bool:
        basename = os.path.basename(filepath)
        parts = filepath.replace("\\", "/").split("/")
        return (
            ".test." in basename
            or ".spec." in basename
            or "__tests__" in parts
        )

    def _function_name(self, node) -> str:
        """Extract function name from various function node shapes."""
        # function_declaration / method_definition have a 'name' field
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode()
        # arrow_function assigned to a variable: look at parent
        parent = node.parent
        if parent and parent.type == "variable_declarator":
            id_node = parent.child_by_field_name("name")
            if id_node:
                return id_node.text.decode()
        return ""
