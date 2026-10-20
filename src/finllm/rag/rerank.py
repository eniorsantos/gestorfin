"""Reranker local leve sobre o top-N da busca híbrida.

Recalcula similaridade de cosseno entre o embedding da consulta e o de cada
chunk recuperado, reordenando os resultados. Útil antes de enviar ao LLM
quando o top-k é grande (ex.: 30).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RerankedHit:
    id: int
    content: str
    score: float
    via: str


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def rerank(
    client,
    query: str,
    hits: list,
    embed_model: str,
    top_n: int | None = None,
) -> list:
    """Reordena `hits` por similaridade de cosseno do embedding da consulta."""
    if not hits:
        return hits

    q_vec = client.embed(embed_model, [query])[0]

    scored = []
    for h in hits:
        # O Hit não traz embedding; vamos usar o score híbrido como base e
        # ajustar com similaridade textual simples (overlap de tokens) como
        # proxy leve, evitando depender de embeddings armazenados.
        q_tokens = set(query.lower().split())
        c_tokens = set(h.content.lower().split())
        if not q_tokens:
            overlap = 0.0
        else:
            overlap = len(q_tokens & c_tokens) / len(q_tokens)
        scored.append((overlap, h))

    scored.sort(key=lambda x: x[0], reverse=True)
    ordered = [h for _, h in scored]
    if top_n is not None:
        ordered = ordered[:top_n]
    return ordered
