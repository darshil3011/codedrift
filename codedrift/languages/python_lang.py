import os
from typing import List
from .base import LanguageAdapter, Symbol, CallSite, ImportRef


class PythonAdapter(LanguageAdapter):
    language_name = "python"
    file_extensions = (".py",)
    function_node_types = ("function_definition",)
    class_node_types = ("class_definition",)
    import_node_types = ("import_statement", "import_from_statement")
    call_node_types = ("call",)

    def extract_functions(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.function_node_types):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            name = name_node.text.decode()
            sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
            kind = "method" if self._is_method(node) else "function"
            symbols.append(Symbol(
                name=name,
                kind=kind,
                file=filepath,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=sig,
                language="python",
            ))
        return symbols

    def extract_classes(self, tree, source_lines: List[str], filepath: str) -> List[Symbol]:
        symbols = []
        for node in self._walk(tree.root_node, self.class_node_types):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            name = name_node.text.decode()
            sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
            symbols.append(Symbol(
                name=name,
                kind="class",
                file=filepath,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=sig,
                language="python",
            ))
        return symbols

    def extract_imports(self, tree, source_lines: List[str], filepath: str) -> List[ImportRef]:
        refs = []
        for node in self._walk(tree.root_node, self.import_node_types):
            line = source_lines[node.start_point[0]].strip() if source_lines else ""
            if node.type == "import_from_statement":
                # from X import a, b, c
                names = [
                    c.text.decode()
                    for c in node.children
                    if c.type in ("dotted_name", "aliased_import", "identifier")
                    and c != node.children[1]  # skip the module name
                ]
                module_node = node.child_by_field_name("module_name")
                module = module_node.text.decode() if module_node else ""
                for name in names:
                    refs.append(ImportRef(symbol_name=name, file=filepath, import_line=line))
            else:
                # import X, Y
                for child in node.children:
                    if child.type in ("dotted_name", "aliased_import"):
                        refs.append(ImportRef(symbol_name=child.text.decode(), file=filepath, import_line=line))
        return refs

    def extract_calls(self, tree, source_lines: List[str], filepath: str) -> List[CallSite]:
        sites = []
        for node in self._walk(tree.root_node, self.call_node_types):
            func_node = node.child_by_field_name("function")
            if not func_node:
                continue
            full_name = func_node.text.decode()
            # simple name: last segment after "." for attribute access
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
        return basename.startswith("test_") or basename.endswith("_test.py")

    # ── helpers ────────────────────────────────────────────────────────────

    def _is_method(self, func_node) -> bool:
        """True if the function is defined inside a class body."""
        parent = func_node.parent
        while parent:
            if parent.type == "class_definition":
                return True
            if parent.type == "module":
                break
            parent = parent.parent
        return False
