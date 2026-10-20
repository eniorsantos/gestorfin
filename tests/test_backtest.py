"""Testes do backtest (Fase 6)."""
from datetime import date

from finllm.backtest import run_backtest, _sharpe, _drawdown_max


def test_sharpe():
    assert _sharpe([0.01, 0.02, -0.01]) > 0
    assert _sharpe([]) == 0.0


def test_drawdown_max():
    assert abs(_drawdown_max([100, 110, 90, 120]) - 0.1818) < 0.001  # pico 110, fundo 90 -> 20/110


def test_run_backtest_nativo():
    precos = [10, 11, 12, 11, 13, 14, 13, 15]
    datas = [f"2024-01-{i:02d}" for i in range(1, 9)]
    sinais = [0, 1, 1, -1, 0, 1, 1, 0]
    res = run_backtest("test", "PETR4", precos, datas, sinais)
    assert res.ticker == "PETR4"
    assert -1 <= res.retorno_total <= 1
    assert res.n_operacoes >= 0
    assert len(res.curva) == len(precos) - 1
