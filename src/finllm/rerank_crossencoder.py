"""Reranker cross-encoder local (roadmap Fase 8 - melhoria RAG).

Reordena os top-N da busca híbrida usando um cross-encoder leve
(sentence-transformers). Se não estiver instalado, fallback para o
reranker por overlap de tokens em `rag.rerank`.
"""
from __future__ import annotations

try:
    from sentence_transformers import CrossEncoder  # type: ignore
except Exception:  # noqa: BLE001
    CrossEncoder = None  # type: ignore

from .rag.rerank import rerank as _rerank_leve


def _modelo_padrao() -> str:
    return "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    def __init__(self, modelo: Optional[str] = None):
        self.modelo_nome = modelo or _modelo_padrao()
        self._modelo = None
        self._disponivel = CrossEncoder is not None

    def _carregar(self):
        if not self._disponivel:
            raise RuntimeError("sentence-transformers não instalado")
        if self._modelo is None:
            self._modelo = CrossEncoder(self.modelo_nome)
        return self._modelo

    def rerank(
        self,
        consulta: str,
        hits: list,
        top_n: Optional[int] = None,
    ) -> list:
        """Reordena `hits` pelo score do cross-encoder."""
        if not hits:
            return hits
        if not self._disponivel:
            return _rerak_fallback(consulta, hits, top_n)

        try:
            modelo = self._carregar()
            pares = [[consulta, h.content] for h in hits]
            scores = modelo.predict(pares)
            ordenado = sorted(zip(hits, scores), key=lambda x: x[1], reverse=True)
            resultado = [h for h, _ in ordenado]
            if top_n is not None:
                resultado = resultado[:top_n]
            return resultado
        except Exception:
            return _rerak_fallback(consulta, hits, top_n)


def _rerak_fallback(consulta: str, hits: list, top_n: Optional[int] = None) -> list:
    """Fallback sem Ollama: reordena por overlap de tokens entre consulta e chunk."""
    if not hits:
        return hits
    q_tokens = set(consulta.lower().split())
    scored = []
    for h in hits:
        c_tokens = set(h.content.lower().split())
        overlap = len(q_tokens & c_tokens) / len(q_tokens) if q_tokens else 0.0
        scored.append((overlap, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    resultado = [h for _, h in scored]
    if top_n is not None:
        resultado = resultado[:top_n]
    return resultado


def rerank_cross_encoder(
    consulta: str,
    hits: list,
    top_n: Optional[int] = None,
    modelo: Optional[str] = None,
) -> list:
    """Função de conveniência para rerank com cross-encoder."""
    reranker = CrossEncoderReranker(modelo=modelo)
    return reranker.rerank(consulta, hits, top_n=top_n)
