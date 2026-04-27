"""PII redaction — strips sensitive string literals before content reaches the LLM."""

import dataclasses
import json
import re
from pathlib import Path
from typing import Optional

_CONFIG_FILE = "redact.json"
_MODEL_ID = "openai/privacy-filter"
_MIN_STR_LEN = 6

# String literal node types per tree-sitter grammar
_STRING_NODES: dict[str, set[str]] = {
    "python":     {"string"},
    "javascript": {"string", "template_string"},
    "typescript": {"string", "template_string"},
    "go":         {"interpreted_string_literal", "raw_string_literal"},
    "rust":       {"string_literal"},
}

# BIOES prefix: "B-secret" → "secret"
_BIOES = re.compile(r"^[BIES]-")

# module-level model cache (loaded once per process)
_session = None
_tokenizer = None
_id2label: dict[int, str] = {}


@dataclasses.dataclass
class RedactConfig:
    enabled: bool = False
    entity_types: list = dataclasses.field(
        default_factory=lambda: ["secret", "private_email", "account_number"]
    )
    allow_patterns: list = dataclasses.field(default_factory=list)
    env_passthrough_keys: list = dataclasses.field(
        default_factory=lambda: ["NODE_ENV", "PORT", "HOST", "DEBUG", "APP_ENV", "LOG_LEVEL"]
    )


def load_config(project_dir: str) -> RedactConfig:
    path = Path(project_dir) / ".codecodedrift" / _CONFIG_FILE
    if not path.exists():
        return RedactConfig()
    data = json.loads(path.read_text())
    valid = {f.name for f in dataclasses.fields(RedactConfig)}
    return RedactConfig(**{k: v for k, v in data.items() if k in valid})


def save_config(project_dir: str, cfg: RedactConfig) -> None:
    path = Path(project_dir) / ".codecodedrift" / _CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataclasses.asdict(cfg), indent=2))


def _ensure_model() -> None:
    global _session, _tokenizer, _id2label
    if _session is not None:
        return
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "PII redaction requires: pip install onnxruntime tokenizers huggingface_hub"
        ) from exc

    onnx_path = hf_hub_download(_MODEL_ID, filename="onnx/model_q4.onnx")
    hf_hub_download(_MODEL_ID, filename="onnx/model_q4.onnx_data")
    tokenizer_path = hf_hub_download(_MODEL_ID, filename="tokenizer.json")
    config_path = hf_hub_download(_MODEL_ID, filename="config.json")

    with open(config_path) as f:
        _id2label.update({int(k): v for k, v in json.load(f).get("id2label", {}).items()})

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    _session = ort.InferenceSession(onnx_path, opts, providers=["CPUExecutionProvider"])
    _tokenizer = Tokenizer.from_file(tokenizer_path)


def _detect_pii(line: str, entity_types: set[str]) -> Optional[str]:
    """Run the model on a source line. Returns the entity label or None.

    Passing the full line (e.g. `credentials = "Tr0ub4dor&3"`) rather than
    the bare string value gives the model the variable-name context it needs
    to distinguish secrets from ordinary strings.
    """
    import numpy as np

    _ensure_model()
    encoding = _tokenizer.encode(line)
    ort_inputs = {
        "input_ids": np.array([encoding.ids], dtype=np.int64),
        "attention_mask": np.array([encoding.attention_mask], dtype=np.int64),
    }
    logits = _session.run(None, ort_inputs)[0][0]  # [seq_len, n_labels]
    for pid in logits.argmax(axis=-1):
        entity = _BIOES.sub("", _id2label.get(int(pid), "O"))
        if entity in entity_types:
            return entity
    return None


def _walk_strings(node, string_node_types: set[str]):
    """Yield string literal nodes, skipping interpolated strings (f-strings, template literals)."""
    if node.type in string_node_types:
        if not any(c.type in ("interpolation", "template_substitution") for c in node.children):
            yield node
        return
    for child in node.children:
        yield from _walk_strings(child, string_node_types)


def _redact_code(source: str, lang: str, entity_types: set[str], allow_patterns: list) -> str:
    string_node_types = _STRING_NODES.get(lang)
    if not string_node_types:
        return source
    try:
        from tree_sitter_language_pack import get_parser
        tree = get_parser(lang).parse(source.encode())
    except Exception:
        return source

    source_lines = source.splitlines()
    replacements: list[tuple[int, int, bytes]] = []
    for node in _walk_strings(tree.root_node, string_node_types):
        value = node.text.decode(errors="replace")
        if len(value) < _MIN_STR_LEN:
            continue
        if any(re.search(p, value) for p in allow_patterns):
            continue
        line = source_lines[node.start_point[0]] if source_lines else value
        entity = _detect_pii(line, entity_types)
        if entity:
            tag = entity.upper().removeprefix("PRIVATE_")
            replacements.append((node.start_byte, node.end_byte, f'"[REDACTED:{tag}]"'.encode()))

    if not replacements:
        return source

    result = bytearray(source.encode())
    for start, end, replacement in sorted(replacements, key=lambda x: x[0], reverse=True):
        result[start:end] = replacement
    return result.decode(errors="replace")


def _redact_env(content: str, entity_types: set[str], allow_patterns: list, passthrough: set[str]) -> str:
    if not entity_types.intersection({"secret", "account_number", "private_email"}):
        return content
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(line)
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not value.strip() or key in passthrough or any(re.search(p, value) for p in allow_patterns):
            lines.append(line)
            continue
        lines.append(f"{key}=[REDACTED:SECRET]")
    return "\n".join(lines)


def redact(content: str, file_path: str, project_dir: str) -> str:
    """Entry point — redact PII from file content before it is returned to the LLM."""
    cfg = load_config(project_dir)
    if not cfg.enabled:
        return content

    entity_types = set(cfg.entity_types)
    allow_patterns = cfg.allow_patterns
    name = Path(file_path).name

    if name.startswith(".env") or name.endswith(".env"):
        return _redact_env(content, entity_types, allow_patterns, set(cfg.env_passthrough_keys))

    from .languages import get_adapter
    adapter = get_adapter(file_path)
    if adapter is None:
        return content

    return _redact_code(content, adapter.language_name, entity_types, allow_patterns)
