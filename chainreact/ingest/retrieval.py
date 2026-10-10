"""Semantic-context retrieval (enrichment only; detection completeness never depends on this).

Embedder is a swappable seam (Claude has no embeddings API; use Ollama/local in practice).
VectorStore here is in-memory; a pgvector-backed store implements the same interface later.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Dict, List, Protocol, Tuple

from chainreact.contracts import FieldDecl


class Embedder(Protocol):
    model: str
    dim: int

    def embed(self, texts: List[str]) -> List[List[float]]: ...


class HashEmbedder:
    """Deterministic bag-of-tokens embedder for tests/offline use."""
    model, dim = "hash-v1", 256

    def embed(self, texts: List[str]) -> List[List[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in t.lower().replace(".", " ").replace("_", " ").split():
                v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


@dataclass
class Chunk:
    service: str
    key: str
    text: str


def chunks_from_decls(decls: List[FieldDecl]) -> List[Chunk]:
    return [Chunk(d.service, f"{d.endpoint}#{d.name}",
                  f"{d.service} {d.endpoint} field {d.name} type {d.type}"
                  + (f" format {d.format}" if d.format else "") + (f" unit {d.unit}" if d.unit else "")
                  + (f" enum {','.join(d.enum)}" if d.enum else "")) for d in decls]


class VectorStore:
    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self._rows: Dict[Tuple[str, str], Tuple[str, Chunk, List[float]]] = {}
        self.embed_calls = 0  # chunks actually embedded (for incremental-cost tests)

    def upsert(self, chunks: List[Chunk]) -> int:
        """Embed only new/changed chunks (content hash). Returns number embedded."""
        todo = []
        for c in chunks:
            h = hashlib.sha256(c.text.encode()).hexdigest()
            cur = self._rows.get((c.service, c.key))
            if cur is None or cur[0] != h:
                todo.append((c, h))
        if todo:
            vecs = self.embedder.embed([c.text for c, _ in todo])
            for (c, h), v in zip(todo, vecs):
                self._rows[(c.service, c.key)] = (h, c, v)
        self.embed_calls += len(todo)
        return len(todo)

    def query(self, text: str, k: int = 5, service: str = None) -> List[Chunk]:
        q = self.embedder.embed([text])[0]
        scored = [(sum(a * b for a, b in zip(q, v)), c) for _, c, v in self._rows.values()
                  if service is None or c.service == service]
        return [c for _, c in sorted(scored, key=lambda x: -x[0])[:k]]
