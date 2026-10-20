"""Download dos dados abertos da CVM (https://dados.cvm.gov.br)."""
from __future__ import annotations

from pathlib import Path

import httpx

from ..config import settings


class NotPublished(Exception):
    pass


def url_for(kind: str, year: int | None = None) -> str:
    base = settings.cvm_base_url
    kind = kind.lower()
    if kind == "cad":
        return f"{base}/CAD/DADOS/cad_cia_aberta.csv"
    if kind == "dfp":
        return f"{base}/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
    if kind == "itr":
        return f"{base}/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
    if kind == "ipe":
        return f"{base}/DOC/IPE/DADOS/ipe_cia_aberta_{year}.zip"
    raise ValueError(f"tipo desconhecido: {kind}")


def local_path(kind: str, year: int | None = None) -> Path:
    name = url_for(kind, year).rsplit("/", 1)[-1]
    return settings.data_dir / "raw" / kind.lower() / name


def fetch(kind: str, year: int | None = None, *, force: bool = False) -> Path:
    dest = local_path(kind, year)
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = url_for(kind, year)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, timeout=settings.http_timeout, follow_redirects=True) as r:
        if r.status_code == 404:
            raise NotPublished(url)
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest
