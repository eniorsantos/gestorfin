"""Testes do reranker cross-encoder (Fase 8 - fallback quando sem rede/modelo)."""
from finllm.rerank_crossencoder import CrossEncoderReranker, rerank_cross_encoder


class FakeHit:
    def __init__(self, content, score=0.0, via="vec"):
        self.content = content
        self.score = score
        self.via = via


def test_rerank_fallback_forcado():
    """Força o fallback (sem sentence-transformers disponível)."""
    reranker = CrossEncoderReranker()
    reranker._disponivel = False
    hits = [FakeHit("receita liquida da WEG 2023", 0.5),
            FakeHit("outro documento irrelevante", 0.4)]
    resultado = reranker.rerank("receita WEG", hits, top_n=1)
    assert len(resultado) == 1
    assert resultado[0].content == "receita liquida da WEG 2023"


def test_rerank_cross_encoder_funcao():
    reranker = CrossEncoderReranker()
    reranker._disponivel = False
    hits = [FakeHit("receita WEG 2023", 0.5), FakeHit("xpto", 0.4)]
    res = reranker.rerank("receita WEG", hits, top_n=1)
    assert len(res) == 1
