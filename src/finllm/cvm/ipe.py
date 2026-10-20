"""Documentos narrativos (IPE): fatos relevantes, comunicados etc. -> texto -> chunks -> pgvector.

ATENÇÃO: o índice IPE lista os documentos e traz um link por documento. O formato servido pelo link
(PDF, HTML, ZIP...) varia; documentos em formato não suportado são marcados como 'ignorado'.
"""
from __future__ import annotations

import zipfile

import httpx
import pandas as pd

from ..config import settings
from ..ollama_client import OllamaClient
from ..rag.entities import norm
from ..rag.index import ChunkIn, index_chunks
from ..rag.text import chunk_text, extract_text
from .download import fetch


def _chunk_por_secao(text: str, max_chars: int = 2500) -> list[str]:
    """Divide texto em chunks respeitando seções (títulos) quando detectadas.

    Tenta usar Docling para identificar títulos/tabelas. Se Docling não estiver
    disponível, faz fallback para chunking por parágrafos com detecção simples
    de títulos (linhas curtas em maiúsculas ou precedidas por número).
    """
    # Tentativa de Docling (dependência opcional). Sem um arquivo físico para
    # converter, forçamos o fallback heurístico abaixo.
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
        raise ImportError  # sem arquivo físico: usar fallback
    except Exception:
        pass

    # Fallback: detecção simples de seção por linhas que parecem títulos
    linhas = [l for l in text.split("\n") if l.strip()]
    if not linhas:
        return []

    secoes: list[tuple[str, list[str]]] = []
    secao_atual: list[str] = []
    titulo_atual = "sem_secao"

    def eh_titulo(linha: str) -> bool:
        limpa = linha.strip()
        if not limpa or len(limpa) >= 80:
            return False
        if limpa.startswith(("http", "www")):
            return False
        return limpa.isupper() or limpa[0].isdigit()

    for linha in linhas:
        if eh_titulo(linha):
            if secao_atual:
                secoes.append((titulo_atual, secao_atual))
            secao_atual = []
            titulo_atual = linha.strip()
        else:
            secao_atual.append(linha)
    if secao_atual:
        secoes.append((titulo_atual, secao_atual))

    chunks: list[str] = []
    for titulo, linhas_secao in secoes:
        texto_secao = "\n".join(linhas_secao)
        if len(texto_secao) <= max_chars:
            chunks.append(f"[{titulo}]\n{texto_secao}")
        else:
            subc = chunk_text(texto_secao, max_chars=max_chars)
            for i, parte in enumerate(subc):
                chunks.append(f"[{titulo} - Parte {i+1}/{len(subc)}]\n{parte}")
    return chunks


def _monta_chunks_ipe(
    text: str,
    header: str,
    cd_cvm,
    denom,
    categoria,
    dt_refer,
    doc_id,
    link,
    dt_entrega,
    usar_secao: bool = True,
) -> list[ChunkIn]:
    """Constrói ChunkIn a partir do texto extraído, opcionalmente por seção."""
    if usar_secao:
        partes = _chunk_por_secao(text, settings.chunk_max_chars)
    else:
        partes = chunk_text(text, settings.chunk_max_chars)
    return [
        ChunkIn(
            source="cvm_ipe",
            content=f"{header}\n{parte}",
            cd_cvm=cd_cvm,
            denom=denom,
            doc_type=categoria,
            ref_date=dt_refer,
            title=doc_id,
            url=link,
            chunk_idx=i,
            metadata={
                "doc_id": doc_id,
                "dt_entrega": str(dt_entrega) if dt_entrega else None,
                "formato": "texto",
                "secao": i,
            },
        )
        for i, parte in enumerate(partes)
    ]


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    m = {norm(c).replace(" ", "_").lower(): c for c in df.columns}
    return df[m[name]] if name in m else pd.Series([None] * len(df), index=df.index)


def list_categories(year: int) -> list[tuple[str, int]]:
    path = fetch("ipe", year)
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        df = pd.read_csv(z.open(name), sep=";", encoding="latin-1", dtype=str)
    vc = _col(df, "categoria").value_counts()
    return [(k, int(v)) for k, v in vc.items()]


