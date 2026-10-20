# 06 · Guardrails e conformidade

## Controles técnicos
| Risco | Controle | Onde |
|---|---|---|
| Alucinação de números | validação determinística contra o contexto + retry + aviso | `rag/guardrails.py`, `rag/answer.py` |
| Responder sem base | abstenção explícita (`nao_encontrado`) medida no benchmark | prompt + `rag_abstain` |
| Fonte desconhecida | citações obrigatórias (`citacoes`) mapeadas para trechos/título | `answer.py`, CLI |
| Truncamento silencioso de contexto | `num_ctx` explícito | `config.py`, `OllamaClient.chat` |
| Não reprodutibilidade | `temperature=0`, `seed`, parâmetros salvos em `run_config.json` | benchmark |
| Troca de embedding sem reindexar | checagem de dimensão | `schema.init_db` |
| Prompt injection via documentos (IPE) | conteúdo tratado como dados; saída restrita a JSON schema; LLM **sem ferramentas** com efeito colateral neste módulo | desenho |

## Limites dos guardrails
- Valida **presença** do número no contexto, não se é o **número certo** (pode citar o valor de outro período presente no contexto). O benchmark `rag_fact` mede esse erro.
- Ignora anos e inteiros ≤ 31; números derivados são sinalizados.
- Não verifica afirmações qualitativas. Para teses/resumos, revisão humana é necessária.

## Auditoria

Tabela `consultas` persistida (roadmap Fase 2 ✅ implementada): registra por consulta pergunta, modelo, temperatura, seed, num_ctx, filtros, ids dos chunks, resposta e resultado da validação.

Comando: `finllm auditoria list [--limit N]`.

Hoje, `rag ask --verbose` também mostra filtros/tentativas/tempos. A validação é registrada automaticamente a cada chamada de `rag answer` (habilitada por padrão).

## Aviso legal
O sistema é **apoio à análise**. No Brasil, a atividade de **análise de valores mobiliários** é regulada (CVM, Resolução CVM 20) e exige credenciamento para quem a exerce profissionalmente (ex.: analista CNPI). **Não** distribua saídas deste sistema como recomendação a terceiros sem avaliação jurídica/compliance. Isto não é aconselhamento jurídico.

## Privacidade
- Dados da CVM são públicos. Com Ollama local, nada sai da máquina além do download dos dados públicos e dos modelos.
- Se você adicionar dados pessoais (carteira, posições), mantenha-os fora de logs e de repositórios; `.env` e `data/` já estão no `.gitignore`.
- Troque as senhas padrão do Postgres (`.env`) e **não exponha** as portas 5432/11434 à internet (o compose publica no host; restrinja por firewall ou `127.0.0.1:` no mapeamento).
