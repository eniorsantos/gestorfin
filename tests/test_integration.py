"""Testes de integração com mock de banco (sem exigir Postgres real)."""
from __future__ import annotations

from datetime import date

import pytest

from finllm.auditoria import registrar_consulta, listar_consultas
from finllm.cvm.load import normalizar_setores
from finllm.fundamentalista import calcular_indicadores, f_score_piotroski
from finllm.rag.sql_direct import (
    _conta_da_pergunta,
    consultar_valor_direto,
    tentar_resposta_direta,
)
from finllm.rag.tools import TOOLS_REAIS, TOOL_DEFINICOES
from finllm.bench.tasks import executar_tool


class _CtxConn:
    def __init__(self, cur):
        self.cur = cur
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []
        self.lastrowid = None

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


class FakeConn(_CtxConn):
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj


def _conn_with(rows):
    cur = FakeCursor(rows)
    return FakeConn(cur), cur


class _AuditoriaCursor:
    def __init__(self, retornar_id=True, listar_rows=None):
        self.retornar_id = retornar_id
        self.listar_rows = listar_rows or []
        self.call_count = 0
        class _Col:
            def __init__(self, nome):
                self.name = nome
        self.description = [_Col(n) for n in ("id", "pergunta", "modelo", "temperatura",
                                              "seed", "num_ctx", "filtros", "chunk_ids",
                                              "resposta", "validacao", "criado_em")]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q, args=None):
        self.call_count += 1

    def fetchone(self):
        if self.retornar_id:
            self.retornar_id = False
            return (1,)
        return None

    def fetchall(self):
        return self.listar_rows


class _AuditoriaConn(_CtxConn):
    pass


def test_auditoria_registrar_e_listar():
    cur = _AuditoriaCursor(listar_rows=[
        (1, "Qual a receita?", "qwen3:8b", 0.0, 42, 8192,
         '{"cd_cvms":[9512]}', '[]', '{"valor":100.0}', '{"ok":true}', "2024-01-01")
    ])
    conn = _AuditoriaConn(cur)

    import finllm.auditoria as mod
    orig_connect = mod._connect
    mod._connect = lambda: conn
    try:
        nid = registrar_consulta(
            pergunta="Qual a receita?", modelo="qwen3:8b",
            filtros={"cd_cvms": [9512]}, chunk_ids=[], resposta={"valor": 100.0},
            validacao={"ok": True},
        )
        assert nid == 1
        assert cur.call_count == 1
        assert conn.committed
        lista = listar_consultas(limit=5)
        assert len(lista) == 1
        assert lista[0]["pergunta"] == "Qual a receita?"
    finally:
        mod._connect = orig_connect


def test_normalizar_setores():
    rows = [
        (9512, "PETROBRAS", "PETRÓLEO, GÁS E BIOCOMBUSTÍVEIS"),
        (4170, "VALE", "MINERAÇÃO"),
        (5410, "WEG", "MAQUINAS E EQUIPAMENTOS"),
    ]
    conn, cur = _conn_with(rows)
    n = normalizar_setores(conn)
    assert n == 3
    assert conn.committed
    assert any("setores" in q for q, _ in cur.executed)


def test_calcular_indicadores():
    """Testa cálculo de indicadores com _connect mockeado."""
    class _FakeCur:
        def __init__(self, valor_por_conta):
            self.valor_por_conta = valor_por_conta
            self.call_count = 0
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, q, args=None):
            self.call_count += 1
        def fetchone(self):
            return None
    import finllm.fundamentalista as mod
    valores = {"3.01": 1000.0, "3.05": 200.0, "3.11": 100.0, "1": 1000.0,
               "2.03": 200.0, "2.02.01": 150.0, "1.01.01": 50.0}
    cur = _FakeCur(valores)
    conn = _CtxConn(cur)

    orig_connect = mod._connect
    orig_busca = mod._busca_conta
    mod._connect = lambda: conn
    def fake_busca(conn, cd_cvm, dt_refer, conta, consolidacao="con"):
        return valores.get(conta)
    mod._busca_conta = fake_busca
    try:
        ind = calcular_indicadores(123, date(2023, 12, 31))
        assert ind.pl == 0.5  # 100/200
        assert ind.roe == 0.5
        assert ind.roic == 0.2  # 200/1000
        assert ind.divida_liquida_ebitda == 0.5  # (150-50)/200
    finally:
        mod._connect = orig_connect
        mod._busca_conta = orig_busca


def test_conta_da_pergunta():
    assert _conta_da_pergunta("Qual a receita líquida da WEG?") == "3.01"
    assert _conta_da_pergunta("Qual o lucro da Vale?") == "3.11"
    assert _conta_da_pergunta("Qual o patrimônio líquido?") == "2.03"
    assert _conta_da_pergunta("Qual o ebit?") == "3.05"
    assert _conta_da_pergunta("Pergunta sem conta") is None


def test_consultar_valor_direto():
    conn, cur = _conn_with([(1234567.0,)])
    import finllm.rag.sql_direct as mod
    orig = mod._connect
    mod._connect = lambda: conn
    try:
        vl = consultar_valor_direto(9512, date(2023, 12, 31), "3.01")
        assert vl == 1234567.0
    finally:
        mod._connect = orig


def test_tentar_resposta_direta_sem_conta():
    assert tentar_resposta_direta("Pergunta genérica", 9512) is None
    assert tentar_resposta_direta("Qual a receita?", None) is None


def test_tools_reais_estrutura():
    assert "get_indicadores" in TOOLS_REAIS
    assert "buscar_documentos" in TOOLS_REAIS
    assert "get_cotacoes" in TOOLS_REAIS
    assert "get_macro" in TOOLS_REAIS
    assert "get_indicadores_tecnicos" in TOOLS_REAIS
    assert "get_sinal_tecnico" in TOOLS_REAIS
    assert len(TOOL_DEFINICOES) == 6


def test_executar_tool_desconhecida():
    resultado = executar_tool("nao_existe", {})
    assert "erro" in resultado


class _HitCursor:
    def __init__(self, sql_captura):
        self.sql_captura = sql_captura
        self.description = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q, params=None):
        self.sql_captura.append((q, params or {}))

    def fetchall(self):
        return []


class _ConnCapture:
    def __init__(self):
        self.chamadas = []

    def cursor(self, row_factory=None):
        return _HitCursor(self.chamadas)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def commit(self):
        pass


def test_hybrid_search_data_entrega_max():
    pytest.importorskip("psycopg")
    from finllm.rag.retrieve import hybrid_search

    captura_sql = []

    class _HitCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, q, params=None):
            captura_sql.append((q, params or {}))

        def fetchall(self):
            return []

    class _ConnCapture:
        def cursor(self, row_factory=None):
            return _HitCursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def commit(self):
            pass

    class FakeClient:
        def embed(self, modelo, textos):
            return [[0.1] * 1024]

    conn = _ConnCapture()
    hybrid_search(conn, FakeClient(), "receita WEG", data_entrega_max=date(2023, 12, 31))
    sql, params = captura_sql[0]
    assert "dt_entrega" in sql
    assert params.get("entrega_max") == date(2023, 12, 31)
