"""Testes de carga e stress (load testing).

Simula múltiplas consultas sequenciais e concorrentes, volume de chunks,
e geração de relatórios de benchmark para medir throughput e estabilidade.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pytest

from finllm.auditoria import registrar_consulta, listar_consultas
from finllm.cvm.load import transform_frame, normalizar_setores
from finllm.rag.text import chunk_lines, chunk_text
from finllm.bench.metrics import score_rag, wilson, percentile, within
from finllm.bench.report import summarize
from finllm.fundamentalista import calcular_indicadores


class _Col:
    def __init__(self, nome):
        self.name = nome


class _FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []
        self.description = [_Col(n) for n in ("id", "pergunta", "modelo", "temperatura",
                                              "seed", "num_ctx", "filtros", "chunk_ids",
                                              "resposta", "validacao", "criado_em")]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q, args=None):
        self.executed.append((q, args))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows

    def executemany(self, q, args_list):
        self.executed.append((q, args_list))


class _FakeConn:
    def __init__(self, cur):
        self.cur = cur
        self.committed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _base_row():
    return dict(
        CNPJ_CIA="1", DENOM_CIA="EMPRESA X", CD_CVM="123", MOEDA="REAL",
        ESCALA_MOEDA="MIL", DT_REFER="2023-12-31", DT_INI_EXERC="2023-01-01",
        DT_FIM_EXERC="2023-12-31", CD_CONTA="3.01", DS_CONTA="Receita",
        ST_CONTA_FIXA="S", VERSAO="1", ORDEM_EXERC="ÚLTIMO", VL_CONTA="100.0",
    )


def _df_n(n: int):
    import pandas as pd

    rows = []
    for i in range(n):
        r = _base_row()
        r["CD_CVM"] = str(100 + i)
        r["DENOM_CIA"] = f"EMPRESA {i}"
        r["CD_CONTA"] = f"3.{i % 5:02d}"
        r["VL_CONTA"] = str(float(i) * 1000)
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------- Carga: transform_frame ----------------
def test_carga_transform_frame_volume():
    """Processar milhares de linhas deve ser rápido e não falhar."""
    import pandas as pd

    df = _df_n(5000)
    out = transform_frame(df, tipo_doc="DFP", demonstracao="DRE", consolidacao="con")
    assert len(out) == 5000
    assert set(out.columns) == set(["cd_cvm", "cnpj", "denom", "tipo_doc", "demonstracao",
                                     "consolidacao", "dt_refer", "dt_ini_exerc", "dt_fim_exerc",
                                     "versao", "moeda", "escala", "cd_conta", "ds_conta",
                                     "vl_conta", "st_conta_fixa"])


def test_carga_chunk_lines_volume():
    """Quebrar tabela grande em chunks não deve perder linhas."""
    header = "Empresa: X | DFP | Valores em R$ mil"
    lines = [f"3.{i:02d} | Conta {i} | {i * 1000}" for i in range(2000)]
    chunks = chunk_lines(header, lines, max_chars=500)
    total_linhas = sum(c.count("\n") for c in chunks)
    assert total_linhas == len(lines)
    assert all(c.startswith(header) for c in chunks)


def test_carga_chunk_text_volume():
    """Texto grande deve ser fragmentado respeitando o limite."""
    texto = "\n\n".join(f"Paragrafo {i}. " + "x " * 200 for i in range(500))
    chunks = chunk_text(texto, max_chars=1000)
    assert all(len(c) <= 1000 for c in chunks)


# ---------------- Carga: concorrência (auditoria) ----------------
def _conn_auditoria(retornar_id=True, listar_rows=None):
    cur = _FakeCursor()
    cur.fetchone = lambda: (1,) if retornar_id else None
    cur.fetchall = lambda: listar_rows or []
    return _FakeConn(cur), cur


def test_carga_auditoria_sequencial():
    import finllm.auditoria as mod
    orig = mod._connect
    conn, cur = _conn_auditoria(listar_rows=[
        (1, "p", "m", 0.0, 42, 8192, "{}", "[]", "{}", "{}", "2024-01-01")
    ])
    mod._connect = lambda: conn
    try:
        t0 = time.perf_counter()
        for i in range(200):
            registrar_consulta(pergunta=f"q{i}", modelo="m", filtros={}, chunk_ids=[],
                               resposta={}, validacao={})
        dt = time.perf_counter() - t0
        assert dt < 5.0  # 200 inserts mock em menos de 5s
        assert cur.executed and conn.committed
        lista = listar_consultas(limit=10)
        assert len(lista) == 1
    finally:
        mod._connect = orig


def test_carga_auditoria_concorrente():
    import finllm.auditoria as mod
    orig = mod._connect
    conn, cur = _conn_auditoria(listar_rows=[])
    mod._connect = lambda: conn
    try:
        def trabalho(i):
            return registrar_consulta(pergunta=f"q{i}", modelo="m", filtros={}, chunk_ids=[],
                                      resposta={}, validacao={})

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as ex:
            futuros = [ex.submit(trabalho, i) for i in range(100)]
            resultados = [f.result() for f in as_completed(futuros)]
        dt = time.perf_counter() - t0
        assert len(resultados) == 100
        assert all(r == 1 for r in resultados)
        assert conn.committed
        assert dt < 10.0
    finally:
        mod._connect = orig


# ---------------- Carga: métricas e relatório ----------------
def test_carga_metricas_volume():
    """Pontuação de muitos itens deve ser consistente."""
    itens = []
    for i in range(1000):
        gold = {"nao_encontrado": False, "valor": float(i), "gold_hashes": ["h"]}
        ctx = [{"hash": "h0"}, {"hash": "h"}]
        parsed = {"nao_encontrado": False, "valor": float(i), "citacoes": [2]}
        itens.append(score_rag("rag_fact", gold, parsed, ctx))
    assert all(r["correct"] for r in itens)


def test_carga_percentil_wilson():
    """Cálculo estatístico em escala."""
    xs = list(range(1, 10001))
    assert percentile(xs, 0.5) == 5000.5
    lo, hi = wilson(800, 1000)
    assert 0.75 < lo < 0.85
    assert 0.75 < hi < 0.95


# ---------------- Carga: indicadores ----------------
def test_carga_indicadores_volume():
    pytest.importorskip("psycopg")
    import finllm.fundamentalista as mod
    valores = {"3.01": 1000.0, "3.05": 200.0, "3.11": 100.0, "1": 1000.0,
               "2.03": 200.0, "2.02.01": 150.0, "1.01.01": 50.0}
    orig = mod._busca_conta
    mod._busca_conta = lambda conn, cd, dt, conta, cons="con": valores.get(conta)
    try:
        t0 = time.perf_counter()
        for i in range(500):
            ind = calcular_indicadores(i + 100, date(2023, 12, 31))
            assert ind.pl == 0.5
        dt = time.perf_counter() - t0
        assert dt < 5.0
    finally:
        mod._busca_conta = orig


# ---------------- Carga: normalização setor ----------------
def test_carga_normalizar_setores_volume():
    pytest.importorskip("psycopg")
    import finllm.cvm.load as mod
    rows = [(100 + i, f"EMP {i}", "BANCOS" if i % 2 == 0 else "SEGUROS")
            for i in range(2000)]
    cur = _FakeCursor(rows)
    conn = _FakeConn(cur)
    orig = mod.connect
    mod.connect = lambda: conn
    try:
        t0 = time.perf_counter()
        n = normalizar_setores(conn)
        dt = time.perf_counter() - t0
        assert n == 2000
        assert conn.committed
        assert dt < 5.0
    finally:
        mod.connect = orig
