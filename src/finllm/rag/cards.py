"""Converte linhas de `demonstracoes` em 'cartões' textuais -> chunks indexáveis.

Cada cartão = (empresa, documento, demonstração, consolidação, período). O cabeçalho é repetido em todos
os chunks do cartão para que a busca por empresa/período funcione mesmo em chunks isolados.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from itertools import groupby

from ..config import settings
from ..cvm.load import CONS, STATEMENTS
from .index import ChunkIn
from .text import chunk_lines

SKIP_PREFIXES = ("3.99",)  # lucro por ação: unidade (R$/ação) diferente do resto do demonstrativo


def fmt_mil(v_reais: float) -> str:
    return f"{float(v_reais) / 1000:,.0f}".replace(",", ".")


def br(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "?"


def _conta_key(c: str) -> tuple:
    try:
        return tuple(int(x) for x in c.split("."))
    except ValueError:
        return (10**6, c)


def _build(key: tuple, rows: list[tuple]) -> list[ChunkIn]:
    cd, denom, tipo, dem, cons, dt_refer, dt_ini = key
    periodo = f"Período: {br(dt_ini)} a {br(dt_refer)}" if dt_ini else f"Data-base: {br(dt_refer)}"
    header = (
        f"Empresa: {denom} (CD_CVM {cd}) | Documento: {tipo} | {CONS.get(cons, cons)} | "
        f"{STATEMENTS.get(dem, dem)} | {periodo} | Valores em R$ mil"
    )
    rows = sorted(rows, key=lambda r: _conta_key(r[0]))
    lines = [f"{c} | {ds} | {fmt_mil(v)}" for c, ds, v in rows if not c.startswith(SKIP_PREFIXES)]
    title = f"{tipo} {dem} {cons} {dt_refer.isoformat()}"
    return [
        ChunkIn(
            source="cvm_statement", content=content, cd_cvm=cd, denom=denom,
            doc_type=f"{tipo}-{dem}-{cons}", ref_date=dt_refer, title=title, chunk_idx=i,
            metadata={"tipo_doc": tipo, "demonstracao": dem, "consolidacao": cons,
                      "dt_ini": dt_ini.isoformat() if dt_ini else None},
        )
        for i, content in enumerate(chunk_lines(header, lines, settings.chunk_max_chars))
    ]


def iter_card_chunks(
    conn, *, cd_cvms: list[int] | None = None, years: list[int] | None = None,
    kinds: list[str] | None = None, statements: list[str] | None = None,
    cons: list[str] | None = None, dt_refer: date | None = None,
) -> Iterator[ChunkIn]:
    where, args = [], []
    if cd_cvms:
        where.append("cd_cvm = ANY(%s)"); args.append(cd_cvms)
    if years:
        where.append("EXTRACT(year FROM dt_refer)::int = ANY(%s)"); args.append(years)
    if kinds:
        where.append("tipo_doc = ANY(%s)"); args.append([k.upper() for k in kinds])
    if statements:
        where.append("demonstracao = ANY(%s)"); args.append(statements)
    if cons:
        where.append("consolidacao = ANY(%s)"); args.append(cons)
    if dt_refer:
        where.append("dt_refer = %s"); args.append(dt_refer)
    sql = (
        "SELECT cd_cvm, denom, tipo_doc, demonstracao, consolidacao, dt_refer, dt_ini_exerc, "
        "cd_conta, ds_conta, vl_conta FROM demonstracoes "
        + ("WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY cd_cvm, tipo_doc, demonstracao, consolidacao, dt_refer, dt_ini_exerc NULLS FIRST"
    )
    with conn.cursor(name="cards_cur") as cur:
        cur.itersize = 5000
        cur.execute(sql, args)
        for key, grp in groupby(cur, key=lambda r: r[:7]):
            yield from _build(key, [(r[7], r[8], r[9]) for r in grp])
    conn.rollback()  # encerra a transação do cursor nomeado
