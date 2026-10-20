"""Motor fundamentalista determinístico (roadmap Fase 3).

Todos os indicadores são calculados a partir dos dados estruturados da CVM
armazenados na tabela `demonstracoes`. O LLM consome via tools, nunca calcula.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Indicadores:
    ticker: str
    cd_cvm: int
    dt_refer: str
    pl: float | None = None
    roe: float | None = None
    roic: float | None = None
    divida_liquida_ebitda: float | None = None
    f_score: int | None = None


def _connect():
    from .db import connect
    return connect()


def _busca_conta(conn, cd_cvm: int, dt_refer, conta: str, consolidacao: str = "con"):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT vl_conta FROM demonstracoes
            WHERE cd_cvm=%s AND dt_refer=%s AND consolidacao=%s AND cd_conta=%s
            ORDER BY versao DESC LIMIT 1
            """,
            (cd_cvm, dt_refer, consolidacao, conta),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None


def calcular_indicadores(cd_cvm: int, dt_refer) -> Indicadores:
    """Calcula indicadores fundamentalistas de forma determinística."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT denom FROM empresas WHERE cd_cvm=%s", (cd_cvm,))
            row = cur.fetchone()
            denom = row[0] if row else ""

        receita = _busca_conta(conn, cd_cvm, dt_refer, "3.01")
        ebit = _busca_conta(conn, cd_cvm, dt_refer, "3.05")
        lucro = _busca_conta(conn, cd_cvm, dt_refer, "3.11")
        ativo_total = _busca_conta(conn, cd_cvm, dt_refer, "1")
        pl_conta = _busca_conta(conn, cd_cvm, dt_refer, "2.03")
        divida_bruta = _busca_conta(conn, cd_cvm, dt_refer, "2.02.01") or 0.0
        caixa = _busca_conta(conn, cd_cvm, dt_refer, "1.01.01") or 0.0

    pl = (lucro / pl_conta) if (lucro is not None and pl_conta) else None
    roe = (lucro / pl_conta) if (lucro is not None and pl_conta) else None
    ebitda = ebit
    div_liq = (divida_bruta - caixa) if (divida_bruta is not None and caixa is not None) else None
    div_liq_ebitda = (div_liq / ebitda) if (div_liq is not None and ebitda) else None
    roic = (ebit / ativo_total) if (ebit is not None and ativo_total) else None

    return Indicadores(
        ticker=denom,
        cd_cvm=cd_cvm,
        dt_refer=dt_refer.isoformat() if hasattr(dt_refer, "isoformat") else str(dt_refer),
        pl=pl,
        roe=roe,
        roic=roic,
        divida_liquida_ebitda=div_liq_ebitda,
        f_score=None,
    )


def f_score_piotroski(cd_cvm: int, dt_refer_atual, dt_refer_anterior) -> int | None:
    """F-Score de Piotroski (9 critérios). Retorna pontuação 0-9 ou None."""
    pontos = 0

    with _connect() as conn:

        def conta(dt, codigo):
            return _busca_conta(conn, cd_cvm, dt, codigo)

        retorno_ativos_atual = conta(dt_refer_atual, "3.11")
    retorno_ativos_ant = conta( dt_refer_anterior, "3.11")
    ativo_total_atual = conta( dt_refer_atual, "1")
    ativo_total_ant = conta( dt_refer_anterior, "1")

    if retorno_ativos_atual is not None and retorno_ativos_atual > 0:
        pontos += 1
    if (
        retorno_ativos_atual is not None
        and ativo_total_atual is not None
        and ativo_total_atual != 0
        and (retorno_ativos_atual / ativo_total_atual)
        > (
            (retorno_ativos_ant or 0)
            / (ativo_total_ant or 1)
            if retorno_ativos_ant is not None and ativo_total_ant
            else 0
        )
    ):
        pontos += 1

    fluxo_caixa = conta( dt_refer_atual, "3.11")
    if fluxo_caixa is not None and fluxo_caixa > 0:
        pontos += 1

    if (
        retorno_ativos_atual is not None
        and ativo_total_atual is not None
        and ativo_total_atual != 0
        and retorno_ativos_ant is not None
        and ativo_total_ant is not None
        and ativo_total_ant != 0
    ):
        roa_atual = retorno_ativos_atual / ativo_total_atual
        roa_ant = retorno_ativos_ant / ativo_total_ant
        if roa_atual > roa_ant:
            pontos += 1

    if fluxo_caixa is not None and retorno_ativos_atual is not None and retorno_ativos_atual != 0:
        if fluxo_caixa > retorno_ativos_atual:
            pontos += 1

    div_atual = conta( dt_refer_atual, "2.03") or 0
    div_ant = conta( dt_refer_anterior, "2.03") or 0
    if div_atual <= div_ant:
        pontos += 1

    lucro_atual = conta( dt_refer_atual, "3.01") or 0
    lucro_ant = conta( dt_refer_anterior, "3.01") or 0
    if lucro_atual > lucro_ant:
        pontos += 1

    margem_atual = (conta( dt_refer_atual, "3.11") or 0) / max(
        conta( dt_refer_atual, "3.01") or 1, 1
    )
    margem_ant = (conta( dt_refer_anterior, "3.11") or 0) / max(
        conta( dt_refer_anterior, "3.01") or 1, 1
    )
    if margem_atual > margem_ant:
        pontos += 1

    rot_atual = (conta( dt_refer_atual, "3.01") or 0) / max(
        conta( dt_refer_atual, "1") or 1, 1
    )
    rot_ant = (conta( dt_refer_anterior, "3.01") or 0) / max(
        conta( dt_refer_anterior, "1") or 1, 1
    )
    if rot_atual > rot_ant:
        pontos += 1

    return pontos
