"""DDL do banco. A dimensão do vetor vem de EMBED_DIM (troque de modelo => reindexe)."""
from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS empresas (
  cd_cvm      integer PRIMARY KEY,
  cnpj        text,
  denom       text NOT NULL,
  setor       text,
  situacao    text,
  updated_at  timestamptz DEFAULT now()
);

-- Demonstrações padronizadas (DFP anual / ITR trimestral). Valores SEMPRE em reais (escala já aplicada).
CREATE TABLE IF NOT EXISTS demonstracoes (
  id             bigserial PRIMARY KEY,
  cd_cvm         integer NOT NULL,
  cnpj           text,
  denom          text,
  tipo_doc       text NOT NULL,        -- DFP | ITR
  demonstracao   text NOT NULL,        -- DRE | BPA | BPP | DFC_MD | DFC_MI | DVA | DRA
  consolidacao   text NOT NULL,        -- con | ind
  dt_refer       date NOT NULL,
  dt_ini_exerc   date,
  dt_fim_exerc   date,
  versao         integer,
  moeda          text,
  escala         integer,
  cd_conta       text NOT NULL,
  ds_conta       text,
  vl_conta       numeric,
  st_conta_fixa  text
);
CREATE INDEX IF NOT EXISTS ix_demo_emp_dt ON demonstracoes (cd_cvm, dt_refer);
CREATE INDEX IF NOT EXISTS ix_demo_lookup ON demonstracoes (tipo_doc, demonstracao, consolidacao, cd_conta);

CREATE TABLE IF NOT EXISTS documentos_ipe (
  doc_id      text PRIMARY KEY,        -- protocolo-versao
  cd_cvm      integer,
  denom       text,
  categoria   text,
  tipo        text,
  especie     text,
  assunto     text,
  dt_refer    date,
  dt_entrega  text,
  link        text,
  status      text DEFAULT 'pendente', -- pendente | indexado | erro | ignorado
  n_chunks    integer,
  erro        text,
  updated_at  timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ipe_status ON documentos_ipe (status, cd_cvm);

CREATE TABLE IF NOT EXISTS chunks (
  id            bigserial PRIMARY KEY,
  source        text NOT NULL,         -- cvm_statement | cvm_ipe
  cd_cvm        integer,
  denom         text,
  doc_type      text,
  ref_date      date,
  title         text,
  url           text,
  chunk_idx     integer DEFAULT 0,
  content       text NOT NULL,
  content_hash  text NOT NULL UNIQUE,
  metadata      jsonb DEFAULT '{}'::jsonb,
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', content)) STORED,
  embedding     vector({dim}),
  created_at    timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_chunks_emb ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS ix_chunks_emp ON chunks (cd_cvm, ref_date);
CREATE INDEX IF NOT EXISTS ix_chunks_src ON chunks (source);

CREATE TABLE IF NOT EXISTS setores (
  cd_cvm      integer PRIMARY KEY,
  denom       text,
  setor_cvm   text,
  setor_norm  text,
  updated_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consultas (
  id             bigserial PRIMARY KEY,
  pergunta       text NOT NULL,
  modelo         text NOT NULL,
  temperatura    real,
  seed           integer,
  num_ctx        integer,
  filtros        jsonb DEFAULT '{}'::jsonb,
  chunk_ids      jsonb DEFAULT '[]'::jsonb,
  resposta       jsonb DEFAULT '{}'::jsonb,
  validacao      jsonb DEFAULT '{}'::jsonb,
  criado_em      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_consultas_criado_em ON consultas (criado_em);

CREATE TABLE IF NOT EXISTS cotacoes (
  ticker      text NOT NULL,
  data        date NOT NULL,
  open        numeric,
  high        numeric,
  low         numeric,
  close       numeric,
  volume      bigint,
  fonte       text DEFAULT 'placeholder',
  criado_em   timestamptz DEFAULT now(),
  PRIMARY KEY (ticker, data)
);
CREATE INDEX IF NOT EXISTS ix_cotacoes_ticker_data ON cotacoes (ticker, data);

CREATE TABLE IF NOT EXISTS indicadores_calc (
  id            bigserial PRIMARY KEY,
  cd_cvm        integer NOT NULL,
  ticker        text,
  dt_refer      date NOT NULL,
  pl            numeric,
  roe           numeric,
  roic          numeric,
  div_liq_ebitda numeric,
  f_score       integer,
  calculado_em  timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_indicadores_calc_cd_dt ON indicadores_calc (cd_cvm, dt_refer);

CREATE TABLE IF NOT EXISTS sinais_tecnicos (
  id          bigserial PRIMARY KEY,
  ticker      text NOT NULL,
  data        date NOT NULL,
  sinal       text NOT NULL,        -- compra, venda, neutro
  indicador   text,                 -- rsi, macd, suporte, resistencia, etc.
  valor       numeric,
  fonte       text,
  criado_em   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sinais_tecnicos_ticker_data ON sinais_tecnicos (ticker, data);

CREATE TABLE IF NOT EXISTS backtest_resultados (
  id             bigserial PRIMARY KEY,
  nome           text NOT NULL,
  ticker         text,
  periodo_ini    date,
  periodo_fim    date,
  retorno_total  numeric,
  sharpe         numeric,
  drawdown_max   numeric,
  n_operacoes    integer,
  parametros     jsonb DEFAULT '{}'::jsonb,
  criado_em      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alertas (
  id          bigserial PRIMARY KEY,
  ticker      text NOT NULL,
  tipo        text NOT NULL,        -- preco, indicador, notícia
  condicao    text NOT NULL,
  valor_referencia numeric,
  ativo       boolean DEFAULT true,
  criado_em   timestamptz DEFAULT now(),
  disparado_em timestamptz
);
CREATE INDEX IF NOT EXISTS ix_alertas_ativo ON alertas (ativo);
"""


def init_db(conn, dim: int) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute(SCHEMA_SQL.replace("{dim}", str(dim)))
        cur.execute(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        )
        current = cur.fetchone()[0]
        if current != dim:
            raise RuntimeError(
                f"Tabela chunks usa vector({current}) mas EMBED_DIM={dim}. "
                "Ao trocar o modelo de embeddings: DROP TABLE chunks; finllm db init; reindexe."
            )
    conn.commit()
