"""Métricas e funções de pontuação (puras, testáveis)."""
from __future__ import annotations

import math


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de Wilson (95%) — com n pequeno, o IC importa mais que o ponto."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - a) / d, (c + a) / d


def within(a: float, b: float, *, rel: float = 0.0, abs_tol: float = 0.0) -> bool:
    return abs(a - b) <= max(abs_tol, rel * abs(b))


def percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    i = (len(xs) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def score_rag(task: str, gold: dict, parsed: dict | None, contexts: list[dict]) -> dict:
    """rag_fact / rag_abstain / rag_calc. `parsed` = JSON da Resposta (ou None se inválido)."""
    if parsed is None:
        return {"valid": False, "correct": False, "answered": False, "cite_ok": False}
    nf = bool(parsed.get("nao_encontrado"))
    val = parsed.get("valor")
    if gold["nao_encontrado"]:
        correct = nf
    elif nf or not isinstance(val, (int, float)):
        correct = False
    elif task == "rag_calc":
        correct = within(float(val), gold["valor"], abs_tol=0.1)
    else:
        correct = within(float(val), gold["valor"], rel=0.005, abs_tol=0.5)
    gold_hashes = set(gold.get("gold_hashes", []))
    cites = [c for c in parsed.get("citacoes", []) if isinstance(c, int) and 1 <= c <= len(contexts)]
    cite_ok = any(contexts[c - 1].get("hash") in gold_hashes for c in cites) if gold_hashes else False
    return {"valid": True, "correct": correct, "answered": not nf, "cite_ok": cite_ok}


def score_classif(gold: str, parsed: dict | None) -> dict:
    if parsed is None:
        return {"valid": False, "correct": False}
    return {"valid": True, "correct": str(parsed.get("sentimento", "")).lower() == gold}


def score_tool(expected: dict, tool_calls: list[dict] | None) -> dict:
    if not tool_calls:
        return {"valid": False, "correct": False}
    call = tool_calls[0].get("function", {})
    args = call.get("arguments") or {}
    if isinstance(args, str):
        import json
        try:
            args = json.loads(args)
        except Exception:  # noqa: BLE001
            return {"valid": False, "correct": False}
    ok = call.get("name") == expected["name"] and all(
        str(args.get(k, "")).strip().lower() == str(v).lower() for k, v in expected["args"].items()
    )
    return {"valid": True, "correct": ok}
