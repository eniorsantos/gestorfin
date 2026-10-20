# Changelog
## 0.5.1 (testes de qualidade: carga, segurança, usabilidade, desempenho)
- `tests/test_carga.py`: carga de dados, concorrência (auditoria sequencial e concorrente), volume de transform_frame/chunking/métricas/indicadores/normalizar_setores
- `tests/test_seguranca.py`: injeção SQL, prompt injection, guardrails numéricos, extração de texto perigosa (ZIP/PDF vazio), parse de números malformados, contas SQL desconhecidas
- `tests/test_usabilidade.py`: help CLI (todos os grupos e comandos), comandos inválidos, parâmetros obrigatórios, mensagens de erro, valores padrão (--use-tools, --data-entrega, --limiar, --porta)
- `tests/test_desempenho.py`: tempo e memória de transform_frame, chunk_lines, chunk_text, guardrails, numbers_in, score_rag, wilson, summarize, builtin_items, score_classif, score_tool, within
- Total: 89 testes passando, 4 skipped (sem psycopg global)

## 0.5.0 (melhorias candidatas implementadas)
- Chunking por seção para documentos IPE/PDF (`src/finllm/cvm/ipe.py: _chunk_por_secao`), com detecção heurística de títulos e fallback quando Docling não disponível
- Data de entrega (point-in-time) nos metadados dos chunks e filtro na busca híbrida (`src/finllm/rag/retrieve.py: data_entrega_max`), evitando look-ahead bias; comando `finllm rag ask --data-entrega YYYY-MM-DD`
- `documentos_ipe.dt_entrega` agora é armazenado no `metadata` de cada chunk IPE

## 0.4.0 (roadmap Fase 7 implementada)
- Dashboard Streamlit (Fase 7): `src/finllm/dashboard/` com páginas de visão geral, screener B3, indicadores fundamentalistas, indicadores técnicos, agentes, alertas e auditoria de consultas
- Comando `finllm dashboard up [--porta N]` para subir o dashboard em `http://localhost:N`
- Tabela `alertas` no schema com CRUD via `db.py` do dashboard
- Screener da B3 com filtro por setor e indicadores (P/L, ROE, ROIC, dívida/EBITDA, F-Score)
- 55 testes unitários e de integração (mock de banco, sem exigir Postgres/Ollama/Streamlit real)

## 0.3.0 (roadmap Fase 2, 3, 4, 5, 6, 8 implementadas)
- Fase 2: Auditoria persistida (`consultas`) + normalização por setor (`setores`) + carga DFC/DVA (`cvm load-dfc-dva`)
- Fase 3: Motor fundamentalista determinístico (P/L, ROE, ROIC, dívida líquida/EBITDA, F-Score) + tools reais integradas ao `rag ask --use-tools` (`get_indicadores`, `buscar_documentos`, `get_macro`)
- Fase 4: Motor técnico (OHLCV via yfinance, SMA/EMA/RSI/MACD/Bollinger, suportes/resistências) + tools `get_cotacoes`, `get_indicadores_tecnicos`, `get_sinal_tecnico` + comandos `tecnico sinal` / `tecnico indicadores`
- Fase 5: Agentes (fundamentalista, técnico, risco 'advogado do diabo', sintetizador) com score composto + comando `agentes analisar <ticker>`
- Fase 6: Backtest point-in-time (vectorbt ou nativo) com Sharpe, drawdown, curva de patrimônio + comando `backtest run`
- Fase 8: Avaliação contínua/regressão CI (`avaliacao regressao` / `salvar-referencia`), OCR para PDFs escaneados (`ocr.py`), reranker cross-encoder (`rerank_crossencoder.py`)
- Melhorias RAG: consulta SQL direta para perguntas numéricas (`sql_direct.py`), reranker leve (`rerank.py`), cache de respostas/embeddings (`cache.py`)
- Novas tabelas: `cotacoes`, `indicadores_calc`, `sinais_tecnicos`, `backtest_resultados`, `alertas`
- 29 testes unitários e de integração (mock de banco)

## 0.2.0 (roadmap Fase 2 e 3 implementadas)
- Auditoria persistida: tabela `consultas` (pergunta, modelo, filtros, chunks, resposta, validação) + comando `finllm auditoria list` (`src/finllm/auditoria.py`)
- Normalização por setor: tabela `setores`, mapeamento CVM → categoria (bancos, seguros, utilities, outros) + comando `finllm cvm setor-normalizar` (`src/finllm/cvm/load.py`)
- Motor fundamentalista determinístico (Fase 3): P/L, ROE, ROIC, dívida líquida/EBITDA, F-Score de Piotroski (`src/finllm/fundamentalista.py`) + comando `finllm indicadores calc <ticker>`
- Tools reais para function calling (Fase 3): `get_indicadores`, `buscar_documentos`, `get_cotacoes`, `get_macro` em `src/finllm/rag/tools.py`, integradas no fluxo `rag/answer.py` com `--use-tools`
- Consulta SQL direta para perguntas numéricas (`src/finllm/rag/sql_direct.py`)
- Reranker local leve sobre top-N da busca híbrida (`src/finllm/rag/rerank.py`)
- 29 testes unitários e de integração (mock de banco, sem exigir Postgres real)
- Importação preguiçosa de `psycopg` em módulos opcionais para permitir coleta de testes sem banco

## 0.1.0
- Infra Docker (Ollama, Postgres+pgvector, app; overrides NVIDIA/AMD; modo Mac).
- Ingestão CVM: cadastro, DFP, ITR, IPE.
- RAG híbrido (pgvector + FTS) com resposta JSON, citações e guardrail numérico.
- Benchmark: rag_fact/abstain/calc, classif, tools; velocidade, VRAM, IC 95%.
- Documentação e ADRs.
