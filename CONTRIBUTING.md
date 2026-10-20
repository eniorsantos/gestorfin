# Contribuindo
1. `pip install -e ".[dev]"`; `pytest -q`; `ruff check src tests`.
2. Mudou prompt, chunking ou recuperação? Rode o benchmark (`gold` e `retrieved`) antes/depois e anexe o `summary.csv`.
3. Novas decisões relevantes: crie um ADR em `docs/adr/`.
4. Atualize `docs/` e `CHANGELOG.md`.
5. Nunca versione `.env`, `data/` ou resultados com dados pessoais.
Licença: defina antes de publicar (nenhuma foi escolhida).
