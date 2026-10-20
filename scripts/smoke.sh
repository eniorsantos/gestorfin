#!/usr/bin/env bash
# Verificação rápida do ambiente (rode dentro do container app: make shell)
set -euo pipefail
finllm db init
finllm db stats
finllm bench hardware
curl -fsS "${OLLAMA_BASE_URL:-http://ollama:11434}/api/tags" | head -c 400; echo
