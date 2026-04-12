import os
from typing import List
from .base import LanguageAdapter, Symbol, CallSite, ImportRef


class GoAdapter(LanguageAdapter):
    language_name = "go"
    file_extensions = (".go",)
    function_node_types = ("function_declaration", "method_declaration")
    class_node_types = ("type_declaration",)
    import_node_types = ("import_declaration",)
    call_node_types = ("call_expression",)

    def extract_functions(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.function_node_types):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            kind = "method" if node.type == "method_declaration" else "function"
            sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
            symbols.append(Symbol(
                name=name_node.text.decode(),
                kind=kind,
                file=filepath,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=sig,
                language="go",
            ))
        return symbols

    def extract_classes(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.class_node_types):
            # type_declaration → type_spec → name
            for spec in self._walk(node, ("type_spec",)):
                name_node = spec.child_by_field_name("name")
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
                    language="go",
                ))
        return symbols

    def extract_imports(self, tree, source_lines: List[str], filepath: str) -> List[ImportRef]:
        refs = []
        for node in self._walk(tree.root_node, self.import_node_types):
            line = source_lines[node.start_point[0]].strip() if source_lines else ""
            for child in self._walk(node, ("import_spec",)):
                path_node = child.child_by_field_name("path")
                if path_node:
                    pkg = path_node.text.decode().strip('"').split("/")[-1]
                    refs.append(ImportRef(symbol_name=pkg, file=filepath, import_line=line))
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
        return os.path.basename(filepath).endswith("_test.go")
