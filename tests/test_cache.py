"""Testes do cache (melhoria RAG)."""
import tempfile
from pathlib import Path

from finllm.cache import CacheRespostas, CacheEmbeddings, cache_respostas, cache_embeddings


def test_cache_respostas(tmp_path):
    c = CacheRespostas(tmp_path)
    c.set("qual a receita?", "qwen3:8b", {"valor": 100.0})
    assert c.get("qual a receita?", "qwen3:8b") == {"valor": 100.0}
    assert c.get("outra pergunta", "qwen3:8b") is None


def test_cache_embeddings(tmp_path):
    c = CacheEmbeddings(tmp_path)
    c.set("texto de teste", "bge-m3", [0.1, 0.2, 0.3])
    assert c.get("texto de teste", "bge-m3") == [0.1, 0.2, 0.3]
    assert c.get("outro texto", "bge-m3") is None


def test_singleton():
    a = cache_respostas()
    b = cache_respostas()
    assert a is b
    c = cache_embeddings()
    d = cache_embeddings()
    assert c is d
