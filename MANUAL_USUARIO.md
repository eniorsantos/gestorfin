# Manual Técnico — Usuário Final

**finllm — Análise financeira com LLM local (Ollama)**

Sistema de apoio à análise fundamentalista e técnica sobre dados abertos da CVM, com LLM local, RAG híbrido, benchmark de modelos, agentes de análise, backtest, dashboard e auditoria.

> ⚠️ **Aviso:** esta ferramenta é apoio à análise. **Não é recomendação de investimento.** No Brasil, a atividade de análise de valores mobiliários é regulada (CVM, Resolução CVM 20).

---

## 1. Visão rápida

O `finllm` permite fazer perguntas sobre empresas listadas na B3 usando dados oficiais da CVM (Demonstrações Financeiras Padronizadas — DFP, Informações Trimestrais — ITR e documentos narrativos — IPE), com:

- **Respostas fundamentadas** em dados estruturados (não no "achismo" do LLM)
- **Citações de fonte** (quais trechos foram usados)
- **Validação numérica automática** (todo número citado é conferido contra o contexto)
- **Escolha de modelo por benchmark** no seu próprio hardware
- **Dashboard web** para navegação visual dos dados e análises

---

## 2. Pré-requisitos

| Item | Requisito |
|------|-----------|
| Docker | Docker Compose (recomendado) |
| GPU | NVIDIA (Container Toolkit), AMD (ROCm) ou Apple Silicon (Ollama nativo) — opcional, funciona em CPU |
| Memória | 8 GB RAM mínimo; 16 GB+ recomendado para modelos maiores |
| Disco | 20 GB+ livres (para modelos Ollama e dados da CVM) |
| Python | 3.11+ (se rodar sem Docker) |

---

## 3. Instalação e primeira execução

### 3.1 Via Docker Compose (recomendado)

```bash
# 1. Baixe/clonou o repositório
cd finllm

# 2. Crie o arquivo de ambiente a partir do exemplo
cp .env.example .env

# 3. Ajuste o .env se necessário (modelos, senhas, porta)
#    OLLAMA_MODELS=bge-m3 qwen3:8b   (modelos baixados automaticamente)

# 4. Suba o ambiente (escolha uma opção abaixo)
make up           # CPU apenas (lento, modelos <= 8B)
make up-nvidia    # GPU NVIDIA (requer NVIDIA Container Toolkit)
make up-amd       # GPU AMD (ROCm, Linux)
make up-mac       # Mac: Ollama nativo + Postgres/app via Docker

# 5. Acompanhe o download dos modelos
docker compose logs -f model-puller
```

### 3.2 Inicialização do banco e ingestão de dados

```bash
# Cria as tabelas no Postgres
make init

# Baixa e carrega cadastro, DFP e ITR para 2022-2024
make pipeline EMPRESAS="WEG PETROBRAS VALE ITAU UNIBANCO" YEARS=2022-2024

# (Opcional) Carrega DFC e DVA (fluxo de caixa e valor adicionado)
finllm cvm load-dfc-dva --years 2022-2024 --empresa WEG PETROBRAS

# (Opcional) Normaliza setores para categorias padrão (bancos, seguros, utilities)
finllm cvm setor-normalizar
```

### 3.3 Verificação rápida

```bash
# Veja o que foi carregado
finllm db stats

# Teste uma consulta
make ask Q="Qual foi a receita líquida consolidada da WEG em 2023?"
```

---

## 4. Comandos principais

### 4.1 Banco de dados (`db`)

| Comando | Descrição |
|---------|-----------|
| `finllm db init` | Cria tabelas e extensões (vector, pg_trgm) |
| `finllm db stats` | Mostra contagens por tabela (empresas, demonstracoes, chunks, etc.) |

### 4.2 Dados da CVM (`cvm`)

