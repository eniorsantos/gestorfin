"""Cache de respostas e embeddings de consulta (melhoria RAG candidata).

Cache simples em disco (JSON) para evitar re-processar perguntas já respondidas
e re-embedar consultas repetidas. Pode ser substituído por Redis no futuro.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional


def _chave(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


class CacheRespostas:
    def __init__(self, diretorio: Path | str = Path("data/cache")):
        self.diretorio = Path(diretorio)
        self.diretorio.mkdir(parents=True, exist_ok=True)

    def _caminho(self, chave: str) -> Path:
        return self.diretorio / f"{chave}.json"

    def get(self, pergunta: str, modelo: str) -> Optional[dict]:
        chave = _chave(f"{modelo}|{pergunta}")
        caminho = self._caminho(chave)
        if not caminho.exists():
            return None
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, pergunta: str, modelo: str, valor: dict) -> None:
        chave = _chave(f"{modelo}|{pergunta}")
        self._caminho(chave).write_text(json.dumps(valor, ensure_ascii=False), encoding="utf-8")


class CacheEmbeddings:
    def __init__(self, diretorio: Path | str = Path("data/cache/embeddings")):
        self.diretorio = Path(diretorio)
        self.diretorio.mkdir(parents=True, exist_ok=True)

    def _caminho(self, chave: str) -> Path:
        return self.diretorio / f"{chave}.json"

    def get(self, texto: str, modelo: str) -> Optional[list[float]]:
        chave = _chave(f"{modelo}|{texto}")
        caminho = self._caminho(chave)
        if not caminho.exists():
            return None
        try:
            data = json.loads(caminho.read_text(encoding="utf-8"))
            return data.get("embedding")
        except Exception:
            return None

    def set(self, texto: str, modelo: str, embedding: list[float]) -> None:
        chave = _chave(f"{modelo}|{texto}")
        self._caminho(chave).write_text(
            json.dumps({"embedding": embedding}), encoding="utf-8"
        )


_cache_respostas: Optional[CacheRespostas] = None
_cache_embeddings: Optional[CacheEmbeddings] = None


def cache_respostas() -> CacheRespostas:
    global _cache_respostas
    if _cache_respostas is None:
        _cache_respostas = CacheRespostas()
    return _cache_respostas


def cache_embeddings() -> CacheEmbeddings:
    global _cache_embeddings
    if _cache_embeddings is None:
        _cache_embeddings = CacheEmbeddings()
    return _cache_embeddings
