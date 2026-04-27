"""Session memory engine — embed, store, and recall proven context sets."""

import json
import time
from typing import Optional

from .db import CodeDriftDB

_EMBED_DIM = 384
_MODEL_NAME = "all-MiniLM-L6-v2"


def _require_deps():
    try:
        import numpy  # noqa: F401
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Memory support requires: pip install codedrift[memory]"
        ) from exc


class SessionMemory:
    """Vector-similarity recall for past agent sessions."""

    def __init__(self, db: CodeDriftDB):
        self.db = db
        self._encoder = None  # lazy — model load is ~1s

    def _get_encoder(self):
        if self._encoder is None:
            _require_deps()
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(_MODEL_NAME)
        return self._encoder

    def _encode(self, text: str):
        import numpy as np
        emb = self._get_encoder().encode(text)
        return emb.astype(np.float32)

    def record(
        self,
        task_text: str,
        context_files: list[str],
        context_symbols: list[str],
        tokens_used: Optional[int] = None,
        outcome: str = "success",
        session_id: Optional[str] = None,
    ) -> int:
        """Embed and store a completed session. Returns the new row id."""
        emb = self._encode(task_text)
        return self.db.insert_session_memory(
            task_text=task_text,
            embedding_bytes=emb.tobytes(),
            context_files_json=json.dumps(context_files),
            context_symbols_json=json.dumps(context_symbols),
            tokens_used=tokens_used,
            outcome=outcome,
            session_id=session_id,
        )

    def recall(self, query: str, threshold: float = 0.40) -> Optional[dict]:
        """
        Return the closest past session if similarity >= threshold, else None.

        Result keys: task_text, context_files, context_symbols,
                     confidence, similarity, session_id.
        """
        candidates = self.recall_all(query)
        for c in candidates:
            if c["similarity"] >= threshold:
                return c
        return None

    def recall_all(self, query: str) -> list[dict]:
        """
        Return all stored sessions ranked by similarity, highest first.
        No threshold applied — useful for debugging.
        """
        import numpy as np

        query_emb = self._encode(query)
        rows = self.db.get_all_session_embeddings()
        if not rows:
            return []

        results = []
        for row in rows:
            stored = np.frombuffer(bytes(row["task_embedding"]), dtype=np.float32)
            denom = np.linalg.norm(query_emb) * np.linalg.norm(stored)
            if denom == 0:
                score = 0.0
            else:
                score = float(np.dot(query_emb, stored) / denom)
            results.append({
                "task_text": row["task_text"],
                "context_files": json.loads(row["context_files"]),
                "context_symbols": json.loads(row["context_symbols"]),
                "confidence": row["confidence"],
                "similarity": round(score, 4),
                "session_id": row["session_id"],
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results
