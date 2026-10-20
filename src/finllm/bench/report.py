"""Agrega results.jsonl -> summary.csv + report.md."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .metrics import percentile, wilson

# Pesos do score composto (renormalizados entre as tarefas presentes). Edite conforme seu caso de uso.
WEIGHTS = {"rag_fact": 0.35, "rag_abstain": 0.20, "rag_calc": 0.10, "tools": 0.15, "classif": 0.10, "json_valid": 0.10}


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(lines)


def summarize(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    recs = [json.loads(line) for line in open(run_dir / "results.jsonl", encoding="utf-8") if line.strip()]
    df = pd.DataFrame(recs)
    meta_p = run_dir / "model_meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    warm = df[df.task == "_warmup"].set_index("model")
    body = df[df.task != "_warmup"].copy()
    rows, detail = [], []
    for model, g in body.groupby("model"):
        row: dict = {"modelo": model}
        score_parts = {}
        for task, t in g.groupby("task"):
            n, k = len(t), int(t["correct"].sum())
            lo, hi = wilson(k, n)
            detail.append({"modelo": model, "tarefa": task, "n": n, "acertos": k, "acc": round(k / n, 3),
                           "ic95": f"{lo:.2f}-{hi:.2f}"})
            row[task] = round(k / n, 3)
            score_parts[task] = k / n
            if task == "rag_fact":
                row["resp_errada_confiante"] = round(float((t["answered"].astype(bool) & ~t["correct"].astype(bool)).mean()), 3)
                row["citacao_ok"] = round(float(t[t["correct"]]["cite_ok"].mean()), 3) if k else None
                if "retrieval_hit" in t:
                    row["recall@k"] = round(float(t["retrieval_hit"].mean()), 3)
            if task == "rag_abstain":
                row["alucinacao_abstain"] = round(1 - k / n, 3)
        row["json_valid"] = round(float(body[body.model == model]["valid"].mean()), 3)
        score_parts["json_valid"] = row["json_valid"]
        w = {t: WEIGHTS[t] for t in score_parts if t in WEIGHTS}
        row["score"] = round(sum(score_parts[t] * w[t] for t in w) / sum(w.values()), 3) if w else None
        ok = g[g.error.isna()] if "error" in g else g
        row["gen_tok/s"] = round(float(ok["gen_tps"].median()), 1) if len(ok) else None
        row["prompt_tok/s"] = round(float(ok["prompt_tps"].median()), 0) if len(ok) else None
        lat = ok["wall_s"].tolist()
        row["lat_p50_s"] = round(percentile(lat, 0.5), 2)
        row["lat_p95_s"] = round(percentile(lat, 0.95), 2)
        row["cold_load_s"] = round(float(warm.loc[model, "load_s"]), 1) if model in warm.index else None
        m = meta.get(model, {})
        row["vram_gb"] = round(m["size_vram"] / 2**30, 1) if m.get("size_vram") is not None else None
        row["gpu_%"] = round(100 * m["size_vram"] / m["size"]) if m.get("size") else None
        row["erros"] = int(g["error"].notna().sum()) if "error" in g else 0
        rows.append(row)
    summary = pd.DataFrame(rows).sort_values("score", ascending=False, na_position="last")
    return summary, pd.DataFrame(detail)


def write_report(run_dir: Path) -> Path:
    summary, detail = summarize(run_dir)
    summary.to_csv(run_dir / "summary.csv", index=False)
    detail.to_csv(run_dir / "detail.csv", index=False)
    hw_p = run_dir / "hardware.json"
    hw = json.loads(hw_p.read_text()) if hw_p.exists() else {}
    cfg_p = run_dir / "run_config.json"
    cfg = json.loads(cfg_p.read_text()) if cfg_p.exists() else {}
    gpus = ", ".join(f"{g['name']} ({g['vram_gb']} GB)" for g in hw.get("gpus", [])) or "n/d (veja gpu_% e vram_gb abaixo)"
    md = [
        f"# Benchmark — {run_dir.name}", "",
        "## Ambiente", "",
        f"- Plataforma: {hw.get('platform', 'n/d')}",
        f"- CPU: {hw.get('cpu_physical', '?')} núcleos físicos / {hw.get('cpu_logical', '?')} lógicos — RAM {hw.get('ram_gb', '?')} GB",
        f"- GPU: {gpus}", f"- Ollama: {hw.get('ollama_version', '?')}",
        f"- Config: {json.dumps(cfg, ensure_ascii=False)}", "",
        "## Resultado por modelo", "",
        "`score` = média ponderada (pesos em `bench/report.py`). **Não escolha só pelo score**: veja IC95% (n pequeno "
        "dá intervalos largos), `alucinacao_abstain`, `resp_errada_confiante` e velocidade.", "",
        _md_table(summary), "",
        "## Acurácia por tarefa (com IC 95% de Wilson)", "", _md_table(detail), "",
        "## Como ler", "",
        "- **rag_fact**: valor de conta correto (tolerância 0,5%). **rag_abstain**: reconheceu que o dado não está no contexto. "
        "**rag_calc**: margem líquida (±0,1 p.p.). **tools**: ferramenta e argumentos corretos. **classif**: sentimento correto.",
        "- **resp_errada_confiante**: respondeu um número errado sem marcar `nao_encontrado` (o pior erro neste domínio).",
        "- **recall@k** (modo `retrieved`): fração de perguntas em que o trecho correto estava entre os k recuperados — "
        "separa falha de recuperação de falha de geração.",
        "- **gpu_%**: parcela do modelo na VRAM (<100% = offload parcial p/ CPU, lento). **cold_load_s**: tempo de carga.",
    ]
    p = run_dir / "report.md"
    p.write_text("\n".join(md), encoding="utf-8")
    return p
