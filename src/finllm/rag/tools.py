"""Implementação real das tools usadas pelo LLM (roadmap Fase 3 e 4).

Expõe: get_indicadores, get_cotacoes, buscar_documentos, get_macro,
get_indicadores_tecnicos, get_sinal_tecnico.
"""
from __future__ import annotations

from ..ollama_client import OllamaClient


def _connect():
    from ..db import connect
    return connect()


def get_indicadores(ticker: str) -> dict:
    """Retorna indicadores fundamentalistas da última DFP consolidada disponível."""
    from ..cvm.load import normalizar_setores
    from ..fundamentalista import calcular_indicadores

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cd_cvm, denom FROM empresas WHERE denom ILIKE %s ORDER BY cd_cvm LIMIT 1",
                (f"%{ticker}%",),
            )
            row = cur.fetchone()
            if not row:
                return {"erro": f"Empresa não encontrada para {ticker!r}"}
            cd_cvm, denom = row
            cur.execute(
                """
                SELECT MAX(dt_refer) FROM demonstracoes
                WHERE cd_cvm=%s AND tipo_doc='DFP' AND consolidacao='con'
                  AND demonstracao IN ('DRE','BPA','BPP')
                """,
                (cd_cvm,),
            )
            dt_row = cur.fetchone()
            if not dt_row or not dt_row[0]:
                return {"erro": f"Sem DFP consolidada para {denom}"}
            dt_refer = dt_row[0]

    ind = calcular_indicadores(cd_cvm, dt_refer)
    return {
        "ticker": ticker.upper(),
        "empresa": denom,
        "cd_cvm": cd_cvm,
        "data_referencia": ind.dt_refer,
        "pl": ind.pl,
        "roe": ind.roe,
        "roic": ind.roic,
        "divida_liquida_ebitda": ind.divida_liquida_ebitda,
        "f_score": ind.f_score,
    }


def get_cotacoes(ticker: str, periodo: str = "6m") -> dict:
    """Série histórica de preços (OHLCV). Tenta yfinance; senão placeholder."""
    try:  # dependência opcional
        import yfinance as yf  # type: ignore

        tk = yf.Ticker(ticker if "." in ticker else f"{ticker}.SA")
        hist = tk.history(period=periodo)
        if hist.empty:
            return {
                "ticker": ticker.upper(),
                "periodo": periodo,
                "mensagem": "Sem dados de cotação disponíveis.",
                "cotacoes": [],
            }
        cotacoes = []
        for data, row in hist.iterrows():
            cotacoes.append({
                "data": str(data.date()) if hasattr(data, "date") else str(data),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if row["Volume"] is not None else 0,
            })
        return {
            "ticker": ticker.upper(),
            "periodo": periodo,
            "fonte": "yfinance",
            "n": len(cotacoes),
            "cotacoes": cotacoes,
        }
    except Exception:  # noqa: BLE001
        return {
            "ticker": ticker.upper(),
            "periodo": periodo,
            "mensagem": "yfinance não disponível ou erro ao buscar. Instale yfinance para cotações reais (roadmap Fase 4).",
            "cotacoes": [],
        }


def buscar_documentos(ticker: str, pergunta: str, k: int = 4) -> dict:
    """Busca semântica em documentos da companhia via RAG híbrido."""
    from ..rag.retrieve import retrieve

    client = OllamaClient()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cd_cvm FROM empresas WHERE denom ILIKE %s ORDER BY cd_cvm LIMIT 1",
                (f"%{ticker}%",),
            )
            row = cur.fetchone()
            if not row:
                return {"erro": f"Empresa não encontrada para {ticker!r}"}
            cd_cvm = row[0]
        hits, _ = retrieve(conn, client, pergunta, k=k, cd_cvm=cd_cvm)
    return {
        "ticker": ticker.upper(),
        "pergunta": pergunta,
        "documentos": [
            {
                "titulo": h.title or h.doc_type,
                "trecho": h.content[:500],
                "score": round(h.score, 4),
                "via": h.via,
            }
            for h in hits
        ],
    }


