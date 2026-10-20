"""Testes do motor técnico (Fase 4)."""
from datetime import date, timedelta

from finllm.tecnico import Cotacao, calcular_indicadores, gerar_sinais


def _cotacoes(n: int, base: float = 10.0, passo: float = 0.1):
    hoje = date.today()
    return [Cotacao("PETR4", hoje - timedelta(days=n - 1 - i),
                    base + i * passo, base + i * passo + 0.5,
                    base + i * passo - 0.5, base + i * passo, 1000)
            for i in range(n)]


def test_calcular_indicadores():
    cotacoes = _cotacoes(60)
    ind = calcular_indicadores(cotacoes)
    assert ind.ticker == "PETR4"
    assert ind.sinal in ("compra", "neutro", "venda")
    assert ind.rsi_14 is not None
    assert ind.sma_20 is not None
    assert ind.sma_50 is not None


def test_gerar_sinais():
    cotacoes = _cotacoes(60)
    sinais = gerar_sinais("PETR4", cotacoes)
    assert isinstance(sinais, list)
