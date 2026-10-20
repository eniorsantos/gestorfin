# ADR 0005 — Cartões textuais de demonstrações em vez de PDFs
**Status:** aceito
**Contexto:** extrair tabelas de PDFs de ITR/DFP é frágil; a CVM publica os mesmos dados estruturados.
**Decisão:** carregar os CSVs padronizados em tabela e gerar, por (empresa, documento, demonstração, consolidação, período), um texto com cabeçalho completo e linhas `conta | descrição | valor (R$ mil)`; chunks repetem o cabeçalho.
**Consequências:** (+) valores exatos, verdade-fundamento para o benchmark, busca por empresa/período robusta. (−) cobre só o padronizado (não notas explicativas, teleconferências — esses vêm do IPE/PDF); volume de chunks alto se indexar todas as empresas.
