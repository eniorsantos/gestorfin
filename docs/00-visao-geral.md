# 00 · Visão geral

## Objetivo
Sistema de apoio à análise **fundamentalista** (e, nas próximas fases, **técnica**) em que um LLM **local** (Ollama) responde perguntas fundamentadas em dados oficiais da CVM, com citação de fonte e verificação automática dos números.

## Escopo desta entrega
1. Infraestrutura reproduzível (`docker compose`): Ollama, Postgres + pgvector, container da aplicação.
2. Ingestão dos dados abertos da CVM: cadastro, DFP (anual), ITR (trimestral), IPE (documentos narrativos).
3. Pipeline RAG híbrido (vetorial + texto completo) com resposta estruturada, citações e guardrail numérico.
4. Benchmark para comparar modelos no seu hardware, com dataset gerado do seu próprio banco.
5. Motor fundamentalista determinístico e motor técnico (OHLCV/indicadores) expostos como tools.
6. Agentes múltiplos (fundamentalista, técnico, risco, sintetizador) com score composto.
7. Backtest point-in-time e dashboard (Streamlit) com alertas e screener da B3.

**Fora do escopo (por ora):** walk-forward avançado, paper trading com execução real — ver [roadmap](08-roadmap.md).

## Princípios
1. **Números não vêm do LLM.** Vêm do banco/código. O LLM lê, resume e cita.
2. **Abster-se é uma resposta válida.** Dado ausente ⇒ `nao_encontrado=true`. O erro mais perigoso é o número errado dito com confiança.
3. **Tudo verificável.** Cada resposta cita trechos; todo número é conferido contra o contexto.
4. **Medir antes de escolher.** Modelo escolhido por benchmark no seu hardware, não por reputação.
5. **Local e reprodutível.** Temperatura 0, seed fixo, versões e parâmetros registrados.

## Glossário
| Termo | Significado |
|---|---|
| CVM | Comissão de Valores Mobiliários (dados em dados.cvm.gov.br) |
| DFP / ITR | Demonstrações Financeiras Padronizadas (anual) / Informações Trimestrais |
| IPE | Documentos periódicos e eventuais: fatos relevantes, comunicados, etc. |
| DRE / BPA / BPP | Resultado / Balanço Ativo / Balanço Passivo |
| `CD_CVM` | Código da companhia na CVM (chave usada no projeto) |
| Cartão | Texto que representa uma demonstração de uma empresa em um período (ver ADR 0005) |
| RRF | Reciprocal Rank Fusion — fusão de rankings da busca vetorial e textual |
| Gold / retrieved | Modos do benchmark: contexto correto garantido × recuperação real |
