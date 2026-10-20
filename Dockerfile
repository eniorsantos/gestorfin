FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# nvidia-smi não existe aqui: o benchmark usa /api/ps do Ollama para medir VRAM real
RUN apt-get update && apt-get install -y --no-install-recommends curl make \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install -e ".[dev]"

CMD ["sleep", "infinity"]
