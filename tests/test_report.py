import json

from finllm.bench.report import write_report


def test_report_end_to_end(tmp_path):
    recs = [{"model": "m1", "task": "_warmup", "item_id": "w", "error": None, "wall_s": 3, "load_s": 2.5}]
    for i in range(10):
        recs.append({"model": "m1", "task": "rag_fact", "item_id": f"f{i}", "valid": True, "correct": i < 8,
                     "answered": True, "cite_ok": True, "error": None, "wall_s": 1.0 + i / 10,
                     "gen_tps": 40.0, "prompt_tps": 900.0})
        recs.append({"model": "m1", "task": "rag_abstain", "item_id": f"a{i}", "valid": True, "correct": i < 9,
                     "answered": i >= 9, "cite_ok": False, "error": None, "wall_s": 1.0, "gen_tps": 40.0,
                     "prompt_tps": 900.0})
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
    (tmp_path / "model_meta.json").write_text(json.dumps({"m1": {"size": 2**33, "size_vram": 2**33}}))
    p = write_report(tmp_path)
    txt = p.read_text()
    assert "m1" in txt and "rag_fact" in txt and "0.8" in txt
    assert (tmp_path / "summary.csv").exists()