| Comando | Descrição |
|---------|-----------|
| `finllm cvm download` | Baixa cadastro, DFP e ITR para `data/raw/` |
| `finllm cvm load` | Carrega DFP/ITR no banco (idempotente) |
| `finllm cvm ipe-categories` | Lista categorias de documentos IPE disponíveis |
| `finllm cvm ipe-sync` | Registra documentos IPE para indexação |
| `finllm cvm setor-normalizar` | Normaliza setores da CVM em categorias padrão |
| `finllm cvm load-dfc-dva` | Carrega DFC (fluxo de caixa) e DVA (valor adicionado) |

### 4.3 Consultas RAG (`rag`)

| Comando | Descrição |
|---------|-----------|
| `finllm rag index-statements` | Gera cartões textuais e indexa demonstrações |
| `finllm rag index-ipe` | Indexa documentos narrativos (fatos relevantes, comunicados) |
| `finllm rag search "texto"` | Apenas busca (sem LLM) — útil para depurar |
| `finllm rag ask "pergunta"` | Resposta com citações, validação numérica e opcionalmente tools |

**Exemplos de `rag ask`:**
```bash
# Consulta simples
finllm rag ask "Qual foi a receita líquida da WEG em 2023?"

# Com uso de tools (indicadores, busca de documentos, etc.)
finllm rag ask "Qual o P/L da Petrobras?" --use-tools

# Point-in-time: só documentos entregues até uma data
finllm rag ask "Qual o resultado da Vale em 2022?" --data-entrega 2023-12-31

# Sem tools (apenas RAG)
finllm rag ask "Qual o patrimônio líquido do Itaú em 2023?" --use-tools=false

# Verboso (mostra filtros, tentativas, tempo)
make ask Q="..."   # usa --verbose por padrão
```

### 4.4 Indicadores fundamentalistas

```bash
# Última DFP consolidada disponível
finllm indicadores calc WEGE3

# Data específica
finllm indicadores calc PETR4 --data 2023-12-31
```

Indicadores calculados: P/L, ROE, ROIC, dívida líquida/EBITDA, F-Score de Piotroski (0-9).

### 4.5 Indicadores técnicos (motor técnico)

```bash
# Sinal agregado (compra / venda / neutro)
finllm tecnico sinal PETR4 --periodo 6m

# Indicadores completos (SMA, EMA, RSI, MACD, Bollinger, suporte/resistência)
finllm tecnico indicadores WEGE3 --periodo 1a
```

Períodos disponíveis: `1m`, `6m`, `1a`, `5a`.

### 4.6 Agentes de análise

Executa quatro agentes (fundamentalista, técnico, risco/"advogado do diabo", sintetizador) e consolida em um score composto.

```bash
finllm agentes analisar WEGE3
```

Saída inclui: sinal final, confiança, score composto, síntese, riscos principais e parecer individual de cada agente.

### 4.7 Backtest point-in-time

Simula uma estratégia baseada em sinais dos agentes sobre preços históricos.

```bash
finllm backtest run --ticker PETR4 --capital 100000 --comissao 0.001
```

Métricas de saída: retorno total, Sharpe, drawdown máximo, número de operações, curva de patrimônio.

### 4.8 Benchmark de modelos

Compara modelos Ollama no seu hardware e ajuda a escolher o melhor.

```bash
# Gera dataset de avaliação a partir do seu banco
make bench-build

# Rode o benchmark (somente modelos que cabem em 16 GB)
make bench MAXMEM=16

# Gere o relatório
make bench-report

# Escolha modelos específicos
finllm bench run --only qwen3:8b,llama3.1:8b --repeats 3
```

O relatório fica em `benchmark/results/<timestamp>/report.md` e inclui acurácia, IC 95%, velocidade, VRAM, `gpu_%` e `resp_errada_confiante`.

### 4.9 Avaliação contínua (regressão CI)

Compara um novo resultado de benchmark com uma referência aprovada.

```bash
# Salve o resultado atual como referência
finllm avaliacao salvar-referencia benchmark/results/latest/summary.csv referencia.json

# Compare um novo resultado contra a referência
finllm avaliacao regressao benchmark/results/novo/summary.csv --referencia-json referencia.json --limiar 0.05
```

