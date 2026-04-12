from .python_lang import PythonAdapter
from .javascript_lang import JavaScriptAdapter
from .go_lang import GoAdapter
from .rust_lang import RustAdapter

ADAPTERS = [PythonAdapter(), JavaScriptAdapter(), GoAdapter(), RustAdapter()]

_ext_map: dict[str, object] = {}
for _adapter in ADAPTERS:
    for _ext in _adapter.file_extensions:
        _ext_map[_ext] = _adapter


def get_adapter(filepath: str):
    """Return the language adapter for a file, or None if unsupported."""
    import os
    ext = os.path.splitext(filepath)[1].lower()
    return _ext_map.get(ext)
