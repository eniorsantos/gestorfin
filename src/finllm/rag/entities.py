"""Resolução de empresas por nome (heurística simples e auditável)."""
from __future__ import annotations

import re
import unicodedata

STOP = {"S", "A", "SA", "CIA", "COMPANHIA", "DE", "DA", "DO", "DAS", "DOS", "E", "HOLDING", "PARTICIPACOES"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", s)).strip().upper()


def core(s: str) -> str:
    toks = [t for t in norm(s).split() if t not in STOP]
    return " ".join(toks[:2])


def aliases(denom: str) -> set[str]:
    """'PETRÓLEO BRASILEIRO S.A. - PETROBRAS' -> {'PETROLEO BRASILEIRO', 'PETROBRAS'}"""
    return {c for p in re.split(r"\s+-\s+", denom or "") if (c := core(p))}


def _alias_map(conn) -> tuple[dict[str, set[int]], dict[int, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT cd_cvm, denom FROM empresas")
        rows = cur.fetchall()
    amap: dict[str, set[int]] = {}
    for cd, denom in rows:
        for a in aliases(denom):
            amap.setdefault(a, set()).add(cd)
    return amap, {cd: d for cd, d in rows}


def find_in_text(conn, text: str) -> int | None:
    """Acha a empresa citada em um texto livre. Retorna None se não houver ou se for ambíguo."""
    amap, _ = _alias_map(conn)
    t = norm(text)
    for alias in sorted(amap, key=len, reverse=True):
        if len(alias) >= 4 and re.search(rf"\b{re.escape(alias)}\b", t):
            ids = amap[alias]
            if len(ids) == 1:
                return next(iter(ids))
    return None


def resolve_empresa(conn, name: str) -> tuple[int, str]:
    """Nome informado pelo usuário -> (cd_cvm, denom). Levanta ValueError se não achar/ambíguo."""
    amap, names = _alias_map(conn)
    key = core(name)
    if key in amap and len(amap[key]) == 1:
        cd = next(iter(amap[key]))
        return cd, names[cd]
    like = [(cd, d) for cd, d in names.items() if norm(name) in norm(d)]
    if len(like) == 1:
        return like[0]
    if not like:
        raise ValueError(f"Empresa não encontrada: {name!r}. Rode `finllm cvm download` e `cvm load` antes.")
    cands = "; ".join(f"{cd}={d}" for cd, d in like[:8])
    raise ValueError(f"Nome ambíguo {name!r}. Candidatos: {cands}. Seja mais específico.")
