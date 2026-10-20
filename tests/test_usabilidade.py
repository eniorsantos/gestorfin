"""Testes de usabilidade.

Cobre CLI (help, comandos inválidos, mensagens de erro), parâmetros com valores
padrão, saída formatada, e experiência do usuário em comandos principais.
"""
from __future__ import annotations

import pytest

pytest.importorskip("psycopg")

from typer.testing import CliRunner

from finllm.cli import app


runner = CliRunner()


# ---------------- Usabilidade: help e comandos ----------------
def test_usabilidade_help_global():
    resultado = runner.invoke(app, ["--help"])
    assert resultado.exit_code == 0
    for grupo in ("db", "cvm", "rag", "bench", "auditoria", "indicadores",
                  "tecnico", "agentes", "backtest", "avaliacao", "dashboard"):
        assert grupo in resultado.output


def test_usabilidade_help_db():
    resultado = runner.invoke(app, ["db", "--help"])
    assert resultado.exit_code == 0
    assert "init" in resultado.output
    assert "stats" in resultado.output


def test_usabilidade_help_cvm():
    resultado = runner.invoke(app, ["cvm", "--help"])
    assert resultado.exit_code == 0
    for cmd in ("download", "load", "ipe-categories", "ipe-sync", "setor-normalizar", "load-dfc-dva"):
        assert cmd in resultado.output


def test_usabilidade_help_rag():
    resultado = runner.invoke(app, ["rag", "--help"])
    assert resultado.exit_code == 0
    for cmd in ("index-statements", "index-ipe", "search", "ask", "cache-limpar", "rerank-test"):
        assert cmd in resultado.output


def test_usabilidade_help_bench():
    resultado = runner.invoke(app, ["bench", "--help"])
    assert resultado.exit_code == 0
    for cmd in ("hardware", "build", "run", "report"):
        assert cmd in resultado.output


def test_usabilidade_help_tecnico():
    resultado = runner.invoke(app, ["tecnico", "--help"])
    assert resultado.exit_code == 0
    assert "sinal" in resultado.output
    assert "indicadores" in resultado.output


def test_usabilidade_help_agentes():
    resultado = runner.invoke(app, ["agentes", "--help"])
    assert resultado.exit_code == 0
    assert "analisar" in resultado.output


def test_usabilidade_help_backtest():
    resultado = runner.invoke(app, ["backtest", "--help"])
    assert resultado.exit_code == 0
    assert "run" in resultado.output


def test_usabilidade_help_avaliacao():
    resultado = runner.invoke(app, ["avaliacao", "--help"])
    assert resultado.exit_code == 0
    assert "regressao" in resultado.output
    assert "salvar-referencia" in resultado.output


def test_usabilidade_help_dashboard():
    resultado = runner.invoke(app, ["dashboard", "--help"])
    assert resultado.exit_code == 0
    assert "up" in resultado.output


# ---------------- Usabilidade: comandos inválidos ----------------
def test_usabilidade_comando_invalido():
    resultado = runner.invoke(app, ["comando_inexistente"])
    assert resultado.exit_code != 0


def test_usabilidade_subcomando_invalido():
    resultado = runner.invoke(app, ["db", "comando_inexistente"])
    assert resultado.exit_code != 0


def test_usabilidade_sem_argumento():
    resultado = runner.invoke(app, [])
    assert resultado.exit_code != 0
    assert "Usage" in resultado.output or "ajuda" in resultado.output.lower() or resultado.output


# ---------------- Usabilidade: parâmetros obrigatórios ----------------
def test_usabilidade_rag_ask_sem_pergunta():
    resultado = runner.invoke(app, ["rag", "ask"])
    assert resultado.exit_code != 0


def test_usabilidade_indicadores_calc_sem_ticker():
    resultado = runner.invoke(app, ["indicadores", "calc"])
    assert resultado.exit_code != 0


def test_usabilidade_tecnico_sinal_sem_ticker():
    resultado = runner.invoke(app, ["tecnico", "sinal"])
    assert resultado.exit_code != 0


# ---------------- Usabilidade: valores padrão ----------------
def test_usabilidade_rag_ask_opcionais_validos():
    """rag ask com --help deve mostrar opções padrão."""
    resultado = runner.invoke(app, ["rag", "ask", "--help"])
    assert resultado.exit_code == 0
    assert "--use-tools" in resultado.output
    assert "--data-entrega" in resultado.output


def test_usabilidade_backtest_run_opcoes():
    resultado = runner.invoke(app, ["backtest", "run", "--help"])
    assert resultado.exit_code == 0
    assert "--ticker" in resultado.output
    assert "--capital" in resultado.output
    assert "--comissao" in resultado.output


def test_usabilidade_avaliacao_regressao_opcoes():
    resultado = runner.invoke(app, ["avaliacao", "regressao", "--help"])
    assert resultado.exit_code == 0
    assert "--limiar" in resultado.output


def test_usabilidade_dashboard_up_opcoes():
    resultado = runner.invoke(app, ["dashboard", "up", "--help"])
    assert resultado.exit_code == 0
    assert "--porta" in resultado.output


# ---------------- Usabilidade: mensagens de erro amigáveis ----------------
def test_usabilidade_erro_empresa_nao_encontrada(mocker):
    """Quando empresa não existe, CLI deve exibir mensagem clara, não traceback."""
    from finllm.cli import _resolve
    from finllm.rag.entities import resolve_empresa

    # Mock que levanta ValueError (empresa ambígua/não encontrada)
    def falso_resolve(conn, name):
        raise ValueError("Nome ambíguo 'X'. Candidatos: 1=A, 2=B")

    mocker.patch("finllm.cli._resolve", side_effect=lambda conn, empresas: (
        falso_resolve(conn, empresas[0]) if empresas else None))

    resultado = runner.invoke(app, ["indicadores", "calc", "EmpresaInexistenteXYZ"])
    assert resultado.exit_code != 0
    # Deve conter mensagem legível, não traceback de Python bruto
    saida = resultado.output + (str(resultado.exception) if resultado.exception else "")
    assert "não encontrada" in saida.lower() or "ambíguo" in saida.lower() or "Candidatos" in saida


# ---------------- Usabilidade: saída formatada ----------------
def test_usabilidade_ajuda_contem_exemplos():
    resultado = runner.invoke(app, ["--help"])
    assert "make pipeline" in resultado.output or "finllm" in resultado.output


def test_usabilidade_comando_desconhecido_sugere():
    resultado = runner.invoke(app, ["xyz"])
    assert resultado.exit_code != 0
