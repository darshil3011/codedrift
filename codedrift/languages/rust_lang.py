import os
from typing import List
from .base import LanguageAdapter, Symbol, CallSite, ImportRef


class RustAdapter(LanguageAdapter):
    language_name = "rust"
    file_extensions = (".rs",)
    function_node_types = ("function_item",)
    class_node_types = ("struct_item", "enum_item", "impl_item")
    import_node_types = ("use_declaration",)
    call_node_types = ("call_expression", "method_call_expression")

    def extract_functions(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.function_node_types):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
            symbols.append(Symbol(
                name=name_node.text.decode(),
                kind="function",
                file=filepath,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=sig,
                language="rust",
            ))
        return symbols

    def extract_classes(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.class_node_types):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            kind_map = {"struct_item": "class", "enum_item": "class", "impl_item": "class"}
            sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
            symbols.append(Symbol(
                name=name_node.text.decode(),
                kind=kind_map.get(node.type, "class"),
                file=filepath,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=sig,
                language="rust",
            ))
        return symbols

    def extract_imports(self, tree, source_lines: List[str], filepath: str) -> List[ImportRef]:
        refs = []
        for node in self._walk(tree.root_node, self.import_node_types):
            line = source_lines[node.start_point[0]].strip() if source_lines else ""
            refs.append(ImportRef(symbol_name=node.text.decode(), file=filepath, import_line=line))
        return refs

    def extract_calls(self, tree, source_lines: List[str], filepath: str) -> List[CallSite]:
        sites = []
        for node in self._walk(tree.root_node, self.call_node_types):
            if node.type == "call_expression":
                fn_node = node.child_by_field_name("function")
            else:
                fn_node = node.child_by_field_name("method")
            if not fn_node:
                continue
            full_name = fn_node.text.decode()
            name = full_name.split("::")[-1].split(".")[-1]
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
        # Rust tests are typically in the same file under #[cfg(test)], or in tests/ dir
        parts = filepath.replace("\\", "/").split("/")
        return "tests" in parts
