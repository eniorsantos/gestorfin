"""Testes de desempenho.

Mede tempo de execução, uso de memória e throughput de operações críticas:
transform_frame, chunking, guardrails, métricas do benchmark, relatório,
geração de dataset e consultas simuladas.
"""
from __future__ import annotations

import time
import tracemalloc

import pytest

from finllm.cvm.load import transform_frame
from finllm.rag.text import chunk_lines, chunk_text
from finllm.rag.guardrails import validate_numbers, numbers_in
from finllm.bench.metrics import score_rag, score_classif, score_tool, wilson, within
from finllm.bench.report import summarize
from finllm.bench.tasks import builtin_items


def _df_n(n: int):
    import pandas as pd

    base = dict(CNPJ_CIA="1", DENOM_CIA="EMPRESA X", CD_CVM="123", MOEDA="REAL",
                ESCALA_MOEDA="MIL", DT_REFER="2023-12-31", DT_INI_EXERC="2023-01-01",
                DT_FIM_EXERC="2023-12-31", CD_CONTA="3.01", DS_CONTA="Receita",
                ST_CONTA_FIXA="S", VERSAO="1", ORDEM_EXERC="ÚLTIMO", VL_CONTA="100.0")
    rows = []
    for i in range(n):
        r = dict(base)
        r["CD_CVM"] = str(100 + i)
        r["DENOM_CIA"] = f"EMPRESA {i}"
        r["VL_CONTA"] = str(float(i) * 1000)
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------- Desempenho: transform_frame ----------------
def test_desempenho_transform_frame_tempo():
    import pandas as pd

    df = _df_n(10000)
    t0 = time.perf_counter()
    out = transform_frame(df, tipo_doc="DFP", demonstracao="DRE", consolidacao="con")
    dt = time.perf_counter() - t0
    assert len(out) == 10000
    assert dt < 10.0  # deve processar 10k linhas em < 10s


def test_desempenho_transform_frame_memoria():
    import pandas as pd

    df = _df_n(5000)
    tracemalloc.start()
    out = transform_frame(df, tipo_doc="DFP", demonstracao="DRE", consolidacao="con")
    atual, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # Pico de memória deve ser razoável (< 200 MB para 5k linhas)
    assert pico < 200 * 1024 * 1024


# ---------------- Desempenho: chunking ----------------
def test_desempenho_chunk_lines_tempo():
    header = "Empresa: X | DFP | Valores em R$ mil"
    lines = [f"3.{i:02d} | Conta {i} | {i * 1000}" for i in range(5000)]
    t0 = time.perf_counter()
    chunks = chunk_lines(header, lines, max_chars=500)
    dt = time.perf_counter() - t0
    assert len(chunks) > 1
    assert dt < 5.0


def test_desempenho_chunk_text_tempo():
    texto = "\n\n".join(f"Paragrafo {i}. " + "conteudo " * 100 for i in range(1000))
    t0 = time.perf_counter()
    chunks = chunk_text(texto, max_chars=1000)
    dt = time.perf_counter() - t0
    assert len(chunks) > 1
    assert dt < 5.0


# ---------------- Desempenho: guardrails ----------------
def test_desempenho_guardrails_volume():
    ctx = [f"3.{i:02d} | Conta {i} | {i * 1000}" for i in range(100)]
    resposta = " ".join(f"valor {i * 1000} [{i % 100 + 1}]" for i in range(50))
    t0 = time.perf_counter()
    v = validate_numbers(resposta, ctx)
    dt = time.perf_counter() - t0
    assert dt < 2.0


def test_desempenho_numbers_in_volume():
    texto = " ".join(f"numero {i} [1]" for i in range(1000))
    t0 = time.perf_counter()
    nums = numbers_in(texto)
    dt = time.perf_counter() - t0
    assert len(nums) == 1000
    assert dt < 1.0


# ---------------- Desempenho: métricas do benchmark ----------------
def test_desempenho_score_rag_volume():
    gold = {"nao_encontrado": False, "valor": 1000.0, "gold_hashes": ["h1"]}
    ctx = [{"hash": "h0"}, {"hash": "h1"}]
    parsed = {"nao_encontrado": False, "valor": 1003.0, "citacoes": [2]}
    t0 = time.perf_counter()
    for _ in range(10000):
        score_rag("rag_fact", gold, parsed, ctx)
    dt = time.perf_counter() - t0
    assert dt < 5.0


def test_desempenho_wilson_volume():
    t0 = time.perf_counter()
    for n in range(1, 5001):
        wilson(n // 2, n)
    dt = time.perf_counter() - t0
    assert dt < 2.0


# ---------------- Desempenho: relatório do benchmark ----------------
def test_desempenho_summarize_volume():
    import json
    import tempfile
    from pathlib import Path

    recs = [{"model": "m1", "task": "_warmup", "item_id": "w", "error": None,
             "wall_s": 1.0, "load_s": 0.5}]
    for i in range(2000):
        recs.append({"model": "m1", "task": "rag_fact", "item_id": f"f{i}",
                     "valid": True, "correct": i % 2 == 0, "answered": True,
                     "cite_ok": True, "error": None, "wall_s": 1.0,
                     "gen_tps": 40.0, "prompt_tps": 900.0})
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "run"
        p.mkdir()
        (p / "results.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
        (p / "model_meta.json").write_text(json.dumps({"m1": {}}))
        (p / "run_config.json").write_text(json.dumps({}))
        t0 = time.perf_counter()
        summary, detail = summarize(p)
        dt = time.perf_counter() - t0
        assert len(summary) == 1
        assert len(detail) == 1
        assert dt < 5.0


# ---------------- Desempenho: builtin_items ----------------
def test_desempenho_builtin_items():
    t0 = time.perf_counter()
    itens = builtin_items()
    dt = time.perf_counter() - t0
    assert len(itens) == 18  # 10 classif + 8 tools
    assert dt < 0.5


# ---------------- Desempenho: classificacao e tools ----------------
def test_desempenho_score_classif_volume():
    t0 = time.perf_counter()
    for i in range(10000):
        score_classif("positivo", {"sentimento": "Positivo"})
    dt = time.perf_counter() - t0
    assert dt < 2.0


def test_desempenho_score_tool_volume():
    exp = {"name": "get_cotacoes", "args": {"ticker": "PETR4", "periodo": "6m"}}
    call = [{"function": {"name": "get_cotacoes", "arguments": {"ticker": "petr4", "periodo": "6m"}}}]
    t0 = time.perf_counter()
    for _ in range(10000):
        score_tool(exp, call)
    dt = time.perf_counter() - t0
    assert dt < 2.0


# ---------------- Desempenho: within ----------------
def test_desempenho_within_volume():
    n = 100000
    t0 = time.perf_counter()
    for i in range(n):
        within(i * 0.001, i * 0.001, rel=0.005)
    dt = time.perf_counter() - t0
    assert dt < 3.0