def sync_index(conn, years: list[int], cd_cvms: list[int] | None, categories: list[str]) -> int:
    """Registra em documentos_ipe os documentos das categorias pedidas (status=pendente)."""
    wanted = {norm(c) for c in categories}
    total = 0
    for year in years:
        path = fetch("ipe", year)
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            df = pd.read_csv(z.open(name), sep=";", encoding="latin-1", dtype=str)
        cat = _col(df, "categoria").fillna("").map(norm)
        df = df[cat.isin(wanted)].copy()
        cds = pd.to_numeric(_col(df, "codigo_cvm"), errors="coerce")
        if cd_cvms:
            df = df[cds.isin(cd_cvms)]
            cds = cds[df.index]
        if df.empty:
            continue
        c = {n: _col(df, n) for n in (
            "protocolo_entrega", "versao", "data_referencia", "nome_companhia", "categoria", "tipo",
            "especie", "assunto", "data_entrega", "link_download")}
        rows = []
        for i in df.index:
            ver = c["versao"][i] or "1"
            dt = pd.to_datetime(c["data_referencia"][i], errors="coerce")
            rows.append((
                f"{c['protocolo_entrega'][i]}-{ver}", int(cds[i]) if pd.notna(cds[i]) else None,
                c["nome_companhia"][i], c["categoria"][i], c["tipo"][i], c["especie"][i], c["assunto"][i],
                dt.date() if pd.notna(dt) else None, c["data_entrega"][i], c["link_download"][i],
            ))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO documentos_ipe (doc_id, cd_cvm, denom, categoria, tipo, especie, assunto, "
                "dt_refer, dt_entrega, link) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (doc_id) DO NOTHING", rows,
            )
        conn.commit()
        total += len(rows)
    return total


def process_pending(conn, client: OllamaClient, *, limit: int, cd_cvms: list[int] | None, log=print) -> dict:
    sql = ("SELECT doc_id, cd_cvm, denom, categoria, assunto, dt_refer, dt_entrega, link "
           "FROM documentos_ipe WHERE status='pendente'")
    args: list = []
    if cd_cvms:
        sql += " AND cd_cvm = ANY(%s)"; args.append(cd_cvms)
    sql += " ORDER BY dt_refer DESC NULLS LAST LIMIT %s"; args.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        docs = cur.fetchall()
    stats = {"indexado": 0, "ignorado": 0, "erro": 0, "chunks": 0}
    for doc_id, cd, denom, categoria, assunto, dt_refer, dt_entrega, link in docs:
        status, err, n = "indexado", None, 0
        try:
            r = httpx.get(link, timeout=settings.http_timeout, follow_redirects=True)
            r.raise_for_status()
            text, fmt = extract_text(r.content)
            if not text or len(text) < 200:
                status, err = "ignorado", f"formato={fmt} sem texto utilizável"
            else:
                header = (f"Empresa: {denom} (CD_CVM {cd}) | {categoria} - {assunto} | "
                          f"Data de referência: {dt_refer} | Documento {doc_id}")
                chunks = _monta_chunks_ipe(
                    text=text,
                    header=header,
                    cd_cvm=cd,
                    denom=denom,
                    categoria=categoria,
                    dt_refer=dt_refer,
                    doc_id=doc_id,
                    link=link,
                    dt_entrega=dt_entrega,
                    usar_secao=True,
                )
                index_chunks(conn, client, chunks)
                n = len(chunks)
        except Exception as e:  # noqa: BLE001 - registrar e seguir
            status, err = "erro", str(e)[:300]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documentos_ipe SET status=%s, erro=%s, n_chunks=%s, updated_at=now() WHERE doc_id=%s",
                (status, err, n, doc_id),
            )
        conn.commit()
        stats[status] += 1
        stats["chunks"] += n
        log(f"  [{status}] {denom} - {assunto} ({n} chunks){' - ' + err if err else ''}")
    return stats
