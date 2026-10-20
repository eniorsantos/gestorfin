"""Busca híbrida: vetorial (pgvector) + texto completo (tsvector pt-BR), fundidas por RRF."""
from __future__ import annotations

import re
from dataclasses import dataclass

from psycopg.rows import dict_row

from ..config import settings
from ..ollama_client import OllamaClient
from . import entities
from .index import to_vec

RRF_K = 60
_YEAR = re.compile(r"\b(19[89]\d|20\d{2})\b")


@dataclass
class Hit:
    id: int
    content: str
    content_hash: str
    source: str
    cd_cvm: int | None
    denom: str | None
    doc_type: str | None
    ref_date: object
    title: str | None
    url: str | None
    score: float
    via: str


def _tsquery(q: str) -> str:
    toks = sorted({t.lower() for t in re.findall(r"[^\W_]{3,}", q)})
    return " | ".join(toks)


def hybrid_search(
    conn, client: OllamaClient, query: str, *, k: int | None = None,
    cd_cvms: list[int] | None = None, years: list[int] | None = None, source: str | None = None,
    data_entrega_max=None, fetch_n: int = 30,
) -> list[Hit]:
    k = k or settings.rag_top_k
    where, params = [], {"n": fetch_n}
    if cd_cvms:
        where.append("cd_cvm = ANY(%(cds)s)"); params["cds"] = cd_cvms
    if years:
        where.append("EXTRACT(year FROM ref_date)::int = ANY(%(years)s)"); params["years"] = years
    if source:
        where.append("source = %(source)s"); params["source"] = source
    if data_entrega_max is not None:
        where.append("(metadata->>'dt_entrega')::date <= %(entrega_max)s"); params["entrega_max"] = data_entrega_max
    w = " AND ".join(where)
    cols = "id, content, content_hash, source, cd_cvm, denom, doc_type, ref_date, title, url"

    qv = to_vec(client.embed(settings.embed_model, [query])[0])
    vec_sql = f"SELECT {cols} FROM chunks {'WHERE ' + w if w else ''} ORDER BY embedding <=> %(qv)s::vector LIMIT %(n)s"
    tsq = _tsquery(query)
    fts_sql = (
        f"SELECT {cols} FROM chunks WHERE {w + ' AND ' if w else ''}tsv @@ to_tsquery('portuguese', %(tsq)s) "
        "ORDER BY ts_rank_cd(tsv, to_tsquery('portuguese', %(tsq)s)) DESC LIMIT %(n)s"
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(vec_sql, {**params, "qv": qv})
        vec_rows = cur.fetchall()
        fts_rows = []
        if tsq:
            try:
                cur.execute(fts_sql, {**params, "tsq": tsq})
                fts_rows = cur.fetchall()
            except Exception:  # tsquery inválida: segue só com vetorial
                conn.rollback()

    fused: dict[int, dict] = {}
    for via, rows in (("vec", vec_rows), ("fts", fts_rows)):
        for rank, r in enumerate(rows):
            e = fused.setdefault(r["id"], {"row": r, "score": 0.0, "via": set()})
            e["score"] += 1.0 / (RRF_K + rank + 1)
            e["via"].add(via)
    ranked = sorted(fused.values(), key=lambda e: e["score"], reverse=True)[:k]
    return [Hit(score=e["score"], via="+".join(sorted(e["via"])), **e["row"]) for e in ranked]


def retrieve(conn, client: OllamaClient, question: str, *, k: int | None = None,
             cd_cvm: int | None = None, auto_filter: bool = True,
             data_entrega_max=None) -> tuple[list[Hit], dict]:
    """Detecta empresa/ano na pergunta e filtra; se nada voltar, refaz sem filtros.

    `data_entrega_max` ativa o modo point-in-time: só retorna chunks cujo documento
    foi entregue na CVM até aquela data, evitando look-ahead bias.
    """
    filters: dict = {}
    if auto_filter:
        cd = cd_cvm or entities.find_in_text(conn, question)
        if cd:
            filters["cd_cvms"] = [cd]
        years = sorted({int(y) for y in _YEAR.findall(question)})
        if years:
            filters["years"] = years
    elif cd_cvm:
        filters["cd_cvms"] = [cd_cvm]
    if data_entrega_max is not None:
        filters["data_entrega_max"] = str(data_entrega_max)
    hits = hybrid_search(conn, client, question, k=k, data_entrega_max=data_entrega_max, **filters)
    if not hits and filters:
        hits = hybrid_search(conn, client, question, k=k)
        filters = {"fallback_sem_filtro": True}
    return hits, filters
