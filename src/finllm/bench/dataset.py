"""Gera o dataset de QA a partir do PRÓPRIO banco (verdade-fundamento = linhas da CVM).

Tipos:
  rag_fact    — valor de uma conta (DFP consolidada) com distratores (mesma conta em outros anos, outra empresa)
  rag_abstain — mesmo formato, mas o período NÃO existe no contexto => resposta correta é "não encontrado"
  rag_calc    — margem líquida (3.11 / 3.01 x 100): testa leitura de 2 valores + aritmética
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timezone
from pathlib import Path

from ..cvm.load import CONS, STATEMENTS
from ..rag.cards import iter_card_chunks
from ..rag.index import ChunkIn

FACT_ACCOUNTS = {("DRE", "3.01"), ("DRE", "3.05"), ("DRE", "3.11"), ("BPA", "1"), ("BPP", "2.03")}


def _ctx(c: ChunkIn) -> dict:
    return {"content": c.content, "hash": c.hash}


def _gold_chunks(conn, cd, dem, dt: date, cd_conta: str) -> list[ChunkIn]:
    chunks = list(iter_card_chunks(conn, cd_cvms=[cd], kinds=["DFP"], statements=[dem], cons=["con"], dt_refer=dt))
    return [c for c in chunks if f"\n{cd_conta} | " in c.content]


def _distractors(conn, rng, cd, dem, cd_conta, exclude_dt: date | None, others: list[tuple], n_same=2) -> list[ChunkIn]:
    out: list[ChunkIn] = []
    same = [r for r in others if r[0] == cd and r[1] == dem and r[2] != exclude_dt]
    rng.shuffle(same)
    for r in same[:n_same]:
        out += _gold_chunks(conn, r[0], r[1], r[2], cd_conta)[:1]
    other = [r for r in others if r[0] != cd and r[1] == dem]
    if other:
        r = rng.choice(other)
        out += _gold_chunks(conn, r[0], r[1], r[2], cd_conta)[:1]
    return out


def build_dataset(conn, *, n_fact=40, n_abstain=15, n_calc=10, seed=42, only_indexed=False) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    idx_filter = ""
    if only_indexed:
        idx_filter = " AND cd_cvm IN (SELECT DISTINCT cd_cvm FROM chunks WHERE source='cvm_statement')"
    with conn.cursor() as cur:
        cur.execute(
            "SELECT cd_cvm, demonstracao, dt_refer, cd_conta, ds_conta, vl_conta, denom FROM demonstracoes "
            "WHERE tipo_doc='DFP' AND consolidacao='con' AND demonstracao IN ('DRE','BPA','BPP') "
            "AND vl_conta IS NOT NULL AND vl_conta <> 0" + idx_filter
        )
        rows = [r for r in cur.fetchall() if (r[1], r[3]) in FACT_ACCOUNTS]
        cur.execute("SELECT max(EXTRACT(year FROM dt_refer))::int FROM demonstracoes WHERE tipo_doc='DFP'")
        max_year = cur.fetchone()[0]
    if not rows:
        raise RuntimeError("Sem dados DFP consolidados no banco. Rode `finllm cvm load` antes.")
    others = sorted({(r[0], r[1], r[2]) for r in rows})
    rng.shuffle(rows)

    def question(r, dt_label: str) -> str:
        cd, dem, dt, conta, ds, vl, denom = r
        return (f"Qual foi o valor de '{ds}' (conta {conta}) na {STATEMENTS[dem]} ({CONS['con']}) de {denom} "
                f"no exercício encerrado em {dt_label}? Responda em R$ mil.")

    items: list[dict] = []
    for r in rows[:n_fact]:
        cd, dem, dt, conta, ds, vl, denom = r
        gold = _gold_chunks(conn, cd, dem, dt, conta)
        if not gold:
            continue
        ctxs = gold[:1] + _distractors(conn, rng, cd, dem, conta, dt, others)
        rng.shuffle(ctxs)
        items.append({
            "id": f"fact-{len(items)+1:03d}", "task": "rag_fact", "question": question(r, dt.strftime("%d/%m/%Y")),
            "gold": {"nao_encontrado": False, "valor": float(vl) / 1000, "gold_hashes": [gold[0].hash]},
            "contexts": [_ctx(c) for c in ctxs],
            "meta": {"cd_cvm": cd, "denom": denom, "conta": conta, "dt_refer": dt.isoformat()},
        })
    n_f = len(items)

    for r in rows[n_fact:n_fact + n_abstain]:
        cd, dem, dt, conta, ds, vl, denom = r
        missing_year = max_year + 2
        ctxs = _distractors(conn, rng, cd, dem, conta, None, others, n_same=2)
        if not ctxs:
            continue
        rng.shuffle(ctxs)
        items.append({
            "id": f"abst-{len(items)-n_f+1:03d}", "task": "rag_abstain",
            "question": question(r, f"31/12/{missing_year}"),
            "gold": {"nao_encontrado": True, "gold_hashes": []},
            "contexts": [_ctx(c) for c in ctxs],
            "meta": {"cd_cvm": cd, "denom": denom, "conta": conta, "ano_inexistente": missing_year},
        })
    n_a = len(items) - n_f

    # cálculo: margem líquida
    by_key: dict[tuple, dict] = {}
    for r in rows:
        if r[1] == "DRE" and r[3] in ("3.01", "3.11"):
            by_key.setdefault((r[0], r[2]), {})[r[3]] = (r[5], r[4], r[6])
    pairs = [(k, v) for k, v in by_key.items() if "3.01" in v and "3.11" in v]
    rng.shuffle(pairs)
    for (cd, dt), v in pairs[:n_calc]:
        rec, lucro = float(v["3.01"][0]), float(v["3.11"][0])
        denom = v["3.01"][2]
        g1, g2 = _gold_chunks(conn, cd, "DRE", dt, "3.01"), _gold_chunks(conn, cd, "DRE", dt, "3.11")
        if not g1 or not g2:
            continue
        gold = {c.hash: c for c in g1 + g2}
        ctxs = list(gold.values()) + _distractors(conn, rng, cd, "DRE", "3.01", dt, others, n_same=1)
        rng.shuffle(ctxs)
        items.append({
            "id": f"calc-{len(items)-n_f-n_a+1:03d}", "task": "rag_calc",
            "question": (f"Qual a margem líquida de {denom} no exercício encerrado em {dt.strftime('%d/%m/%Y')} "
                         "(DFP consolidada), calculada como conta 3.11 dividida pela conta 3.01, vezes 100? "
                         "Responda em %, com duas casas decimais."),
            "gold": {"nao_encontrado": False, "valor": lucro / rec * 100, "gold_hashes": list(gold)},
            "contexts": [_ctx(c) for c in ctxs],
            "meta": {"cd_cvm": cd, "denom": denom, "dt_refer": dt.isoformat()},
        })

    meta = {
        "seed": seed, "created_at": datetime.now(timezone.utc).isoformat(), "max_year_in_db": max_year,
        "counts": {t: sum(1 for i in items if i["task"] == t) for t in ("rag_fact", "rag_abstain", "rag_calc")},
        "only_indexed": only_indexed,
    }
    return items, meta


def save(items: list[dict], meta: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
