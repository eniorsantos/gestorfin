from finllm.bench.metrics import percentile, score_classif, score_rag, score_tool, wilson, within


def test_wilson_basico():
    lo, hi = wilson(8, 10)
    assert 0.4 < lo < 0.5 and 0.9 < hi < 0.98
    assert wilson(0, 0) == (0.0, 0.0)


def test_within():
    assert within(100.4, 100, rel=0.005)
    assert not within(101, 100, rel=0.005)
    assert within(0.3, 0.0, abs_tol=0.5)


def test_score_fact_correto_errado_e_abstencao():
    gold = {"nao_encontrado": False, "valor": 1000.0, "gold_hashes": ["h1"]}
    ctx = [{"hash": "h0"}, {"hash": "h1"}]
    ok = score_rag("rag_fact", gold, {"nao_encontrado": False, "valor": 1003.0, "citacoes": [2]}, ctx)
    assert ok["correct"] and ok["cite_ok"] and ok["answered"]
    bad = score_rag("rag_fact", gold, {"nao_encontrado": False, "valor": 1100.0, "citacoes": [1]}, ctx)
    assert not bad["correct"] and bad["answered"] and not bad["cite_ok"]
    nf = score_rag("rag_fact", gold, {"nao_encontrado": True, "valor": None}, ctx)
    assert not nf["correct"] and not nf["answered"]
    abst = {"nao_encontrado": True, "gold_hashes": []}
    assert score_rag("rag_abstain", abst, {"nao_encontrado": True}, ctx)["correct"]
    assert not score_rag("rag_abstain", abst, {"nao_encontrado": False, "valor": 5}, ctx)["correct"]
    assert not score_rag("rag_fact", gold, None, ctx)["valid"]


def test_calc_tolerancia_pp():
    g = {"nao_encontrado": False, "valor": 12.34, "gold_hashes": []}
    assert score_rag("rag_calc", g, {"nao_encontrado": False, "valor": 12.40}, [])["correct"]
    assert not score_rag("rag_calc", g, {"nao_encontrado": False, "valor": 13.0}, [])["correct"]


def test_classif_e_tool():
    assert score_classif("positivo", {"sentimento": "Positivo"})["correct"]
    exp = {"name": "get_cotacoes", "args": {"ticker": "PETR4", "periodo": "6m"}}
    call = [{"function": {"name": "get_cotacoes", "arguments": {"ticker": "petr4", "periodo": "6m"}}}]
    assert score_tool(exp, call)["correct"]
    assert not score_tool(exp, [{"function": {"name": "get_macro", "arguments": {}}}])["correct"]
    assert not score_tool(exp, None)["valid"]


def test_percentile():
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert percentile([], 0.5) == 0.0
