"""Validação determinística das respostas: todo número citado precisa existir no contexto."""
from __future__ import annotations

import re
from dataclasses import dataclass

NUM_RE = re.compile(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?(?:\.\d+)?")
_CITE = re.compile(r"\[\d+\]")


def parse_number(s: str) -> float | None:
    """Aceita '1.234.567', '1.234,56', '1234.56', '-12,5'."""
    s = s.strip()
    try:
        if "," in s:
            return float(s.replace(".", "").replace(",", "."))
        if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", s):
            return float(s.replace(".", ""))
        return float(s)
    except ValueError:
        return None


def numbers_in(text: str) -> list[float]:
    text = _CITE.sub(" ", text)
    out = []
    for m in NUM_RE.finditer(text):
        v = parse_number(m.group())
        if v is not None:
            out.append(v)
    return out


@dataclass
class Validation:
    ok: bool
    unsupported: list[float]


def validate_numbers(answer: str, contexts: list[str], *, ignore_small_ints: int = 31) -> Validation:
    """Números da resposta ausentes do contexto. Ignora anos (1900-2100) e inteiros pequenos (dias, trimestres).

    Limitação assumida: números derivados (somas, razões) também são sinalizados — o cálculo deve ser feito em código.
    """
    ctx = set()
    for c in contexts:
        ctx.update(round(abs(v), 6) for v in numbers_in(c))
    bad = []
    for v in numbers_in(answer):
        av = abs(v)
        if float(av).is_integer() and (av <= ignore_small_ints or 1900 <= av <= 2100):
            continue
        if round(av, 6) not in ctx:
            bad.append(v)
    return Validation(ok=not bad, unsupported=bad)
