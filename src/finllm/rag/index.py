"""Embeddings + gravação de chunks no pgvector (idempotente via content_hash)."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date

from ..config import settings
from ..ollama_client import OllamaClient


@dataclass
class ChunkIn:
    source: str
    content: str
    cd_cvm: int | None = None
    denom: str | None = None
    doc_type: str | None = None
    ref_date: date | None = None
    title: str | None = None
    url: str | None = None
    chunk_idx: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def to_vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def index_chunks(
    conn, client: OllamaClient, chunks: Iterable[ChunkIn], *, batch: int = 16,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[int, int]:
    """Retorna (novos, ignorados_por_ja_existirem)."""
    new = skipped = 0
    buf: list[ChunkIn] = []

    def flush() -> None:
        nonlocal new, skipped, buf
        if not buf:
            return
        with conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM chunks WHERE content_hash = ANY(%s)", ([c.hash for c in buf],))
            have = {r[0] for r in cur.fetchall()}
            todo = [c for c in buf if c.hash not in have]
            skipped += len(buf) - len(todo)
            if todo:
                vecs = client.embed(settings.embed_model, [c.content for c in todo])
                for c, v in zip(todo, vecs, strict=True):
                    cur.execute(
                        "INSERT INTO chunks (source, cd_cvm, denom, doc_type, ref_date, title, url, chunk_idx, "
                        "content, content_hash, metadata, embedding) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::vector) "
                        "ON CONFLICT (content_hash) DO NOTHING",
                        (c.source, c.cd_cvm, c.denom, c.doc_type, c.ref_date, c.title, c.url, c.chunk_idx,
                         c.content, c.hash, json.dumps(c.metadata), to_vec(v)),
                    )
                new += len(todo)
        conn.commit()
        buf = []
        if progress:
            progress(new, skipped)

    for ch in chunks:
        buf.append(ch)
        if len(buf) >= batch:
            flush()
    flush()
    return new, skipped
