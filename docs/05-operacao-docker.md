# 05 · Operação e Docker

## Serviços
| Serviço | Imagem | Função |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | dados + vetores; init cria extensões (`db/init/`) |
| `ollama` | `ollama/ollama` | servidor de modelos (`:11434`) |
| `model-puller` | idem | baixa `OLLAMA_MODELS` e encerra |
| `app` | build local | CLI `finllm` (código montado em `/app`) |
| `adminer` | `adminer` | UI do banco (perfil `tools`: `--profile tools`) |

Volumes: `pgdata` (banco), `ollama` (modelos). `docker compose down` **preserva** dados; `down -v` apaga tudo.

## Por plataforma
| Ambiente | Comando | Observação |
|---|---|---|
| CPU | `make up` | funciona, lento; use modelos ≤ 8B |
| NVIDIA | `make up-nvidia` | requer NVIDIA Container Toolkit; teste: `docker run --rm --gpus all ubuntu nvidia-smi` |
| AMD (Linux) | `make up-amd` | imagem `ollama/ollama:rocm`, `/dev/kfd` e `/dev/dri` |
| **Mac (Apple Silicon)** | instale o Ollama nativo, `ollama serve`, depois `make up-mac` | Docker no Mac **não acessa a GPU**; o app aponta para `host.docker.internal:11434` |
| Windows + WSL2 | como NVIDIA, com Docker Desktop (WSL2) e driver NVIDIA no Windows | |

## Primeiro uso
```bash
cp .env.example .env            # ajuste OLLAMA_MODELS, LLM_MODEL, senhas
make up-nvidia
docker compose logs -f model-puller
make init
make pipeline EMPRESAS="WEG ITAU UNIBANCO" YEARS=2022-2024
make ask Q="Qual o patrimônio líquido consolidado do Itaú Unibanco em 2023?"
```

## Variáveis (`.env`)
| Variável | Padrão | Nota |
|---|---|---|
| `OLLAMA_MODELS` | `bge-m3 qwen3:8b` | modelos baixados no boot (espaço-separados) |
| `LLM_MODEL` / `EMBED_MODEL` / `EMBED_DIM` | `qwen3:8b` / `bge-m3` / `1024` | trocar embedding ⇒ reindexar |
| `LLM_NUM_CTX` | `8192` | custo de VRAM cresce com o contexto |
| `LLM_THINK` | `false` | vazio = padrão do modelo |
| `OLLAMA_NUM_PARALLEL` / `OLLAMA_MAX_LOADED_MODELS` | `1` / `1` | para varrer muitos ativos, suba com cuidado (VRAM) |
| `OLLAMA_KEEP_ALIVE` | `30m` | tempo com o modelo na memória |

## Dimensionamento (Q4, regra prática)
| VRAM / memória | Modelos viáveis |
|---|---|
| 8 GB | 7–8B |
| 16 GB | ~14B |
| 24 GB | 27–32B |
| 48 GB+ | 70B |
Rode `finllm bench hardware` e o benchmark: `gpu_%` < 100 indica que o modelo/contexto não cabe.

## Backup e manutenção
```bash
docker compose exec postgres pg_dump -U finllm finllm | gzip > backup.sql.gz
docker compose exec postgres psql -U finllm -c "VACUUM ANALYZE chunks"
```
Dados brutos da CVM ficam em `data/raw/` (cache de download; `--force` rebaixa).

## Troubleshooting
| Sintoma | Causa provável | Ação |
|---|---|---|
| `connection refused` ao Ollama no `app` | serviço subindo / Mac sem Ollama nativo | `docker compose ps`; no Mac, `ollama serve` e `make up-mac` |
| Modelo não encontrado (404) | não baixado | `docker compose exec ollama ollama pull <modelo>` |
| `Tabela chunks usa vector(N)…` | trocou modelo de embedding | `DROP TABLE chunks;` → `make init` → reindexar |
| Respostas ignoram parte do contexto | `num_ctx` curto (truncamento silencioso) | suba `LLM_NUM_CTX`, reduza `RAG_TOP_K` |
| Muito lento | offload parcial para CPU | modelo menor, menor `num_ctx`, veja `gpu_%` no relatório |
| JSON inválido em modelo "thinking" | `num_predict` curto | `options: {num_predict: 2048}` no YAML |
| `404` no download CVM | ano ainda não publicado / URL mudou | confira em dados.cvm.gov.br; ajuste `CVM_BASE_URL` |
| `KeyError`/colunas na carga | layout do CSV mudou | inspecione o CSV e ajuste `cvm/load.py` |
| Empresa "ambígua" | nome genérico | use nome mais específico ou o alias (ex.: "PETROBRAS") |
| `rag search` vazio | índice vazio / filtro excessivo | `finllm db stats`; reindexe; teste sem ano/empresa na pergunta |
