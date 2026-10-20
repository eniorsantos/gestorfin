"""Executa o benchmark: mesmos itens, mesmos parâmetros, vários modelos; grava JSONL bruto."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..config import settings
from ..ollama_client import OllamaClient, timings
from ..rag.answer import Resposta, build_messages, parse_resposta
from ..rag.retrieve import retrieve
from . import metrics, tasks


@dataclass
class ModelCfg:
    name: str
    think: bool | None = False
    min_mem_gb: float = 0
    options: dict = field(default_factory=dict)


def load_models(path: Path, *, only: list[str] | None = None, max_mem_gb: float | None = None) -> list[ModelCfg]:
    raw = yaml.safe_load(path.read_text())["models"]
    out = []
    for m in raw:
        cfg = ModelCfg(name=m["name"], think=m.get("think", False), min_mem_gb=m.get("min_mem_gb", 0),
                       options=m.get("options", {}))
        if only and cfg.name not in only:
            continue
        if max_mem_gb is not None and cfg.min_mem_gb > max_mem_gb:
            continue
        out.append(cfg)
    return out


def _call(client: OllamaClient, mc: ModelCfg, messages, **kw):
    opts = {"num_predict": 768, **mc.options}
    t0 = time.perf_counter()
    try:
        resp, err = client.chat(mc.name, messages, think=mc.think, options=opts, **kw), None
    except Exception as e:  # noqa: BLE001
        resp, err = None, str(e)[:300]
    return resp, err, time.perf_counter() - t0


def _retrieve_contexts(conn, client, items: list[dict], k: int) -> dict[str, list[dict]]:
    """Recuperação feita UMA vez por item (compartilhada entre modelos). Também mede recall@k."""
    cache = {}
    for it in items:
        if it["task"].startswith("rag_"):
            hits, _ = retrieve(conn, client, it["question"], k=k)
            cache[it["id"]] = [{"content": h.content, "hash": h.content_hash} for h in hits]
    return cache


def run_benchmark(
    client: OllamaClient, models: list[ModelCfg], items: list[dict], out_dir: Path, *,
    context_mode: str = "gold", repeats: int = 1, conn=None, k: int | None = None, log=print,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    k = k or settings.rag_top_k
    retrieved = _retrieve_contexts(conn, client, items, k) if context_mode == "retrieved" else {}
    results_path = out_dir / "results.jsonl"
    model_meta: dict[str, dict] = {}
    schema_resp = Resposta.model_json_schema()
    schema_cls = tasks.Classificacao.model_json_schema()

    with open(results_path, "w", encoding="utf-8") as fout:
        def emit(rec: dict) -> None:
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()

        for mc in models:
            log(f"\n=== {mc.name} ===")
            # warm-up: carrega o modelo e mede o cold start separadamente
            resp, err, wall = _call(client, mc, [{"role": "user", "content": "Responda apenas: OK"}])
            tm = timings(resp) if resp else {}
            emit({"model": mc.name, "task": "_warmup", "item_id": "warmup", "error": err, "wall_s": wall, **tm})
            if err:
                log(f"  ! falha ao carregar/usar o modelo: {err}")
                continue

            for rep in range(repeats):
                for n, it in enumerate(items, 1):
                    task = it["task"]
                    rec = {"model": mc.name, "task": task, "item_id": it["id"], "repeat": rep}
                    if task.startswith("rag_"):
                        ctxs = retrieved[it["id"]] if context_mode == "retrieved" else it["contexts"]
                        msgs = build_messages(it["question"], [c["content"] for c in ctxs])
                        resp, err, wall = _call(client, mc, msgs, schema=schema_resp)
                        parsed = parse_resposta(resp["message"]["content"]) if resp else None
                        pd_ = parsed.model_dump() if parsed else None
                        rec.update(metrics.score_rag(task, it["gold"], pd_, ctxs))
                        if context_mode == "retrieved" and it["gold"].get("gold_hashes"):
                            rec["retrieval_hit"] = any(c["hash"] in it["gold"]["gold_hashes"] for c in ctxs)
                        rec["parsed"] = pd_
                    elif task == "classif":
                        msgs = [{"role": "system", "content": tasks.CLASSIF_SYSTEM},
                                {"role": "user", "content": it["text"]}]
                        resp, err, wall = _call(client, mc, msgs, schema=schema_cls)
                        pd_ = None
                        if resp:
                            try:
                                pd_ = json.loads(resp["message"]["content"])
                                tasks.Classificacao.model_validate(pd_)
                            except Exception:  # noqa: BLE001
                                pd_ = None
                        rec.update(metrics.score_classif(it["gold"], pd_))
                    elif task == "tools":
                        msgs = [{"role": "system", "content": tasks.TOOL_SYSTEM},
                                {"role": "user", "content": it["question"]}]
                        resp, err, wall = _call(client, mc, msgs, tools=tasks.TOOLS)
                        calls = resp["message"].get("tool_calls") if resp else None
                        rec.update(metrics.score_tool(it["expected"], calls))
                    else:
                        continue
                    rec.update({"error": err, "wall_s": wall, **(timings(resp) if resp else {})})
                    emit(rec)
                    if n % 10 == 0:
                        log(f"  {n}/{len(items)} (rep {rep + 1}/{repeats})")

            try:  # VRAM/offload reais, com o modelo ainda carregado
                for m in client.ps():
                    if m.get("name", "").split(":")[0] == mc.name.split(":")[0] or m.get("model") == mc.name:
                        model_meta[mc.name] = {"size": m.get("size"), "size_vram": m.get("size_vram"),
                                               "context_length": m.get("context_length")}
            except Exception:  # noqa: BLE001
                pass
            client.unload(mc.name)

    (out_dir / "model_meta.json").write_text(json.dumps(model_meta, indent=2))
    return results_path