def get_macro(serie: str) -> dict:
    """Série macroeconômica brasileira (placeholder roadmap Fase 4/8)."""
    return {
        "serie": serie,
        "mensagem": "Série macroeconômica ainda não implementada (roadmap Fase 4/8).",
    }


def get_indicadores_tecnicos(ticker: str, periodo: str = "6m") -> dict:
    """Calcula indicadores técnicos de um ticker."""
    cotacao_result = get_cotacoes(ticker, periodo)
    if "erro" in cotacao_result or not cotacao_result.get("cotacoes"):
        return {
            "ticker": ticker.upper(),
            "mensagem": cotacao_result.get("mensagem", "Sem cotações para calcular indicadores técnicos."),
        }

    from ..tecnico import Cotacao, calcular_indicadores
    from datetime import date as _date

    cotacoes = []
    for c in cotacao_result["cotacoes"]:
        d = c["data"]
        if isinstance(d, str):
            d = _date.fromisoformat(d)
        cotacoes.append(
            Cotacao(
                ticker=ticker,
                data=d,
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c.get("volume", 0),
            )
        )
    ind = calcular_indicadores(cotacoes)
    return {
        "ticker": ind.ticker,
        "data": ind.data.isoformat() if hasattr(ind.data, "isoformat") else str(ind.data),
        "sinal": ind.sinal,
        "rsi_14": ind.rsi_14,
        "macd": ind.macd,
        "macd_signal": ind.macd_signal,
        "macd_hist": ind.macd_hist,
        "sma_20": ind.sma_20,
        "sma_50": ind.sma_50,
        "sma_200": ind.sma_200,
        "bb_upper": ind.bb_upper,
        "bb_middle": ind.bb_middle,
        "bb_lower": ind.bb_lower,
        "suporte": ind.suporte,
        "resistencia": ind.resistencia,
    }


def get_sinal_tecnico(ticker: str, periodo: str = "6m") -> dict:
    """Retorna o sinal técnico agregado de um ticker."""
    ind = get_indicadores_tecnicos(ticker, periodo)
    if "mensagem" in ind:
        return ind
    return {
        "ticker": ind["ticker"],
        "data": ind["data"],
        "sinal": ind["sinal"],
        "rsi_14": ind["rsi_14"],
        "macd_hist": ind["macd_hist"],
        "sma_20": ind["sma_20"],
        "sma_50": ind["sma_50"],
    }


TOOLS_REAIS = {
    "get_indicadores": get_indicadores,
    "get_cotacoes": get_cotacoes,
    "buscar_documentos": buscar_documentos,
    "get_macro": get_macro,
    "get_indicadores_tecnicos": get_indicadores_tecnicos,
    "get_sinal_tecnico": get_sinal_tecnico,
}

TOOL_DEFINICOES = [
    {
        "type": "function",
        "function": {
            "name": "get_indicadores",
            "description": "Indicadores fundamentalistas calculados (P/L, ROE, ROIC, dívida líquida/EBITDA, F-Score) de um ticker.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "Ex.: WEGE3"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cotacoes",
            "description": "Série histórica de preços (OHLCV) de um ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "periodo": {"type": "string", "enum": ["1m", "6m", "1a", "5a"]},
                },
                "required": ["ticker", "periodo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_documentos",
            "description": "Busca semântica em fatos relevantes, releases e demonstrações da companhia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "pergunta": {"type": "string"},
                },
                "required": ["ticker", "pergunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_macro",
            "description": "Série macroeconômica brasileira atual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "serie": {"type": "string", "enum": ["selic", "ipca", "cambio"]},
                },
                "required": ["serie"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicadores_tecnicos",
            "description": "Indicadores técnicos de um ticker (SMA, EMA, RSI, MACD, Bollinger, suportes/resistências) e sinal agregado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Ex.: WEGE3"},
                    "periodo": {"type": "string", "enum": ["1m", "6m", "1a", "5a"]},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sinal_tecnico",
            "description": "Sinal técnico agregado (compra/venda/neutro) de um ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Ex.: WEGE3"},
                    "periodo": {"type": "string", "enum": ["1m", "6m", "1a", "5a"]},
                },
                "required": ["ticker"],
            },
        },
    },
]
