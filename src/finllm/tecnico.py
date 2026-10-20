"""Motor técnico (roadmap Fase 4).

OHLCV, indicadores técnicos (SMA, EMA, RSI, MACD, Bollinger, suportes/resistências)
e geração de sinais. Implementado em código determinístico; o LLM consome via tools.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

try:  # dependência opcional
    import pandas as pd
except Exception:  # noqa: BLE001
    pd = None  # type: ignore


@dataclass
class Cotacao:
    ticker: str
    data: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class IndicadoresTecnicos:
    ticker: str
    data: date
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    suporte: Optional[float] = None
    resistencia: Optional[float] = None
    sinal: str = "neutro"


def _ma(series: list[float], janela: int) -> list[Optional[float]]:
    if pd is not None:
        s = pd.Series(series)
        return s.rolling(janela).mean().tolist()
    out: list[Optional[float]] = []
    for i in range(len(series)):
        if i + 1 < janela:
            out.append(None)
        else:
            out.append(sum(series[i - janela + 1 : i + 1]) / janela)
    return out


def _ema(series: list[float], janela: int) -> list[Optional[float]]:
    if pd is not None:
        s = pd.Series(series)
        return s.ewm(span=janela, adjust=False).mean().tolist()
    if not series:
        return []
    alpha = 2 / (janela + 1)
    out: list[Optional[float]] = [series[0]]
    for i in range(1, len(series)):
        out.append(alpha * series[i] + (1 - alpha) * out[i - 1])
    return out


def _rsi(series: list[float], janela: int = 14) -> list[Optional[float]]:
    if pd is not None:
        s = pd.Series(series)
        delta = s.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / janela, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / janela, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        return (100 - (100 / (1 + rs))).tolist()
    if len(series) < janela + 1:
        return [None] * len(series)
    out: list[Optional[float]] = [None] * janela
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, janela + 1):
        d = series[i] - series[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains) / janela
    avg_loss = sum(losses) / janela
    def calc_rsi(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        rs = ag / al
        return 100 - (100 / (1 + rs))
    out.append(calc_rsi(avg_gain, avg_loss))
    for i in range(janela + 1, len(series)):
        d = series[i] - series[i - 1]
        gain = max(d, 0.0)
        loss = max(-d, 0.0)
        avg_gain = (avg_gain * (janela - 1) + gain) / janela
        avg_loss = (avg_loss * (janela - 1) + loss) / janela
        out.append(calc_rsi(avg_gain, avg_loss))
    return out


def _macd(series: list[float], rapida: int = 12, lenta: int = 26, sinal: int = 9):
    ema_rapida = _ema(series, rapida)
    ema_lenta = _ema(series, lenta)
    macd_line: list[Optional[float]] = []
    for a, b in zip(ema_rapida, ema_lenta):
        macd_line.append((a - b) if (a is not None and b is not None) else None)
    # sinal = EMA do macd_line (só valores não None)
    valores_macd = [v for v in macd_line if v is not None]
    sinal_line_raw = _ema(valores_macd, sinal) if valores_macd else []
    sinal_idx = 0
    macd_signal: list[Optional[float]] = []
    macd_hist: list[Optional[float]] = []
    si = 0
    for v in macd_line:
        if v is None:
            macd_signal.append(None)
            macd_hist.append(None)
        else:
            sval = sinal_line_raw[si] if si < len(sinal_line_raw) else None
            si += 1
            macd_signal.append(sval)
            macd_hist.append((v - sval) if (v is not None and sval is not None) else None)
    return macd_line, macd_signal, macd_hist


def _bollinger(series: list[float], janela: int = 20, num_std: float = 2.0):
    sma = _ma(series, janela)
    upper: list[Optional[float]] = []
    lower: list[Optional[float]] = []
    middle: list[Optional[float]] = []
    for i in range(len(series)):
        if sma[i] is None or i + 1 < janela:
            upper.append(None)
            lower.append(None)
            middle.append(None)
            continue
        janela_vals = series[i - janela + 1 : i + 1]
        media = sum(janela_vals) / janela
        var = sum((x - media) ** 2 for x in janela_vals) / janela
        std = var ** 0.5
        middle.append(sma[i])
        upper.append(sma[i] + num_std * std)
        lower.append(sma[i] - num_std * std)
    return upper, middle, lower


def _suportes_resistencias(highs: list[float], lows: list[float], janela: int = 10):
    suporte: list[Optional[float]] = []
    resistencia: list[Optional[float]] = []
    for i in range(len(lows)):
        if i + 1 < janela:
            suporte.append(None)
            resistencia.append(None)
            continue
        seg_low = lows[i - janela + 1 : i + 1]
        seg_high = highs[i - janela + 1 : i + 1]
        suporte.append(min(seg_low))
        resistencia.append(max(seg_high))
    return suporte, resistencia


def calcular_indicadores(cotacoes: list[Cotacao]) -> IndicadoresTecnicos:
    """Calcula indicadores técnicos a partir de uma lista ordenada de cotações."""
    if not cotacoes:
        return IndicadoresTecnicos(ticker="", data=date.today(), sinal="neutro")

    closes = [c.close for c in cotacoes]
    highs = [c.high for c in cotacoes]
    lows = [c.low for c in cotacoes]
    volumes = [c.volume for c in cotacoes]

    sma20 = _ma(closes, 20)
    sma50 = _ma(closes, 50)
    sma200 = _ma(closes, 200)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    rsi14 = _rsi(closes, 14)
    macd_line, macd_signal, macd_hist = _macd(closes)
    bb_upper, bb_middle, bb_lower = _bollinger(closes)
    suporte, resistencia = _suportes_resistencias(highs, lows)

    n = len(cotacoes)
    ultimo = cotacoes[-1]
    rsi_val = rsi14[n - 1]
    macd_val = macd_line[n - 1]
    macd_sig = macd_signal[n - 1]
    macd_h = macd_hist[n - 1]
    close = ultimo.close

    sinal = "neutro"
    motivos = []
    if rsi_val is not None:
        if rsi_val < 30:
            sinal = "compra"
            motivos.append("RSI sobrevenda")
        elif rsi_val > 70:
            sinal = "venda"
            motivos.append("RSI sobrecompra")
    if macd_val is not None and macd_sig is not None:
        if macd_val > macd_sig and (macd_h or 0) > 0:
            if sinal == "neutro":
                sinal = "compra"
            motivos.append("MACD de alta")
        elif macd_val < macd_sig and (macd_h or 0) < 0:
            if sinal == "neutro":
                sinal = "venda"
            motivos.append("MACD de baixa")
    if sma20[n - 1] is not None and sma50[n - 1] is not None:
        if close > sma20[n - 1] > sma50[n - 1]:
            if sinal == "neutro":
                sinal = "compra"
        elif close < sma20[n - 1] < sma50[n - 1]:
            if sinal == "neutro":
                sinal = "venda"

    return IndicadoresTecnicos(
        ticker=ultimo.ticker,
        data=ultimo.data,
        sma_20=sma20[n - 1],
        sma_50=sma50[n - 1],
        sma_200=sma200[n - 1],
        ema_12=ema12[n - 1],
        ema_26=ema26[n - 1],
        rsi_14=rsi_val,
        macd=macd_val,
        macd_signal=macd_sig,
        macd_hist=macd_h,
        bb_upper=bb_upper[n - 1],
        bb_middle=bb_middle[n - 1],
        bb_lower=bb_lower[n - 1],
        suporte=suporte[n - 1],
        resistencia=resistencia[n - 1],
        sinal=sinal,
    )


def gerar_sinais(ticker: str, cotacoes: list[Cotacao]) -> list[dict]:
    """Gera lista de sinais técnicos para persistência."""
    ind = calcular_indicadores(cotacoes)
    sinais = []
    if ind.sinal != "neutro":
        sinais.append({
            "ticker": ticker,
            "data": ind.data,
            "sinal": ind.sinal,
            "indicador": "conjunto",
            "valor": ind.close if hasattr(ind, 'close') else None,
            "fonte": "tecnico_interno",
        })
    if ind.rsi_14 is not None:
        if ind.rsi_14 < 30:
            sinais.append({
                "ticker": ticker,
                "data": ind.data,
                "sinal": "compra",
                "indicador": "rsi_14",
                "valor": ind.rsi_14,
                "fonte": "tecnico_interno",
            })
        elif ind.rsi_14 > 70:
            sinais.append({
                "ticker": ticker,
                "data": ind.data,
                "sinal": "venda",
                "indicador": "rsi_14",
                "valor": ind.rsi_14,
                "fonte": "tecnico_interno",
            })
    return sinais
