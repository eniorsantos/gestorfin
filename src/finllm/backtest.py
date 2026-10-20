"""Backtest point-in-time (roadmap Fase 6).

Simula uma estratégia baseada nos sinais dos agentes (fundamentalista/técnico)
sobre preços históricos. Usa vectorbt quando disponível; caso contrário, uma
implementação nativa simples. Resultado é registrável em `backtest_resultados`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

try:  # dependência opcional
    import vectorbt as vbt  # type: ignore
except Exception:  # noqa: BLE001
    vbt = None  # type: ignore

try:
    import pandas as pd
except Exception:  # noqa: BLE001
    pd = None  # type: ignore


@dataclass
class ResultadoBacktest:
    nome: str
    ticker: str
    periodo_ini: date
    periodo_fim: date
    retorno_total: float
    sharpe: float
    drawdown_max: float
    n_operacoes: int
    parametros: dict = field(default_factory=dict)
    curva: list[tuple[str, float]] = field(default_factory=list)


def _retornos_da_curva(precos: list[float]) -> list[float]:
    if len(precos) < 2:
        return []
    return [(precos[i] / precos[i - 1]) - 1 for i in range(1, len(precos))]


def _sharpe(retornos: list[float], rf_diaria: float = 0.0) -> float:
    if not retornos:
        return 0.0
    media = sum(retornos) / len(retornos)
    var = sum((r - media) ** 2 for r in retornos) / max(len(retornos) - 1, 1)
    desvio = var ** 0.5
    if desvio == 0:
        return 0.0
    # anualização aprox. 252 pregões
    return ((media - rf_diaria) / desvio) * (252 ** 0.5)


def _drawdown_max(precos: list[float]) -> float:
    pico = 0.0
    max_dd = 0.0
    for p in precos:
        if p > pico:
            pico = p
        dd = (pico - p) / pico if pico > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _backtest_nativo(
    ticker: str,
    precos: list[float],
    sinais: list[int],  # 1 compra, -1 venda, 0 neutro
    datas: list[str],
    capital_inicial: float = 100000.0,
    comissao: float = 0.001,
) -> ResultadoBacktest:
    """Backtest simples: entra na posição segundo o sinal do dia anterior."""
    capital = capital_inicial
    posicao = 0  # quantidade de ações
    operacoes = 0
    curva = []
    valor_anterior = capital_inicial

    for i in range(1, len(precos)):
        sinal_anterior = sinais[i - 1]
        preco_atual = precos[i]
        preco_anterior = precos[i - 1]

        # Rebalanceia no início do dia com base no sinal do dia anterior
        if sinal_anterior == 1 and posicao == 0:
            # compra tudo
            qtd = (capital * (1 - comissao)) / preco_atual
            posicao = qtd
            capital = 0.0
            operacoes += 1
        elif sinal_anterior == -1 and posicao > 0:
            # vende tudo
            capital = posicao * preco_atual * (1 - comissao)
            posicao = 0.0
            operacoes += 1

        valor = capital + posicao * preco_atual
        curva.append((datas[i] if i < len(datas) else "", round(valor, 2)))
        valor_anterior = valor

    valor_final = capital + posicao * (precos[-1] if precos else 0)
    retorno_total = (valor_final / capital_inicial) - 1

    # Reconstroi preços da curva para drawdown
    precos_curva = [c[1] for c in curva]
    dd_max = _drawdown_max(precos_curva) if precos_curva else 0.0

    retornos = _retornos_da_curva([c[1] for c in curva])
    sharpe = _sharpe(retornos)

    return ResultadoBacktest(
        nome="sinais_agentes",
        ticker=ticker,
        periodo_ini=date.fromisoformat(datas[0]) if datas else date.today(),
        periodo_fim=date.fromisoformat(datas[-1]) if datas else date.today(),
        retorno_total=retorno_total,
        sharpe=sharpe,
        drawdown_max=dd_max,
        n_operacoes=operacoes,
        parametros={"capital_inicial": capital_inicial, "comissao": comissao},
        curva=curva,
    )


def run_backtest(
    nome: str,
    ticker: str,
    precos: list[float],
    datas: list[str],
    sinais: list[int],
    capital_inicial: float = 100000.0,
    comissao: float = 0.001,
    use_vectorbt: bool = False,
) -> ResultadoBacktest:
    """Executa o backtest. `sinais[i]` é o sinal para o dia i (1 compra, -1 venda, 0 neutro)."""
    if use_vectorbt and vbt is not None and pd is not None:
        import pandas as _pd

        df = _pd.DataFrame({"close": precos}, index=_pd.to_datetime(datas))
        # Sinais: 1 = longo, 0 = fora
        entradas = [1 if s == 1 else 0 for s in sinais]
        saídas = [1 if s == -1 else 0 for s in sinais]
        pf = vbt.Portfolio.from_signals(
            df["close"],
            entries=entradas,
            exits=saídas,
            init_cash=capital_inicial,
            fees=comissao,
            freq="D",
        )
        retorno_total = float(pf.total_return().iloc[0] if hasattr(pf.total_return(), "iloc") else pf.total_return())
        # Sharpe aproximado via retornos do portfolio
        rets = pf.returns()
        if hasattr(rets, "dropna"):
            rets_list = rets.dropna().tolist()
        else:
            rets_list = list(rets)
        sharpe = _sharpe(rets_list)
        curva = [(str(d.date()), round(float(v), 2)) for d, v in pf.value().items()]
        drawdown = pf.max_drawdown()
        dd_max = float(drawdown.iloc[0] if hasattr(drawdown, "iloc") else drawdown)
        n_ops = int(pf.trades.count() if hasattr(pf.trades, "count") else len([s for s in sinais if s != 0]))

        return ResultadoBacktest(
            nome=nome,
            ticker=ticker,
            periodo_ini=_pd.to_datetime(datas[0]).date() if datas else date.today(),
            periodo_fim=_pd.to_datetime(datas[-1]).date() if datas else date.today(),
            retorno_total=retorno_total,
            sharpe=sharpe,
            drawdown_max=dd_max,
            n_operacoes=n_ops,
            parametros={"capital_inicial": capital_inicial, "comissao": comissao, "uso_vectorbt": True},
            curva=curva,
        )

    return _backtest_nativo(ticker, precos, sinais, datas, capital_inicial, comissao)
