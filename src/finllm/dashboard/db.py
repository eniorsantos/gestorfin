"""Acesso ao banco para o dashboard (com fallback offline quando sem Postgres)."""
from __future__ import annotations

from typing import Optional

try:
    from ..db import connect as _real_connect
except Exception:  # psycopg não instalado ou sem banco
    _real_connect = None  # type: ignore


def connect() -> Optional[object]:
    """Retorna uma conexão psycopg ou None se não houver banco disponível."""
    if _real_connect is None:
        return None
    try:
        return _real_connect()
    except Exception:
        return None


def _fetchall(conn, sql: str, params=()):
    if conn is None:
        return [], []
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    return cols, rows


def _fetchone(conn, sql: str, params=()):
    if conn is None:
        return None
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def estatisticas_gerais() -> dict:
    conn = connect()
    if conn is None:
        return {
            "empresas": 0,
            "demonstacoes": 0,
            "chunks": 0,
            "consultas": 0,
            "alertas": 0,
        }
    try:
        out = {}
        for tabela, alias in (("empresas", "empresas"),
                              ("demonstracoes", "demonstacoes"),
                              ("chunks", "chunks"),
                              ("consultas", "consultas"),
                              ("alertas", "alertas")):
            cols, rows = _fetchall(conn, f"SELECT count(*) FROM {tabela}")
            out[alias] = int(rows[0][0]) if rows else 0
        return out
    finally:
        conn.close()


def listar_empresas(limit: int = 100, setor: Optional[str] = None):
    conn = connect()
    if conn is None:
        return []
    sql = "SELECT cd_cvm, denom, setor, situacao FROM empresas"
    params = ()
    if setor:
        sql += " WHERE setor = %s"
        params = (setor,)
    sql += " ORDER BY denom LIMIT %s"
    params = params + (limit,)
    cols, rows = _fetchall(conn, sql, params)
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def listar_setores():
    conn = connect()
    if conn is None:
        return []
    cols, rows = _fetchall(conn, "SELECT DISTINCT setor FROM empresas WHERE setor IS NOT NULL ORDER BY setor")
    conn.close()
    return [r[0] for r in rows]


def listar_consultas(limit: int = 50):
    conn = connect()
    if conn is None:
        return []
    cols, rows = _fetchall(
        conn,
        "SELECT id, pergunta, modelo, criado_em, resposta, validacao FROM consultas ORDER BY criado_em DESC LIMIT %s",
        (limit,),
    )
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def listar_alertas(ativo: Optional[bool] = None):
    conn = connect()
    if conn is None:
        return []
    sql = "SELECT id, ticker, tipo, condicao, valor_referencia, ativo, criado_em, disparado_em FROM alertas"
    params = ()
    if ativo is not None:
        sql += " WHERE ativo = %s"
        params = (ativo,)
    sql += " ORDER BY criado_em DESC"
    cols, rows = _fetchall(conn, sql, params)
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def criar_alerta(ticker: str, tipo: str, condicao: str, valor_referencia: float) -> int:
    conn = connect()
    if conn is None:
        return -1
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO alertas (ticker, tipo, condicao, valor_referencia, ativo)
            VALUES (%s, %s, %s, %s, true)
            RETURNING id
            """,
            (ticker, tipo, condicao, valor_referencia),
        )
        row = cur.fetchone()
        conn.commit()
        alerta_id = int(row[0])
    conn.close()
    return alerta_id


def indicadores_ticker(ticker: str) -> dict:
    """Retorna indicadores fundamentalistas + técnicos de um ticker (ou vazio se sem DB)."""
    from ..fundamentalista import calcular_indicadores
    from datetime import date

    conn = connect()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cd_cvm, denom FROM empresas WHERE denom ILIKE %s ORDER BY cd_cvm LIMIT 1",
                (f"%{ticker}%",),
            )
            row = cur.fetchone()
            if not row:
                return {}
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
            dt_refer = dt_row[0] if dt_row and dt_row[0] else None
    finally:
        conn.close()

    if dt_refer is None:
        return {"ticker": ticker.upper(), "empresa": denom, "mensagem": "Sem DFP consolidada"}

    ind = calcular_indicadores(cd_cvm, dt_refer)
    return {
        "ticker": ticker.upper(),
        "empresa": ind.ticker,
        "cd_cvm": ind.cd_cvm,
        "data_referencia": ind.dt_refer,
        "pl": ind.pl,
        "roe": ind.roe,
        "roic": ind.roic,
        "divida_liquida_ebitda": ind.divida_liquida_ebitda,
        "f_score": ind.f_score,
    }
