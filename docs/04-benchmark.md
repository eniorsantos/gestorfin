# 04 · Benchmark de modelos

Objetivo: escolher, **com dados e no seu hardware**, o modelo do Ollama para o RAG financeiro.

## Metodologia
Mesmos itens, mesmos parâmetros (`temperature=0`, `seed`, `num_ctx`, `num_predict=768`), `think` configurável por modelo, saída por JSON schema, 1 *warm-up* por modelo (mede o *cold start* à parte), unload ao final.

### Tarefas
| Tarefa | Origem | O que mede | Critério de acerto |
|---|---|---|---|
| `rag_fact` | gerada do **seu banco** | ler o valor certo entre trechos parecidos (mesma conta em outros anos, outra empresa) | valor dentro de 0,5% (ou 0,5 mil) |
| `rag_abstain` | gerada do banco | reconhecer que o período **não existe** no contexto | `nao_encontrado=true` |
| `rag_calc` | gerada do banco | ler 2 valores e calcular margem líquida (3.11 ÷ 3.01 × 100) | ±0,1 p.p. |
| `classif` | embutida (10 manchetes **sintéticas**) | sentimento em PT-BR com JSON schema | rótulo igual |
| `tools` | embutida (8 pedidos) | escolher a ferramenta e os argumentos corretos | nome + argumentos |

A "verdade" das tarefas RAG é a própria linha da CVM (não depende de LLM-juiz). O dataset registra `seed`, data e contagens em `*.meta.json`.

### Modos de contexto
- **`gold`** (padrão): contexto correto + 2–3 distratores. Isola a capacidade de **leitura/raciocínio** do modelo.
- **`retrieved`**: usa a recuperação real (exige índice; gere o dataset com `--only-indexed`). Reporta **`recall@k`**, separando falha de recuperação de falha de geração.

### Métricas
Acurácia por tarefa com **IC 95% de Wilson**; `alucinacao_abstain` (respondeu algo quando devia abster-se); `resp_errada_confiante` (número errado sem abster-se — o pior erro); `citacao_ok`; `json_valid`; velocidade (`gen_tok/s`, `prompt_tok/s`, latência p50/p95, `cold_load_s`); memória (`vram_gb`, `gpu_%` via `/api/ps`).
`score` = média ponderada (pesos em `bench/report.py::WEIGHTS`); serve para ordenar, **não** para decidir sozinho.

## Como rodar
```bash
make bench-build                                  # ou: finllm bench build --n-fact 60 --n-abstain 20 --n-calc 15
make bench MAXMEM=16                              # só modelos com min_mem_gb <= 16
finllm bench run --only qwen3:8b,llama3.1:8b --repeats 3
finllm bench run --context retrieved              # após: bench build --only-indexed
make bench-report
```
Saída em `benchmark/results/<timestamp>/`: `results.jsonl` (bruto, por chamada), `summary.csv`, `detail.csv`, `report.md`, `hardware.json`, `model_meta.json`, `run_config.json`.

Modelos candidatos: `benchmark/models.yaml` (nome, `think`, `min_mem_gb`, `options`). Baixe antes (`ollama pull`) ou use `--pull`.

## Como interpretar
1. Descarte modelos com `json_valid` < ~0,98 ou `gpu_%` < 100 (offload para CPU derruba a velocidade).
2. Entre os restantes, priorize **menor `resp_errada_confiante`** e **menor `alucinacao_abstain`** antes de acurácia bruta.
3. Compare **intervalos**, não pontos: com n = 40, uma diferença de 5 p.p. quase nunca é significativa. Aumente `--n-*` e `--repeats`.
4. Use velocidade para desempatar. Considere `prompt_tok/s` (RAG é dominado por *prefill*) tanto quanto `gen_tok/s`.
5. Revalide ao trocar quantização, versão do Ollama ou `num_ctx`.

## Limites do benchmark
- Mede leitura de **demonstrações padronizadas**; não mede análise qualitativa (teleconferências, tese, comparação setorial).
- Itens de `classif` e `tools` são poucos e sintéticos: servem como *sanity check*, não como ranking confiável. Estenda com seus dados rotulados.
- Bancos/seguradoras têm plano de contas distinto; as contas escolhidas existem, mas o significado econômico varia.
- Resultados dependem de hardware, versão do Ollama, quantização e `num_ctx`; temperatura 0 + seed dão reprodutibilidade **prática**, não bit a bit.
- Modelos com *thinking* ligado podem exceder `num_predict` e falhar o JSON — aumente `options.num_predict` no YAML para esses casos.

## Estendendo
- Nova tarefa: crie itens em `bench/tasks.py` (ou no dataset), uma função `score_*` em `metrics.py` e um ramo em `runner.py`.
- Novos pesos/critérios: `report.py`.
- Compare configurações do **mesmo** modelo (ex.: `think` on/off, `num_ctx`) duplicando a entrada no YAML com `options` diferentes e nomes distintos via `--only`.
