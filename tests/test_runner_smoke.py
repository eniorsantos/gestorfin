"""Smoke do benchmark ponta a ponta com um Ollama falso (sem rede, sem banco)."""
import json

from finllm.bench import tasks
from finllm.bench.report import write_report
from finllm.bench.runner import ModelCfg, run_benchmark


class FakeClient:
    """Responde 'perfeitamente' a cada tarefa, para validar o encanamento."""

    def __init__(self):
        self.unloaded = []

    def chat(self, model, messages, *, schema=None, tools=None, options=None, think=None, keep_alive=None):
        base = {"load_duration": 2_000_000_000, "total_duration": 1_000_000_000, "eval_count": 50,
                "eval_duration": 1_000_000_000, "prompt_eval_count": 500, "prompt_eval_duration": 500_000_000}
        user = messages[-1]["content"]
        if tools:
            for q, exp in tasks.TOOL_ITEMS:
                if q == user:
                    return {**base, "message": {"content": "", "tool_calls": [
                        {"function": {"name": exp["name"], "arguments": exp["args"]}}]}}
        if schema and "sentimento" in json.dumps(schema):
            gold = dict(tasks.CLASSIF_ITEMS)[user]
            body = {"sentimento": gold, "relevancia": "media", "justificativa": "ok"}
        elif schema:
            if "FICTICIO" in user:
                body = {"nao_encontrado": True, "resposta": "não consta", "citacoes": []}
            else:
                body = {"nao_encontrado": False, "resposta": "x [1]", "valor": 1000.0, "unidade": "R$ mil", "citacoes": [1]}
        else:
            body = "OK"
        return {**base, "message": {"content": body if isinstance(body, str) else json.dumps(body)}}

    def ps(self):
        return [{"name": "fake:1b", "size": 2**32, "size_vram": 2**32}]

    def unload(self, model):
        self.unloaded.append(model)


def test_benchmark_smoke(tmp_path):
    items = tasks.builtin_items() + [
        {"id": "fact-001", "task": "rag_fact", "question": "Qual o valor?", "gold": {"nao_encontrado": False, "valor": 1000.0, "gold_hashes": ["h"]},
         "contexts": [{"content": "ctx", "hash": "h"}]},
        {"id": "abst-001", "task": "rag_abstain", "question": "FICTICIO?", "gold": {"nao_encontrado": True, "gold_hashes": []},
         "contexts": [{"content": "ctx", "hash": "z"}]},
    ]
    fc = FakeClient()
    out = tmp_path / "run"
    run_benchmark(fc, [ModelCfg(name="fake:1b")], items, out, log=lambda *a, **k: None)
    recs = [json.loads(line) for line in open(out / "results.jsonl")]
    assert {r["task"] for r in recs} == {"_warmup", "classif", "tools", "rag_fact", "rag_abstain"}
    assert all(r["correct"] for r in recs if r["task"] != "_warmup")
    assert fc.unloaded == ["fake:1b"]
    md = write_report(out).read_text()
    assert "fake:1b" in md and "1.0" in md
