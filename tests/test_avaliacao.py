"""Testes da avaliação contínua/regressão (Fase 8)."""
import json
import tempfile
from pathlib import Path

from finllm.avaliacao import (
    carregar_referencia,
    comparar_com_referencia,
    gerar_relatorio_regressao,
    salvar_referencia,
    MetricaReferencia,
)


def test_salvar_e_carregar_referencia(tmp_path):
    saida = tmp_path / "ref.json"
    resumo = [{"modelo": "qwen3:8b", "rag_fact": 0.8, "json_valid": 1.0,
               "resp_errada_confiante": 0.0}]
    salvar_referencia(resumo, saida)
    ref = carregar_referencia(saida)
    chave = "qwen3:8b::rag_fact"
    assert chave in ref
    assert ref[chave].acuracia == 0.8


def test_comparar_sem_regressao():
    ref = {"m1::rag_fact": MetricaReferencia("m1", "rag_fact", 0.8, 0.7, 0.9, 1.0, 0.0)}
    resumo = [{"modelo": "m1", "rag_fact": 0.85}]
    res = comparar_com_referencia(resumo, ref)
    assert not res[0].regressou


def test_comparar_com_regressao():
    ref = {"m1::rag_fact": MetricaReferencia("m1", "rag_fact", 0.8, 0.7, 0.9, 1.0, 0.0)}
    resumo = [{"modelo": "m1", "rag_fact": 0.7}]  # queda 0.1 > 0.05
    res = comparar_com_referencia(resumo, ref, limiar_queda=0.05)
    assert res[0].regressou


def test_gerar_relatorio(tmp_path):
    ref = {"m1::rag_fact": MetricaReferencia("m1", "rag_fact", 0.8, 0.7, 0.9, 1.0, 0.0)}
    resumo = [{"modelo": "m1", "rag_fact": 0.7}]
    res = comparar_com_referencia(resumo, ref, limiar_queda=0.05)
    saida = tmp_path / "report.md"
    gerar_relatorio_regressao(res, saida)
    txt = saida.read_text(encoding="utf-8")
    assert "Regressão" in txt or "regressão" in txt.lower() or "Sem regressões" in txt
