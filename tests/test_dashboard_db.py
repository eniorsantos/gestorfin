"""Testes do módulo db do dashboard (sem exigir Postgres real)."""
from finllm.dashboard import db as dash_db


def test_estatisticas_gerais_sem_banco():
    # Sem psycopg/banco, conectar retorna None e estatísticas são zeros
    stats = dash_db.estatisticas_gerais()
    assert stats == {
        "empresas": 0,
        "demonstacoes": 0,
        "chunks": 0,
        "consultas": 0,
        "alertas": 0,
    }


def test_listar_empresas_sem_banco():
    assert dash_db.listar_empresas() == []


def test_listar_setores_sem_banco():
    assert dash_db.listar_setores() == []


def test_listar_consultas_sem_banco():
    assert dash_db.listar_consultas() == []


def test_listar_alertas_sem_banco():
    assert dash_db.listar_alertas() == []


def test_criar_alerta_sem_banco():
    assert dash_db.criar_alerta("PETR4", "preco", ">= 30", 30.0) == -1


def test_indicadores_ticker_sem_banco():
    assert dash_db.indicadores_ticker("PETROBRAS") == {}
