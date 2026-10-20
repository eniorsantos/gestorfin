# ADR 0002 — PostgreSQL + pgvector com busca híbrida
**Status:** aceito
**Decisão:** um único Postgres guarda dados relacionais, texto (`tsvector` português) e vetores (HNSW, cosseno); recuperação = vetorial + FTS fundidos por RRF.
**Por quê:** números, nomes próprios e códigos de conta são mal servidos só por embeddings; um banco só simplifica operação, filtros SQL (empresa/ano) e consistência.
**Consequências:** (+) simples, filtros fortes, transacional. (−) escala menor que bancos vetoriais dedicados (suficiente para B3 inteira em dezenas de milhões de vetores? não validado — medir). Dimensão do vetor fixa por tabela.
**Alternativas:** Qdrant/Weaviate (mais recursos de busca, mais um serviço), Elasticsearch/OpenSearch.
