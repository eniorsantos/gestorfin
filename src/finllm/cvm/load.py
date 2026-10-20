"""Carga das demonstrações (DFP/ITR) e do cadastro de companhias no Postgres."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

STATEMENTS = {
    "DRE": "Demonstração do Resultado",
    "BPA": "Balanço Patrimonial - Ativo",
    "BPP": "Balanço Patrimonial - Passivo",
    "DFC_MD": "Fluxo de Caixa (Método Direto)",
    "DFC_MI": "Fluxo de Caixa (Método Indireto)",
    "DVA": "Demonstração do Valor Adicionado",
    "DRA": "Demonstração do Resultado Abrangente",
}
CONS = {"con": "Consolidado", "ind": "Individual"}

_FILE_RE = re.compile(r"^(?P<tipo>dfp|itr)_cia_aberta_(?P<dem>[A-Z_]+)_(?P<cons>con|ind)_(?P<ano>\d{4})\.csv$")

COLS = [
    "cd_cvm", "cnpj", "denom", "tipo_doc", "demonstracao", "consolidacao", "dt_refer", "dt_ini_exerc",
    "dt_fim_exerc", "versao", "moeda", "escala", "cd_conta", "ds_conta", "vl_conta", "st_conta_fixa",
]
_DEDUP = ["cd_cvm", "dt_refer", "dt_ini_exerc", "cd_conta"]


def transform_frame(
    df: pd.DataFrame, *, tipo_doc: str, demonstracao: str, consolidacao: str,
    cd_cvms: list[int] | None = None,
) -> pd.DataFrame:
    """CSV bruto da CVM -> linhas prontas para o banco.

    - mantém só ORDEM_EXERC = ÚLTIMO (o PENÚLTIMO é repetição do exercício anterior);
    - mantém só a maior VERSAO por (companhia, data-base) — reapresentações;
    - aplica ESCALA_MOEDA (MIL x1000) => valores em reais.
    """
    ordem = df["ORDEM_EXERC"].str.upper()
    df = df[ordem.str.contains("LTIMO", na=False) & ~ordem.str.contains("PEN", na=False)].copy()
    df["CD_CVM"] = pd.to_numeric(df["CD_CVM"], errors="coerce")
    df = df.dropna(subset=["CD_CVM"])
    if cd_cvms:
        df = df[df["CD_CVM"].astype(int).isin(cd_cvms)]
    if df.empty:
        return pd.DataFrame(columns=COLS)

    df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce").fillna(0).astype(int)
    df = df[df["VERSAO"] == df.groupby(["CD_CVM", "DT_REFER"])["VERSAO"].transform("max")]
    escala = df["ESCALA_MOEDA"].str.upper().map({"MIL": 1000, "UNIDADE": 1}).fillna(1)
    out = pd.DataFrame({
        "cd_cvm": df["CD_CVM"].astype(int),
        "cnpj": df.get("CNPJ_CIA"),
        "denom": df.get("DENOM_CIA"),
        "tipo_doc": tipo_doc.upper(),
        "demonstracao": demonstracao,
        "consolidacao": consolidacao,
        "dt_refer": df["DT_REFER"],
        "dt_ini_exerc": df.get("DT_INI_EXERC"),
        "dt_fim_exerc": df.get("DT_FIM_EXERC"),
        "versao": df["VERSAO"],
        "moeda": df.get("MOEDA"),
        "escala": escala.astype(int),
        "cd_conta": df["CD_CONTA"],
        "ds_conta": df.get("DS_CONTA"),
        "vl_conta": pd.to_numeric(df["VL_CONTA"], errors="coerce") * escala,
        "st_conta_fixa": df.get("ST_CONTA_FIXA"),
    })
    out = out.dropna(subset=["vl_conta"]).drop_duplicates(subset=_DEDUP)
    return out[COLS]


def load_zip(
    conn, path: Path, *, tipo_doc: str, statements: list[str], cd_cvms: list[int] | None = None,
    log=print,
) -> int:
    """Carrega um zip DFP/ITR. Idempotente: apaga e reinsere as (data-base, demonstração) tocadas."""
    total = 0
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            m = _FILE_RE.match(name)
            if not m or m["dem"] not in statements:
                continue
            with z.open(name) as f:
                raw = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)
            out = transform_frame(
                raw, tipo_doc=tipo_doc, demonstracao=m["dem"], consolidacao=m["cons"], cd_cvms=cd_cvms
            )
            if out.empty:
                continue
            datas = sorted(out["dt_refer"].unique())
            rows = out.astype(object).where(out.notna(), None)
            with conn.cursor() as cur:
                dele = (
                    "DELETE FROM demonstracoes WHERE tipo_doc=%s AND demonstracao=%s AND consolidacao=%s "
                    "AND dt_refer = ANY(%s::date[])"
                )
                args: list = [tipo_doc.upper(), m["dem"], m["cons"], datas]
                if cd_cvms:
                    dele += " AND cd_cvm = ANY(%s)"
                    args.append(cd_cvms)
                cur.execute(dele, args)
                with cur.copy(f"COPY demonstracoes ({', '.join(COLS)}) FROM STDIN") as cp:
                    for row in rows.itertuples(index=False, name=None):
                        cp.write_row(row)
            conn.commit()
            total += len(out)
            log(f"  {name}: {len(out):,} linhas")
    return total


def load_cadastro(conn, path: Path) -> int:
    df = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
    df["CD_CVM"] = pd.to_numeric(df["CD_CVM"], errors="coerce")
    df = df.dropna(subset=["CD_CVM", "DENOM_SOCIAL"]).drop_duplicates("CD_CVM")
    rows = [
        (int(r.CD_CVM), getattr(r, "CNPJ_CIA", None), r.DENOM_SOCIAL, getattr(r, "SETOR_ATIV", None),
         getattr(r, "SIT", None))
        for r in df.itertuples()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO empresas (cd_cvm, cnpj, denom, setor, situacao) VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT (cd_cvm) DO UPDATE SET cnpj=EXCLUDED.cnpj, denom=EXCLUDED.denom, "
            "setor=EXCLUDED.setor, situacao=EXCLUDED.situacao, updated_at=now()",
            rows,
        )
    conn.commit()
    return len(rows)


SETOR_MAP = {
    "BANCOS": "bancos",
    "SEGUROS": "seguros",
    "UTILIDADES PÚBLICAS": "utilities",
    "ENERGIA ELÉTRICA": "utilities",
    "SANEAMENTO": "utilities",
}


def normalizar_setores(conn) -> int:
    """Normaliza o setor da CVM em categoria padrão e grava em tabela setores."""
    with conn.cursor() as cur:
        cur.execute("SELECT cd_cvm, denom, setor FROM empresas")
        rows = cur.fetchall()
    inseridos = 0
    with conn.cursor() as cur:
        for cd, denom, setor_cvm in rows:
            key = (setor_cvm or "").strip().upper()
            setor_norm = SETOR_MAP.get(key, "outros")
            cur.execute(
                """
                INSERT INTO setores (cd_cvm, denom, setor_cvm, setor_norm)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cd_cvm) DO UPDATE SET
                    denom=EXCLUDED.denom, setor_cvm=EXCLUDED.setor_cvm,
                    setor_norm=EXCLUDED.setor_norm, updated_at=now()
                """,
                (cd, denom, setor_cvm, setor_norm),
            )
            inseridos += 1
        conn.commit()
    return inseridos


__all__ = [
    "STATEMENTS",
    "CONS",
    "SETOR_MAP",
    "transform_frame",
    "load_zip",
    "load_cadastro",
    "normalizar_setores",
]