Se alguma tarefa cair mais de 5 p.p. (limiar padrão), o comando retorna erro.

### 4.10 Auditoria

Lista as consultas registradas automaticamente a cada `rag ask`.

```bash
finllm auditoria list --limit 20
```

Cada registro inclui: pergunta, modelo, filtros aplicados, IDs dos chunks usados, resposta e resultado da validação numérica.

### 4.11 Dashboard (Streamlit)

Interface web para navegação visual.

```bash
finllm dashboard up --porta 8501
```

Acesse `http://localhost:8501`. Páginas disponíveis:

| Página | O que faz |
|--------|-----------|
| Visão geral | Métricas do ambiente e últimas consultas auditadas |
| Screener B3 | Lista empresas por setor com indicadores (P/L, ROE, ROIC, dívida/EBITDA, F-Score) |
| Indicadores | Cálculo fundamentalista de um ticker |
| Técnico | Indicadores técnicos e sinais de compra/venda |
| Agentes | Execução dos 4 agentes com score composto |
| Alertas | CRUD de alertas de preço/indicador |
| Auditoria | Histórico de consultas registradas |

---

## 5. Fluxos de uso recomendados

### 5.1 Análise de uma empresa (fundamentalista)

```bash
# 1. Carregue os dados
make pipeline EMPRESAS="WEG" YEARS=2022-2024

# 2. Pergunte sobre demonstrações
finllm rag ask "Qual foi a receita líquida consolidada da WEG em 2023?"

# 3. Veja os indicadores calculados
finllm indicadores calc WEGE3

# 4. Execute os agentes para uma visão consolidada
finllm agentes analisar WEGE3
```

### 5.2 Comparação entre empresas

```bash
make pipeline EMPRESAS="WEG PETROBRAS VALE ITAU UNIBANCO" YEARS=2022-2024

# Abra o dashboard no screener
finllm dashboard up
# → Selecione "Screener B3" e filtre por setor
```

### 5.3 Escolha do melhor modelo para seu hardware

```bash
make bench-build
make bench MAXMEM=16
make bench-report
# → Leia benchmark/results/<data>/report.md e escolha o modelo com melhor score
#   e menor "resp_errada_confiante" e "alucinacao_abstain"
```

### 5.4 Análise point-in-time (sem look-ahead bias)

```bash
# Só considere documentos que já haviam sido divulgados até 31/12/2022
finllm rag ask "Qual o resultado da Vale em 2022?" --data-entrega 2023-12-31
```

---

## 6. Variáveis de ambiente (`.env`)

Copie de `.env.example` e ajuste conforme necessário:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `POSTGRES_USER` | `finllm` | Usuário do Postgres |
| `POSTGRES_PASSWORD` | `finllm` | Senha do Postgres |
| `POSTGRES_DB` | `finllm` | Nome do banco |
| `POSTGRES_PORT` | `5432` | Porta do Postgres |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL do Ollama (use `host.docker.internal:11434` no Mac) |
| `OLLAMA_MODELS` | `bge-m3 qwen3:8b` | Modelos baixados no boot (separados por espaço) |
| `LLM_MODEL` | `qwen3:8b` | Modelo de chat padrão |
| `EMBED_MODEL` | `bge-m3` | Modelo de embeddings |
| `EMBED_DIM` | `1024` | Dimensão dos vetores (deve bater com o modelo de embedding) |
| `LLM_NUM_CTX` | `8192` | Janela de contexto do modelo |
| `LLM_TEMPERATURE` | `0.0` | Temperatura (sempre 0 para reprodutibilidade) |
| `LLM_SEED` | `42` | Seed fixo |
| `LLM_THINK` | `false` | Desliga "thinking" (recomendado para JSON schema) |
| `RAG_TOP_K` | `6` | Quantidade de trechos recuperados por pergunta |
| `CHUNK_MAX_CHARS` | `2500` | Tamanho máximo de cada chunk de texto |
| `IPE_CATEGORIES` | `Fato Relevante,Comunicado ao Mercado` | Categorias IPE a indexar |

