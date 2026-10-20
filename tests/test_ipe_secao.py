"""Testes do chunking por seção (melhoria candidata - Docling/secao)."""
from finllm.cvm.ipe import _chunk_por_secao


def test_chunk_por_secao_simples():
    texto = """INTRODUCAO
Este e o texto de introducao do documento.

DADOS FINANCEIROS
Receita: 1.000.000
Lucro: 200.000

CONCLUSAO
O documento termina aqui."""
    chunks = _chunk_por_secao(texto, max_chars=200)
    assert len(chunks) >= 3
    # Cada chunk deve trazer o título da seção
    assert any("[INTRODUCAO]" in c for c in chunks)
    assert any("[DADOS FINANCEIROS]" in c for c in chunks)
    assert any("[CONCLUSAO]" in c for c in chunks)


def test_chunk_por_secao_vazio():
    assert _chunk_por_secao("", max_chars=100) == []


def test_chunk_por_secao_sem_titulo():
    texto = "Apenas um paragrafo sem titulos detectados."
    chunks = _chunk_por_secao(texto, max_chars=100)
    assert len(chunks) >= 1
