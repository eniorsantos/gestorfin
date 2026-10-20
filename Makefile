SHELL := /bin/bash
DC       ?= docker compose
RUN      = $(DC) exec app finllm
EMPRESAS ?= PETROBRAS VALE WEG
YEARS    ?= 2022-2024
EMP_FLAGS = $(foreach e,$(EMPRESAS),--empresa "$(e)")

.PHONY: help env up up-nvidia up-amd up-mac down logs shell init pipeline ask bench-build bench bench-report test lint

help:  ## Lista os comandos
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

env:  ## Cria .env a partir do exemplo
	@test -f .env || cp .env.example .env

up: env  ## Sobe tudo (CPU)
	$(DC) up -d --build

up-nvidia: env  ## Sobe tudo com GPU NVIDIA
	$(DC) -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up -d --build

up-amd: env  ## Sobe tudo com GPU AMD (ROCm)
	$(DC) -f docker-compose.yml -f docker-compose.gpu-amd.yml up -d --build

up-mac: env  ## Mac: Ollama nativo (Metal); sobe só postgres + app
	OLLAMA_BASE_URL=http://host.docker.internal:11434 $(DC) up -d --build postgres app

down:  ## Para os serviços (mantém volumes)
	$(DC) down

logs:  ## Logs em tempo real
	$(DC) logs -f --tail=100

shell:  ## Shell no container da aplicação
	$(DC) exec app bash

init:  ## Cria o schema do banco
	$(RUN) db init

pipeline:  ## Pipeline completo p/ EMPRESAS e YEARS (ex.: make pipeline EMPRESAS="WEG ITAU UNIBANCO")
	$(RUN) db init
	$(RUN) cvm download --years $(YEARS)
	$(RUN) cvm load --years $(YEARS) $(EMP_FLAGS)
	$(RUN) rag index-statements --years $(YEARS) $(EMP_FLAGS)

ask:  ## Pergunta: make ask Q="Qual a receita líquida da WEG em 2023?"
	$(RUN) rag ask "$(Q)" --verbose

bench-build:  ## Gera dataset de avaliação a partir do banco
	$(RUN) bench build

bench:  ## Roda o benchmark (CONTEXT=gold|retrieved, MAXMEM=GB)
	$(RUN) bench run --context $(or $(CONTEXT),gold) $(if $(MAXMEM),--max-mem-gb $(MAXMEM),)

bench-report:  ## Relatório da última execução
	$(RUN) bench report

test:  ## Testes unitários (não exigem banco nem Ollama)
	$(DC) exec app pytest -q

lint:  ## Ruff
	$(DC) exec app ruff check src tests
