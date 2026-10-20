"""Consulta SQL direta para perguntas puramente numéricas (melhoria RAG).

Permite responder perguntas como "qual foi a receita líquida da X em 2023?"
diretamente contra a tabela `demonstracoes`, sem passar pelo LLM para leitura
de valor. O LLM só formata a resposta final.
"""
from __future__ import annotations

import re

def _connect():
    from ..db import connect
    return connect()

_CONTA_POR_DESCRICAO = {
    "receita": "3.01",
    "receita liquida": "3.01",
    "receita líquida": "3.01",
    "faturamento": "3.01",
    "ebit": "3.05",
    "resultado antes de financeiro e tributos": "3.05",
    "lucro": "3.11",
    "lucro liquido": "3.11",
    "lucro líquido": "3.11",
    "ativo total": "1",
    "patrimonio liquido": "2.03",
    "patrimônio líquido": "2.03",
}

_YEAR = re.compile(r"\b(19[89]\d|20\d{2})\b")


def _conta_da_pergunta(pergunta: str) -> str | None:
    p = pergunta.lower()
    for desc, conta in _CONTA_POR_DESCRICAO.items():
        if desc in p:
            return conta
    return None


def consultar_valor_direto(
    cd_cvm: int, dt_refer, conta: str, consolidacao: str = "con"
) -> float | None:
    """Busca o valor de uma conta diretamente no banco."""
    with _connect() as conn:
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


def tentar_resposta_direta(pergunta: str, cd_cvm: int | None) -> dict | None:
    """Tenta responder diretamente via SQL. Retorna dict com valor ou None se não for possível."""
    conta = _conta_da_pergunta(pergunta)
    if conta is None or cd_cvm is None:
        return None

    anos = sorted({int(y) for y in _YEAR.findall(pergunta)})
    if not anos:
        return None

    ano = anos[0]
    from datetime import date
    dt_refer = date(ano, 12, 31)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT denom FROM empresas WHERE cd_cvm=%s", (cd_cvm,))
            row = cur.fetchone()
            if not row:
                return None
            denom = row[0]

    vl = consultar_valor_direto(cd_cvm, dt_refer, conta)
    if vl is None:
        return None

    return {
        "empresa": denom,
        "cd_cvm": cd_cvm,
        "conta": conta,
        "data_referencia": dt_refer.isoformat(),
        "valor_reais": vl,
        "valor_mil": vl / 1000,
    }
