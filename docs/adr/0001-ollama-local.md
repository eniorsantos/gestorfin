# ADR 0001 — LLM local com Ollama
**Status:** aceito
**Contexto:** análise financeira com custo previsível, privacidade de eventuais dados pessoais e independência de provedor.
**Decisão:** usar Ollama (API REST nativa) para chat, *tool calling*, saída estruturada e embeddings.
**Consequências:** (+) custo marginal zero, dados locais, troca fácil de modelo. (−) modelos locais alucinam mais e variam em PT-BR e em tool calling ⇒ guardrails obrigatórios e **benchmark por hardware** (este projeto). Hardware define o teto de qualidade.
**Alternativas:** APIs hospedadas (maior qualidade, custo/privacidade); vLLM/llama.cpp direto (mais controle, mais operação).
