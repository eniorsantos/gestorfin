# 07 · Testes e qualidade

`make test` (ou `pytest -q` no venv). **Não** exigem banco, Ollama nem rede.

| Arquivo | Cobre |
|---|---|
| `test_cvm_transform.py` | versão mais recente, `ÚLTIMO` × `PENÚLTIMO`, escala MIL/UNIDADE, filtro por empresa, colunas opcionais ausentes |
| `test_chunking.py` | cabeçalho repetido, `Parte i/n`, nenhuma linha perdida, limites de tamanho |
| `test_guardrails.py` | parsing pt-BR, número ausente/presente, exceções de anos/inteiros, citações `[n]` |
| `test_entities.py` | normalização, aliases (`... - PETROBRAS`), resolução e ambiguidade |
| `test_metrics.py` | Wilson, tolerâncias, pontuação de fact/abstain/calc/classif/tools |
| `test_report.py` | agregação e geração do relatório |
| `test_runner_smoke.py` | benchmark ponta a ponta com Ollama simulado |
| `test_carga.py` | carga de dados, concorrência (auditoria), volume de transformação/chunking/métricas |
| `test_seguranca.py` | injeção SQL, prompt injection, guardrails numéricos, extração de texto perigosa, parse de números |
| `test_usabilidade.py` | help CLI, comandos inválidos, parâmetros obrigatórios, mensagens de erro, valores padrão |
| `test_desempenho.py` | tempo e memória de transform_frame, chunking, guardrails, métricas, relatório, builtin_items |

## Lacunas conhecidas (a cobrir quando houver ambiente)
1. Testes de integração com Postgres/pgvector (ex.: `pytest-postgresql` ou `testcontainers`): `init_db`, `load_zip` (COPY), `iter_card_chunks`, `hybrid_search`.
2. Teste de contrato com um Ollama real (modelo pequeno) para `chat` com schema/tools e `embed`.
3. Teste do download com *fixtures* de zips reais da CVM (amostras recortadas).
4. Teste de carga real com Postgres + Ollama simultâneos (medir latência p95 e throughput de consultas RAG).

## Qualidade de código
`ruff check src tests` (regras E, F, W, B). Python ≥ 3.11, tipos nas fronteiras públicas. Mudanças em prompt (`answer.SYSTEM`) devem ser acompanhadas de nova rodada do benchmark.

## Checklist de PR
- [ ] `pytest` e `ruff` verdes
- [ ] Mudou prompt/chunking/recuperação? Rodou `bench run` (gold e retrieved) e anexou o `summary.csv`
- [ ] Atualizou docs e `CHANGELOG.md`
