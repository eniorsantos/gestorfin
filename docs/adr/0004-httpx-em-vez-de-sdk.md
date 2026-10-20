# ADR 0004 — httpx direto na API do Ollama
**Status:** aceito
**Decisão:** cliente fino sobre `/api/chat`, `/api/embed`, `/api/ps`, `/api/tags`, `/api/pull`, sem o SDK oficial.
**Por quê:** controle total dos campos de tempo (`load_duration`, `eval_duration`…), de `think`, `format` e `keep_alive`, e menos acoplamento a versões do SDK — essencial para medir performance.
**Consequências:** (+) transparência. (−) manter o contrato da API; mudanças no Ollama podem exigir ajuste em `ollama_client.py`.
