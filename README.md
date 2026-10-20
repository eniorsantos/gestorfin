# finllm — Análise financeira com LLM local (Ollama)

Sistema completo de apoio à análise financeira fundamentalista e técnica, com **LLM local (Ollama)**, **RAG híbrido sobre dados abertos da CVM**, **benchmark de modelos**, **motor determinístico de indicadores**, **motor técnico**, **agentes de análise**, **backtest point-in-time**, **dashboard Streamlit**, **auditoria persistida** e **suite completa de testes** (carga, segurança, usabilidade, desempenho).

> **Princípio:** o LLM não calcula nem "lembra" números. Números vêm de dados estruturados e código determinístico; o LLM interpreta, resume e cita. Toda resposta passa por validação numérica contra o contexto.
>
> ⚠️ Ferramenta de apoio à análise. **Não é recomendação de investimento.**

---

## Índice

1. [Visão geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [O que foi implementado (todas as fases do roadmap)](#o-que-foi-implementado)
4. [Módulos de código detalhados](#módulos-de-código-detalhados)
5. [Modelo de dados](#modelo-de-dados)
6. [CLI e comandos](#cli-e-comandos)
7. [Quickstart](#quickstart)
8. [Testes (carga, segurança, usabilidade, desempenho)](#testes)
9. [Roadmap e status](#roadmap-e-status)
10. [Decisões de arquitetura (ADRs)](#decisões-de-arquitetura-adrs)
11. [Limites e avisos](#limites-e-avisos)

---

## Visão geral

O `finllm` permite responder perguntas sobre empresas listadas na B3 usando dados oficiais da CVM (Comissão de Valores Mobiliários), com citação de fonte e verificação automática dos números. O sistema roda inteiramente local via Ollama, sem envio de dados para provedores externos.

O projeto é dividido em camadas:

| Camada | Responsabilidade |
|--------|------------------|
| **Infraestrutura** | Docker Compose (Postgres + pgvector, Ollama, app, Adminer), overrides de GPU (NVIDIA/AMD/Mac) |
| **Ingestão CVM** | Download e carga de cadastro, DFP, ITR, IPE, DFC/DVA; normalização por setor |
| **Pipeline RAG** | Cartões textuais, chunking por seção, embeddings (bge-m3), busca híbrida vetorial + FTS com RRF, guardrails numéricos |
| **Motor determinístico** | Indicadores fundamentalistas (P/L, ROE, ROIC, dívida líquida/EBITDA, F-Score Piotroski) |
| **Motor técnico** | OHLCV (yfinance), SMA/EMA/RSI/MACD/Bollinger, suportes/resistências, sinais de compra/venda |
| **Agentes** | Fundamentalista, técnico, risco ("advogado do diabo") e sintetizador com score composto |
| **Backtest** | Simulação point-in-time de estratégia baseada em sinais dos agentes |
| **Benchmark** | Comparação de modelos Ollama (acurácia, abstenção, cálculo, tools, JSON, velocidade, VRAM) |
| **Avaliação contínua** | Regressão de benchmark em CI contra referência salva |
| **Dashboard** | Streamlit com visão geral, screener B3, indicadores, técnico, agentes, alertas e auditoria |
| **Auditoria** | Tabela `consultas` persistida com pergunta, modelo, filtros, chunks, resposta e validação |

---

## Arquitetura

```
Fontes (CVM: cadastro, DFP, ITR, IPE)
    │
    ▼
Ingestão (download → load → transform_frame → Postgres)
    │
    ▼
PostgreSQL + pgvector (empresas, demonstracoes, documentos_ipe, chunks, setores, consultas, alertas, …)
    │
    ▼
RAG (cartões → chunks → embeddings → busca híbrida vetorial+FTS+RRF → resposta JSON + guardrails)
    │
    ▼
Ollama (chat com JSON schema / function calling, embeddings via /api/embed)
    │
    ▼
Resposta citada + validação numérica determinística
```

**Fluxo de indexação (offline):**
1. `cvm download` → baixa CSVs/zips da CVM para `data/raw/`
2. `cvm load` → carrega cadastro e DFP/ITR no Postgres (idempotente, escala MIL→reais, só versão mais recente)
3. `rag index-statements` → gera cartões textuais por (empresa, documento, demonstração, consolidação, período) e indexa com embeddings
4. `cvm ipe-sync` + `rag index-ipe` → indexa documentos narrativos (PDF/HTML/texto) com chunking por seção

**Fluxo de consulta (online) — `rag ask`:**
1. Detecta empresa e anos na pergunta; filtra busca híbrida (vetorial cosseno + FTS português, fusão RRF)
2. Gera resposta em JSON schema via Ollama (`temperature=0`, `seed` fixo, `num_ctx` explícito)
3. Valida números da resposta contra o contexto (1 retry guiado se houver números não suportados)
4. Registra na auditoria (opcional)

---

## O que foi implementado (todas as fases do roadmap)

### Fase 1 — Infraestrutura, ingestão CVM, RAG híbrido, guardrail, benchmark ✅
- Docker Compose com Postgres (pgvector/pg16), Ollama, model-puller, app, Adminer
- Overrides de GPU: NVIDIA, AMD (ROCm), Mac (Ollama nativo)
- Ingestão de cadastro, DFP, ITR, IPE da CVM
- Pipeline RAG híbrido com cartões textuais, embeddings bge-m3, busca vetorial + FTS com fusão RRF
- Guardrail numérico: todo número da resposta deve existir no contexto
- Benchmark de modelos: rag_fact, rag_abstain, rag_calc, classif, tools; IC 95% de Wilson, VRAM, velocidade

### Fase 2 — Auditoria persistida, normalização por setor, DFC/DVA ✅
- Tabela `consultas` (pergunta, modelo, temperatura, seed, num_ctx, filtros, chunk_ids, resposta, validacao, criado_em)
- Comando `finllm auditoria list`
- Tabela `setores` com mapeamento CVM → categoria padrão (bancos, seguros, utilities, outros)
- Comando `finllm cvm setor-normalizar`
- Carga de DFC/DVA via `finllm cvm load-dfc-dva`

### Fase 3 — Motor fundamentalista determinístico como tools ✅
- `src/finllm/fundamentalista.py`: P/L, ROE, ROIC, dívida líquida/EBITDA, F-Score Piotroski (0-9)
- `src/finllm/rag/tools.py`: tools reais `get_indicadores`, `buscar_documentos`, `get_cotacoes`, `get_macro`
- Integração com function calling no fluxo `rag ask --use-tools`
- Comando `finllm indicadores calc <ticker>`

### Fase 4 — Motor técnico (OHLCV, indicadores, sinais) ✅
- `src/finllm/tecnico.py`: SMA (20/50/200), EMA (12/26), RSI (14), MACD, Bandas de Bollinger, suportes/resistências
- Integração com yfinance para cotações reais
- Tools `get_indicadores_tecnicos` e `get_sinal_tecnico`
- Comandos `finllm tecnico sinal <ticker>` e `finllm tecnico indicadores <ticker>`

### Fase 5 — Agentes de análise ✅
- `src/finllm/agentes.py`: 4 agentes (fundamentalista, técnico, risco/advogado do diabo, sintetizador)
- Score composto ponderado (fundamentalista 40%, técnico 30%, risco 30%)
- Comando `finllm agentes analisar <ticker>`
- Saída com sinal final, confiança, score composto, síntese e riscos principais

### Fase 6 — Backtest point-in-time ✅
- `src/finllm/backtest.py`: simulação nativa (com suporte opcional a vectorbt)
- Métricas: retorno total, Sharpe, drawdown máximo, número de operações
- Curva de patrimônio
- Comando `finllm backtest run`

### Fase 7 — Dashboard, alertas, screener da B3 ✅
- `src/finllm/dashboard/`: app Streamlit com 7 páginas
  - Visão geral (métricas + últimas consultas auditadas)
  - Screener B3 (filtro por setor + indicadores)
  - Indicadores fundamentalistas
  - Indicadores técnicos
  - Agentes de análise
  - Alertas (CRUD)
  - Auditoria de consultas
- Comando `finllm dashboard up [--porta 8501]`
- Tabela `alertas` no schema

### Fase 8 — Avaliação contínua, OCR, reranker cross-encoder ✅
- `src/finllm/avaliacao.py`: regressão de benchmark em CI, comparação com referência salva, limiar configurável
- Comandos `finllm avaliacao regressao` e `finllm avaliacao salvar-referencia`
- `src/finllm/ocr.py`: OCR para PDFs escaneados (pytesseract opcional)
- `src/finllm/rerank_crossencoder.py`: reranker cross-encoder (sentence-transformers) com fallback offline

---

## Melhorias candidatas (implementadas) ✅

| Melhoria | Status | Onde |
|----------|--------|------|
| Reranker local (cross-encoder) sobre top-N | ✅ | `src/finllm/rerank_crossencoder.py`, `rag rerank-test` |
| Consulta SQL direta para perguntas numéricas | ✅ | `src/finllm/rag/sql_direct.py` |
| Chunking por seção para PDFs | ✅ | `src/finllm/cvm/ipe.py: _chunk_por_secao` |
| Data de entrega (point-in-time) nos metadados | ✅ | `retrieve.data_entrega_max`, `rag ask --data-entrega` |
| Cache de respostas e embeddings | ✅ | `src/finllm/cache.py`, `rag cache-limpar` |
| OCR para PDFs escaneados | ✅ | `src/finllm/ocr.py` |

---

## Módulos de código detalhados

### `src/finllm/` (raiz do pacote)

| Arquivo | Função |
|---------|--------|
| `cli.py` | CLI Typer com todos os comandos (db, cvm, rag, bench, indicadores, tecnico, agentes, backtest, avaliacao, dashboard, auditoria) |
| `config.py` | Configuração central via variáveis de ambiente / `.env` (pydantic-settings) |
| `db.py` | Conexão com Postgres (psycopg) |
| `schema.py` | DDL completo: empresas, demonstracoes, documentos_ipe, chunks, setores, consultas, cotacoes, indicadores_calc, sinais_tecnicos, backtest_resultados, alertas |
| `auditoria.py` | Registro e listagem de consultas para rastreabilidade |

### `src/finllm/cvm/` (ingestão CVM)

| Arquivo | Função |
|---------|--------|
| `download.py` | Download de cadastro, DFP, ITR, IPE da CVM (URL configurável, detecção de não-publicado) |
| `load.py` | Carga idempotente de cadastro e DFP/ITR; `transform_frame` (apenas ÚLTIMO, maior versão, escala MIL→reais, deduplicação); `normalizar_setores`; `load_dfc_dva` |
| `ipe.py` | Registro e indexação de documentos IPE; `_chunk_por_secao` (chunking por seção); `_monta_chunks_ipe` com metadata de `dt_entrega` |

### `src/finllm/rag/` (pipeline RAG)

| Arquivo | Função |
|---------|--------|
| `cards.py` | Geração de cartões textuais por (empresa, documento, demonstração, consolidação, período) com cabeçalho repetido |
| `entities.py` | Resolução heurística de empresas por nome (normalização, stop-words, aliases, detecção de ambiguidade) |
| `guardrails.py` | Validação determinística: todo número da resposta deve existir no contexto (ignora anos 1900-2100 e inteiros ≤ 31) |
| `index.py` | Embeddings via Ollama `/api/embed` (batches de 16, idempotência por content_hash SHA-256, checagem de dimensão) |
| `retrieve.py` | Busca híbrida: vetorial (pgvector HNSW cosseno) + FTS português (tsvector) + fusão RRF; filtro por empresa/ano; `data_entrega_max` para point-in-time |
| `answer.py` | Geração com JSON schema, 1 retry guiado, function calling (tools reais), registro de auditoria |
| `text.py` | Extração de texto (PDF via PyMuPDF, HTML via BeautifulSoup) e chunking por parágrafos com overlap |
| `tools.py` | Implementação real das tools: `get_indicadores`, `get_cotacoes` (yfinance), `buscar_documentos`, `get_macro`, `get_indicadores_tecnicos`, `get_sinal_tecnico` |
| `sql_direct.py` | Consulta SQL direta para perguntas puramente numéricas (mapeia sinônimos de conta → código CVM) |
| `rerank.py` | Reranker leve por overlap de tokens |
| `cache.py` | Cache de respostas e embeddings em disco (JSON) |

### `src/finllm/bench/` (benchmark)

| Arquivo | Função |
|---------|--------|
| `dataset.py` | Geração de dataset de avaliação a partir do próprio banco (rag_fact, rag_abstain, rag_calc); modos gold e retrieved |
| `tasks.py` | Tarefas embutidas: classif (10 manchetes sintéticas de sentimento PT-BR), tools (8 pedidos de function calling); `executar_tool` para tools reais |
| `hardware.py` | Detecção de hardware (CPU, RAM, GPU via nvidia-smi, versão do Ollama) |
| `metrics.py` | Acurácia com IC 95% de Wilson, tolerâncias (0,5% / 0,5 mil, ±0,1 p.p.), `resp_errada_confiante`, `alucinacao_abstain`, `cite_ok`, `json_valid`, `recall@k` |
| `report.py` | Agregação de resultados → summary.csv + detail.csv + report.md; score composto ponderado |
| `runner.py` | Execução do benchmark (warm-up, múltiplos repeats, medição de VRAM/offload via `/api/ps`, unload ao final) |

### `src/finllm/` (módulos de negócio adicionais)

| Arquivo | Função |
|---------|--------|
| `fundamentalista.py` | Indicadores fundamentalistas determinísticos (P/L, ROE, ROIC, dívida líquida/EBITDA, F-Score Piotroski) |
| `tecnico.py` | Indicadores técnicos (SMA/EMA/RSI/MACD/Bollinger, suportes/resistências, sinais) |
| `agentes.py` | 4 agentes + sintetizador com score composto |
| `backtest.py` | Backtest point-in-time nativo (vectorbt opcional) |
| `avaliacao.py` | Regressão de benchmark em CI contra referência salva |
| `ocr.py` | OCR para PDFs escaneados (pytesseract opcional) |
| `rerank_crossencoder.py` | Reranker cross-encoder com fallback offline |
| `cache.py` | Cache de respostas e embeddings |

### `src/finllm/dashboard/` (Fase 7)

| Arquivo | Função |
|---------|--------|
| `db.py` | Acesso ao banco com fallback offline (sem Postgres) |
| `app.py` | App Streamlit com 7 páginas (visão geral, screener, indicadores, técnico, agentes, alertas, auditoria) |

---

## Modelo de dados

### Tabelas principais

| Tabela | Chave | Descrição |
|--------|-------|-----------|
| `empresas` | `cd_cvm` (PK) | Companhias listadas na CVM (nome, CNPJ, setor, situação) |
| `demonstracoes` | `id` (serial) | DFP/ITR: valores em reais, por conta, consolidação, período |
| `documentos_ipe` | `doc_id` (PK) | Documentos narrativos (fatos relevantes, comunicados) com `dt_entrega` |
| `chunks` | `id` (serial) | Chunks indexados: conteúdo, embedding (vector HNSW), tsvector (GIN), metadata JSONB |
| `setores` | `cd_cvm` (PK) | Normalização de setor (bancos, seguros, utilities, outros) |
| `consultas` | `id` (serial) | Auditoria: pergunta, modelo, filtros, chunks, resposta, validação |
| `cotacoes` | `(ticker, data)` (PK) | Série histórica de preços OHLCV |
| `indicadores_calc` | `id` (serial) | Indicadores fundamentalistas calculados e armazenados |
| `sinais_tecnicos` | `id` (serial) | Sinais técnicos gerados |
| `backtest_resultados` | `id` (serial) | Resultados de backtest (retorno, Sharpe, drawdown, operações) |
| `alertas` | `id` (serial) | Alertas de preço/indicador por ticker |

Índices: HNSW (cosseno) em `chunks.embedding`, GIN em `chunks.tsv`, B-tree em `chunks(cd_cvm, ref_date)`, `chunks(source)`, `demonstracoes(cd_cvm, dt_refer)`, `consultas(criado_em)`, `alertas(ativo)`.

---

## CLI e comandos

```
finllm db init | stats
finllm cvm download | load | ipe-categories | ipe-sync | setor-normalizar | load-dfc-dva
finllm rag index-statements | index-ipe | search | ask [--use-tools] [--data-entrega YYYY-MM-DD] | cache-limpar | rerank-test
finllm bench hardware | build | run | report
finllm indicadores calc <ticker> [--data YYYY-MM-DD]
finllm tecnico sinal <ticker> [--periodo 6m]
finllm tecnico indicadores <ticker> [--periodo 6m]
finllm agentes analisar <ticker>
finllm backtest run [--ticker PETR4] [--capital 100000] [--comissao 0.001]
finllm auditoria list [--limit N]
finllm avaliacao regressao <resumo_csv> [--referencia-json ref.json] [--limiar 0.05]
finllm avaliacao salvar-referencia <resumo_csv> <saida.json>
finllm dashboard up [--porta 8501]
```

### Exemplos de uso

```bash
# 1. Sobe o ambiente (NVIDIA GPU)
make up-nvidia

# 2. Ingestão de dados
make pipeline EMPRESAS="WEG PETROBRAS VALE" YEARS=2022-2024
finllm cvm setor-normalizar
finllm cvm load-dfc-dva

# 3. Consulta RAG
make ask Q="Qual foi a receita líquida consolidada da WEG em 2023?"
finllm rag ask "Qual o P/L da Petrobras?" --use-tools

# 4. Consulta point-in-time (apenas documentos entregues até 2023-12-31)
finllm rag ask "Qual o resultado da Vale em 2022?" --data-entrega 2023-12-31

# 5. Indicadores fundamentalistas
finllm indicadores calc WEGE3

# 6. Indicadores técnicos
finllm tecnico sinal PETR4
finllm tecnico indicadores PETR4 --periodo 6m

# 7. Agentes de análise
finllm agentes analisar WEGE3

# 8. Backtest
finllm backtest run --ticker PETR4 --capital 100000 --comissao 0.001

# 9. Benchmark
make bench-build
make bench MAXMEM=16
make bench-report

# 10. Avaliação contínua (regressão CI)
finllm avaliacao salvar-referencia benchmark/results/latest/summary.csv referencia.json
finllm avaliacao regressao benchmark/results/novo/summary.csv --referencia-json referencia.json --limiar 0.05

# 11. Dashboard
finllm dashboard up --porta 8501
```

---

## Testes (carga, segurança, usabilidade, desempenho)

O projeto possui **89 testes passando** (4 skipped sem psycopg global), organizados em:

| Arquivo | O que cobre |
|---------|-------------|
| `test_cvm_transform.py` | Transformação CVM: versão mais recente, ÚLTIMO × PENÚLTIMO, escala MIL/UNIDADE, filtro por empresa |
| `test_chunking.py` | Cabeçalho repetido, Parte i/n, nenhuma linha perdida, limites de tamanho |
| `test_guardrails.py` | Parsing pt-BR, número ausente/presente, exceções de anos/inteiros, citações `[n]` |
| `test_entities.py` | Normalização, aliases, resolução e ambiguidade de empresas |
| `test_metrics.py` | Wilson, tolerâncias, pontuação de todas as tarefas do benchmark |
| `test_report.py` | Agregação e geração do relatório de benchmark |
| `test_runner_smoke.py` | Benchmark ponta a ponta com Ollama simulado |
| `test_carga.py` | **Carga**: transform_frame 10k linhas, chunking 2k linhas, auditoria sequencial (200) e concorrente (100 × 8 workers), métricas em escala, indicadores 500 cálculos, normalizar_setores 2000 empresas |
| `test_seguranca.py` | **Segurança**: injeção SQL via nomes de empresa, prompt injection, guardrails numéricos, extração de texto perigosa (ZIP/PDF vazio), parse de números malformados, contas SQL desconhecidas |
| `test_usabilidade.py` | **Usabilidade**: help CLI de todos os grupos, comandos inválidos, parâmetros obrigatórios, mensagens de erro, valores padrão |
| `test_desempenho.py` | **Desempenho**: tempo e memória (tracemalloc) de transform_frame, chunking, guardrails, numbers_in, score_rag, wilson, summarize, builtin_items, score_classif, score_tool, within |
| `test_ipe_secao.py` | Chunking por seção para documentos IPE/PDF |
| `test_integration.py` | Integração com mock de banco: auditoria, normalizar_setores, indicadores, SQL direto, tools reais |
| `test_tecnico.py` | Motor técnico: indicadores e geração de sinais |
| `test_agentes.py` | Agentes: execução com e sem dados, 3 pareceres, score composto |
| `test_backtest.py` | Backtest: Sharpe, drawdown máximo, execução nativa |
| `test_avaliacao.py` | Avaliação contínua: salvar/carregar referência, comparação com/sem regressão, relatório |
| `test_cache.py` | Cache: respostas e embeddings (get/set, singleton) |
| `test_ocr.py` | OCR: PDF vazio, extração sem PDF válido |
| `test_rerank_crossencoder.py` | Reranker: fallback forçado quando sentence-transformers indisponível |
| `test_dashboard_db.py` | Dashboard DB: estatísticas, listagens, criar alerta, indicadores sem banco |

Execução:
```bash
make test        # ou: pytest tests/ -q
```

---

## Roadmap e status

| Fase | Entrega | Status |
|------|---------|--------|
| 1 | Infra (compose), ingestão CVM, RAG híbrido, guardrail numérico, benchmark | ✅ Implementado |
| 2 | Auditoria persistida, carga de DFC/DVA, normalização por setor | ✅ Implementado |
| 3 | Motor fundamentalista determinístico exposto como tools | ✅ Implementado |
| 4 | Motor técnico (OHLCV, indicadores, suportes/resistências) + tools | ✅ Implementado |
| 5 | Agentes (fundamentalista, técnico, risco, sintetizador) + score composto | ✅ Implementado |
| 6 | Backtest point-in-time (vectorbt ou nativo) | ✅ Implementado |
| 7 | Dashboard (Streamlit), alertas, screener da B3 | ✅ Implementado |
| 8 | Avaliação contínua (regressão CI), OCR para PDFs, reranker cross-encoder | ✅ Implementado |

**Pendentes menores (melhorias candidatas):**
- Chunking por seção via Docling completo (atualmente heurística + fallback)
- Data de entrega point-in-time como filtro padrão nas consultas (já disponível via `--data-entrega`)
- Walk-forward avançado, paper trading com execução real

---

## Decisões de arquitetura (ADRs)

| ADR | Decisão |
|-----|---------|
| 0001 | Ollama local para chat, tool calling, saída estruturada e embeddings |
| 0002 | PostgreSQL + pgvector com busca híbrida (vetorial + FTS + RRF) |
| 0003 | Números determinísticos: vêm de dados/código; LLM apenas interpreta e cita |
| 0004 | httpx direto na API do Ollama (sem SDK oficial) |
| 0005 | Cartões textuais de demonstrações em vez de extração de tabelas de PDF |

---

## Limites e avisos

- O sistema é **apoio à análise**, não recomendação de investimento. No Brasil, análise de valores mobiliários é regulada (CVM, Resolução CVM 20).
- O LLM pode alucinar; o guardrail reduz o risco mas não elimina (valida presença, não correção absoluta do número).
- Resolução de empresa por nome é heurística; use `--empresa` para forçar.
- O benchmark mede leitura de demonstrações padronizadas; não cobre análise qualitativa (teleconferências, tese de investimento).
- Formatos de CSV da CVM podem mudar; valide na primeira execução com `finllm db stats` e `finllm rag search`.
- Não exponha portas 5432/11434 à internet; troque senhas padrão do Postgres.

---

## Contribuição e histórico

- Contribuição: [CONTRIBUTING.md](CONTRIBUTING.md)
- Histórico: [CHANGELOG.md](CHANGELOG.md)
- Documentação detalhada: [docs/](docs/)
