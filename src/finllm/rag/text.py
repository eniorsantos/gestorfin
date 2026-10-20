"""Extração de texto e chunking."""
from __future__ import annotations

import re


def extract_text(content: bytes) -> tuple[str | None, str]:
    """Retorna (texto, formato). texto=None se o formato não é suportado."""
    head = content[:8]
    if head.startswith(b"%PDF"):
        import fitz  # pymupdf

        with fitz.open(stream=content, filetype="pdf") as doc:
            return clean("\n\n".join(p.get_text() for p in doc)), "pdf"
    if head.startswith(b"PK"):
        return None, "zip"
    txt = content.decode("utf-8", errors="ignore") if content[:3] != b"\xff\xfe" else content.decode("utf-16", "ignore")
    if "<html" in txt[:2000].lower() or "<body" in txt[:2000].lower():
        from bs4 import BeautifulSoup

        return clean(BeautifulSoup(txt, "html.parser").get_text("\n")), "html"
    return clean(txt), "text"


def clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 2500, overlap: int = 200) -> list[str]:
    """Chunking por parágrafos; parágrafos gigantes são quebrados por sentenças/caracteres com overlap."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []
    for p in paras:
        if len(p) <= max_chars:
            pieces.append(p)
            continue
        start = 0
        while start < len(p):
            end = min(start + max_chars, len(p))
            cut = p.rfind(". ", start, end)
            if cut > start + max_chars // 2 and end < len(p):
                end = cut + 1
            pieces.append(p[start:end].strip())
            if end >= len(p):
                break
            start = max(end - overlap, start + 1)
    chunks, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + len(piece) + 2 > max_chars:
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n\n{piece}" if cur else piece
    if cur:
        chunks.append(cur)
    return chunks


def chunk_lines(header: str, lines: list[str], max_chars: int = 2500) -> list[str]:
    """Quebra uma tabela em chunks, repetindo o cabeçalho (empresa/período) em cada um."""
    groups: list[list[str]] = []
    cur: list[str] = []
    size = len(header) + 24
    for ln in lines:
        if cur and size + len(ln) + 1 > max_chars:
            groups.append(cur)
            cur, size = [], len(header) + 24
        cur.append(ln)
        size += len(ln) + 1
    if cur:
        groups.append(cur)
    n = len(groups)
    out = []
    for i, g in enumerate(groups, 1):
        h = header if n == 1 else f"{header} | Parte {i}/{n}"
        out.append(h + "\n" + "\n".join(g))
    return out
