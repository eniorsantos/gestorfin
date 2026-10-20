# 08 · Roadmap

| Fase | Entrega | Status |
|---|---|---|
| 1 | Infra (compose), ingestão CVM, RAG híbrido, guardrail numérico, benchmark | ✅ esta entrega (validar em ambiente real) |
| 2 | Auditoria persistida (tabela `consultas`), carga de DFC/DVA, normalização por setor (bancos, seguros, utilities) | ✅ implementada (auditoria + setor + `cvm load-dfc-dva`) |
| 3 | Motor fundamentalista determinístico (P/L, ROE, ROIC, dívida líq./EBITDA, F-Score…) exposto como **tools** | ✅ implementado (indicadores + tools reais integradas ao `rag ask --use-tools`) |
| 4 | Motor técnico (OHLCV via brapi/yfinance, indicadores, suportes/resistências) + tools | ✅ implementado (`tecnico.py`, tools `get_cotacoes`/`get_indicadores_tecnicos`/`get_sinal_tecnico`, comandos `tecnico sinal` / `tecnico indicadores`) |
| 5 | Agentes (fundamentalista, técnico, risco como "advogado do diabo", sintetizador) + score composto | ✅ implementado (`agentes.py`, comando `agentes analisar <ticker>`) |
| 6 | Backtest point-in-time (vectorbt), walk-forward, paper trading | ✅ implementado nativo (`backtest.py`, comando `backtest run`); vectorbt opcional |
| 7 | Dashboard (Streamlit/Next.js), alertas, screener da B3 | ✅ implementado (`src/finllm/dashboard/`, comando `finllm dashboard up`) |
| 8 | Avaliação contínua do LLM (regressão do benchmark em CI), OCR para PDFs escaneados, reranker | ✅ implementado (`avaliacao.py`, `ocr.py`, `rerank_crossencoder.py`, comandos `avaliacao regressao` / `salvar-referencia`, `rag rerank-test`) |

## Melhorias de RAG (status)
- *Reranker* local (cross-encoder) sobre o top-30 antes do top-k — ✅ implementado (`rerank_crossencoder.py`, `rag rerank-test`)
- Consulta estruturada direta (SQL) para perguntas puramente numéricas — ✅ implementado (`rag/sql_direct.py`)
- Chunking por seção para PDFs (títulos, tabelas via Docling) — ✅ implementado (`ipe/_chunk_por_secao` com fallback heurístico)
- Data de entrega (point-in-time) nos metadados — ✅ implementado (`retrieve.data_entrega_max`, `ipe` armazena `dt_entrega` no metadata do chunk)
- Cache de respostas e de embeddings de consulta — ✅ implementado (`rag/cache.py`, `rag cache-limpar`)
- OCR para PDFs escaneados — ✅ implementado (`ocr.py`)
