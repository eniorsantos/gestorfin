import pandas as pd

from finllm.cvm.load import COLS, transform_frame


def _df():
    base = dict(CNPJ_CIA="1", DENOM_CIA="EMPRESA X", CD_CVM="123", MOEDA="REAL", ESCALA_MOEDA="MIL",
                DT_REFER="2023-12-31", DT_INI_EXERC="2023-01-01", DT_FIM_EXERC="2023-12-31",
                CD_CONTA="3.01", DS_CONTA="Receita", ST_CONTA_FIXA="S")
    rows = [
        {**base, "VERSAO": "1", "ORDEM_EXERC": "ÚLTIMO", "VL_CONTA": "100.0"},        # versão antiga
        {**base, "VERSAO": "2", "ORDEM_EXERC": "ÚLTIMO", "VL_CONTA": "110.0"},        # reapresentação (vale)
        {**base, "VERSAO": "2", "ORDEM_EXERC": "PENÚLTIMO", "VL_CONTA": "90.0"},      # exercício anterior (descarta)
        {**base, "VERSAO": "2", "ORDEM_EXERC": "ÚLTIMO", "CD_CVM": "999", "VL_CONTA": "5"},
        {**base, "VERSAO": "2", "ORDEM_EXERC": "ÚLTIMO", "CD_CONTA": "3.02", "ESCALA_MOEDA": "UNIDADE", "VL_CONTA": "7"},
    ]
    return pd.DataFrame(rows)


def test_transform_versao_ordem_escala():
    out = transform_frame(_df(), tipo_doc="dfp", demonstracao="DRE", consolidacao="con")
    assert list(out.columns) == COLS
    r = out[(out.cd_cvm == 123) & (out.cd_conta == "3.01")]
    assert len(r) == 1 and float(r.vl_conta.iloc[0]) == 110_000.0   # versão 2, escala MIL
    r2 = out[(out.cd_cvm == 123) & (out.cd_conta == "3.02")]
    assert float(r2.vl_conta.iloc[0]) == 7.0                          # UNIDADE
    assert not (out.vl_conta == 90_000).any()


def test_transform_filtra_empresa():
    out = transform_frame(_df(), tipo_doc="DFP", demonstracao="DRE", consolidacao="con", cd_cvms=[999])
    assert set(out.cd_cvm) == {999}


def test_transform_sem_colunas_opcionais():
    df = _df().drop(columns=["DT_INI_EXERC"])
    out = transform_frame(df, tipo_doc="DFP", demonstracao="BPA", consolidacao="con")
    assert out["dt_ini_exerc"].isna().all()