> Após trocar `EMBED_MODEL` ou `EMBED_DIM`, é necessário recriar a tabela `chunks` e reindexar: `DROP TABLE chunks; make init; make rag index-statements ...`

---

## 7. Interpretação das respostas

Quando você roda `finllm rag ask`, a saída inclui:

| Campo | Significado |
|-------|-------------|
| **Resposta** | Texto curto em português, com citações `[n]` aos trechos usados |
| **Valor** | Número único extraído, se aplicável (em R$ mil, a menos que indicado) |
| **Unidade** | Ex.: `R$ mil`, `%` |
| **Não encontrado** | Se o modelo indicou que a informação não está no contexto |
| **Validação numérica** | ✅ OK se todos os números existem no contexto; ⚠ se houver números não suportados |
| **Fontes** | Lista dos trechos recuperados, com score e origem (vetorial/texto) |
| **Tool usada** | Se function calling foi acionado (ex.: `get_indicadores`) |

**Regras de ouro do sistema:**
1. Números vêm do banco/código, nunca do LLM.
2. Se o dado não existe no contexto, o modelo deve responder `nao_encontrado=true`.
3. Toda resposta cita os trechos usados (`[n]`).
4. O sistema não é recomendação de investimento.

---

## 7. Solução de problemas comuns

| Sintoma | Causa provável | Ação |
|---------|---------------|------|
| `connection refused` ao Ollama | Serviço ainda subindo ou Mac sem Ollama nativo | `docker compose ps`; no Mac, rode `ollama serve` e `make up-mac` |
| Modelo não encontrado (404) | Modelo não baixado | `docker compose exec ollama ollama pull <modelo>` |
| Tabela chunks usa vector(N) diferente | Trocou o modelo de embeddings | `DROP TABLE chunks; make init; reindexe` |
| Resposta ignora parte do contexto | `num_ctx` muito curto | Aumente `LLM_NUM_CTX` ou reduza `RAG_TOP_K` |
| Muito lento | Offload parcial para CPU | Use modelo menor, menor `num_ctx`, veja `gpu_%` no relatório do benchmark |
| JSON inválido em modelo "thinking" | `num_predict` curto | Aumente `options.num_predict` no `benchmark/models.yaml` |
| `404` no download CVM | Ano ainda não publicado | Confira em dados.cvm.gov.br; ajuste `CVM_BASE_URL` |
| Empresa ambígua | Nome genérico | Use `--empresa` com nome mais específico |
| `rag search` vazio | Índice vazio ou filtro excessivo | `finllm db stats`; reindexe; teste sem ano/empresa |
| Empresa não encontrada | Cadastro não carregado | Rode `finllm cvm download` e `cvm load` primeiro |

---

## 8. Boas práticas

1. **Sempre valide o ambiente na primeira execução:** rode `finllm db stats` e `finllm rag search "teste"` antes de confiar nas respostas.
2. **Use modelos adequados ao seu hardware:** execute `finllm bench hardware` e o benchmark antes de escolher o modelo para produção.
3. **Prefira `--use-tools`** para perguntas que exijam indicadores calculados (P/L, ROE, etc.) — o LLM chama código determinístico, não calcula sozinho.
4. **Use `--data-entrega`** em análises históricas para evitar look-ahead bias (só considere documentos já divulgados).
5. **Não exponha portas 5432/11434 à internet** e troque as senhas padrão do Postgres.
6. **O sistema não substitui analista credenciado.** Revise saídas qualitativas manualmente.

---

## 9. Suporte e contribuição

- Documentação detalhada: `docs/` (00-visão-geral a 08-roadmap + ADRs)
- Changelog: `CHANGELOG.md`
- Contribuição: `CONTRIBUTING.md`
- Issues e problemas: repositório GitHub do projeto

---

*finllm — Apoio à análise financeira. Não é recomendação de investimento.*
