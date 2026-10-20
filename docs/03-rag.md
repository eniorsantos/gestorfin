# 03 · Pipeline RAG

## 1. Cartões de demonstrações (`rag/cards.py`)
Em vez de embutir PDFs de ITR/DFP, o sistema usa os **dados estruturados** da CVM e renderiza um *cartão* por (empresa, documento, demonstração, consolidação, período):

```
Empresa: WEG S.A. (CD_CVM 5410) | Documento: DFP | Consolidado | Demonstração do Resultado | Período: 01/01/2023 a 31/12/2023 | Valores em R$ mil
3.01 | Receita de Venda de Bens e/ou Serviços | 32.xxx.xxx
3.02 | Custo dos Bens e/ou Serviços Vendidos | -2x.xxx.xxx
...
```
(valores ilustrativos). Cartões longos são divididos em chunks de até `CHUNK_MAX_CHARS`, **repetindo o cabeçalho** e marcando `Parte i/n` — cada chunk é autossuficiente para a busca. Valores sempre em R$ mil com ponto de milhar (padrão pt-BR) e sem conversão de unidade pelo LLM.

## 2. Documentos narrativos (`cvm/ipe.py`, `rag/text.py`)
`ipe-sync` registra documentos das categorias configuradas; `index-ipe` baixa, extrai texto (PDF via PyMuPDF; HTML via BeautifulSoup), divide em parágrafos (`chunk_text`, com overlap só para parágrafos gigantes) e prefixa cada chunk com empresa/categoria/assunto/data.

## 3. Embeddings (`rag/index.py`)
- Modelo padrão: **`bge-m3`** (multilíngue, 1024 dims, bom em português). `nomic-embed-text` é mais leve; `qwen3-embedding` é alternativa. Mudou o modelo ⇒ mudou `EMBED_DIM` ⇒ recriar `chunks` e reindexar (o `db init` detecta a divergência).
- Idempotência: `content_hash` (SHA-256) único; reindexar só embeda o que é novo.
- Lotes de 16 via `/api/embed`.

## 4. Recuperação (`rag/retrieve.py`)
Busca **híbrida** (ADR 0002):
1. vetorial (`embedding <=> query`, cosseno, HNSW);
2. texto completo (`tsvector` português, consulta OR entre termos);
3. fusão **RRF** (`1/(60+rank)`), top-k (`RAG_TOP_K`, padrão 6).

**Filtros automáticos:** empresa (alias/nome em `entities.py`, ambíguo ⇒ nenhum) e anos citados na pergunta (`EXTRACT(year FROM ref_date)`). Se o filtro zerar os resultados, refaz sem filtro (e informa em `filters`).

Por que híbrida: embeddings capturam semântica ("receita", "faturamento"), mas são fracos em códigos/números/nomes próprios; o FTS cobre isso.

## 5. Geração (`rag/answer.py`)
- Prompt de sistema com 7 regras (só contexto, não converter unidade, conferir empresa/período/consolidação, abster-se, citar).
- Saída forçada por **JSON schema** (`Resposta`: `nao_encontrado`, `resposta`, `valor`, `unidade`, `citacoes`).
- `temperature=0`, `seed` fixo, `num_ctx` explícito (o padrão do Ollama é pequeno e trunca em silêncio), `think=false` por padrão.

## 6. Guardrail numérico (`rag/guardrails.py`)
Todo número da `resposta` precisa existir (em valor absoluto) em algum trecho de contexto. Ignora anos (1900–2100) e inteiros ≤ 31. Falhou ⇒ **1 retry** informando os números não suportados; persistindo, a CLI exibe ⚠.
Limitação deliberada: números **derivados** (somas, razões) também são sinalizados — cálculos devem ser feitos em código (tools), não pelo LLM.

## 7. Parâmetros de ajuste
| Parâmetro | Efeito | Quando mexer |
|---|---|---|
| `RAG_TOP_K` | mais contexto × mais ruído/latência | perguntas comparativas entre períodos: 8–12 |
| `CHUNK_MAX_CHARS` | granularidade | cartões muito grandes ou modelo com contexto curto |
| `LLM_NUM_CTX` | janela real | ≥ 8192; suba se `k` e chunks aumentarem (custa VRAM) |
| `--cons con,ind` | quais consolidações indexar | reduza para cortar volume (só `con`) |
| `--statements` | demonstrações indexadas | incluir DFC/DVA se precisar |

## 8. Function calling (tools reais)

O LLM pode chamar tools reais para obter dados além do RAG (roadmap Fase 3):

| Tool | Descrição |
|------|-----------|
| `get_indicadores` | P/L, ROE, ROIC, dívida líquida/EBITDA de um ticker (dados CVM) |
| `buscar_documentos` | Busca semântica em fatos relevantes/releases da companhia |
| `get_cotacoes` | Série histórica OHLCV (placeholder Fase 4) |
| `get_macro` | Série macro (Selic, IPCA, câmbio) (placeholder Fase 4/8) |

Ative com `finllm rag ask "..." --use-tools` (padrão: ligado). Quando o LLM solicitar uma tool, ela é executada contra o banco e o resultado é incorporado na resposta final.

## 9. Consulta SQL direta (melhoria RAG)

Perguntas puramente numéricas (ex.: "qual a receita líquida da WEG em 2023?") podem ser respondidas diretamente via SQL contra a tabela `demonstracoes`, sem passar pelo LLM para leitura de valor. O módulo `rag/sql_direct.py` mapeia sinônimos de conta para códigos (3.01 receita, 3.11 lucro, 2.03 patrimônio líquido, etc.) e retorna o valor exato.

## 10. Reranker local (melhoria RAG)

`rag/rerank.py` reordena o top-N da busca híbrida por similaridade de tokens entre consulta e chunk, antes do envio ao LLM. Útil quando `RAG_TOP_K` é grande (ex.: 30).

## 11. Chunking por seção para documentos IPE/PDF (melhoria RAG)

`cvm/ipe.py: _chunk_por_secao` divide documentos narrativos respeitando seções/títulos detectados (heurística de maiúsculas/números, com suporte a Docling quando disponível). Cada chunk é prefixado com o título da seção, preservando a estrutura do documento original.

## 12. Point-in-time por data de entrega (melhoria RAG)

A busca híbrida (`rag/retrieve.py`) aceita `data_entrega_max`: só retorna chunks cujo documento IPE foi entregue na CVM até aquela data (`metadata.dt_entrega`). Evita look-ahead bias em análises históricas.

Comando: `finllm rag ask "..." --data-entrega 2023-12-31`.

## 8. Estimativa de volume (ordem de grandeza)
Cada cartão ≈ 1–3 chunks. Por empresa/ano: 3 demonstrações × 2 consolidações × (1 DFP + 4 períodos ITR, DRE com 2 variantes) ⇒ da ordem de **dezenas a ~100 chunks/empresa/ano**. Para uma watchlist de 10–30 empresas × 3 anos, milhares de chunks — viável em minutos a poucas horas dependendo de GPU. Indexar toda a B3 é possível, mas planeje o tempo (use `--empresa` e `--cons con` para começar).

## 9. Como depurar
```bash
finllm rag search "receita líquida WEG 2023" -k 6      # só recuperação (sem LLM)
finllm rag ask "..." --verbose                          # mostra filtros, tentativas, tempos
finllm db stats                                         # confere volumes
```
Sintomas comuns: resposta "não encontrado" ⇒ rode `rag search` e veja se o cartão certo apareceu (problema de recuperação) antes de culpar o modelo — o modo `--context retrieved` do benchmark mede isso (`recall@k`).
