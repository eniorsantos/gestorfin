# ADR 0003 — Números determinísticos; LLM interpreta
**Status:** aceito
**Decisão:** valores vêm de dados estruturados/código. O LLM não faz aritmética de produção, não converte unidades e só cita valores presentes no contexto; um validador confere cada número.
**Consequências:** (+) reduz o risco principal (alucinação numérica) e torna erros detectáveis. (−) cálculos derivados exigem tools (fases 3–5); o benchmark `rag_calc` mede o quanto o modelo erra quando *obrigado* a calcular.
