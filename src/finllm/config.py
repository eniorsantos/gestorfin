"""Configuração central (variáveis de ambiente / .env)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://finllm:finllm@localhost:5432/finllm"
    ollama_base_url: str = "http://localhost:11434"

    llm_model: str = "qwen3:8b"
    embed_model: str = "bge-m3"
    embed_dim: int = 1024
    llm_num_ctx: int = 8192
    llm_temperature: float = 0.0
    llm_seed: int = 42
    llm_think: bool | None = False
    llm_keep_alive: str = "30m"

    data_dir: Path = Path("data")
    cvm_base_url: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA"
    ipe_categories: str = "Fato Relevante,Comunicado ao Mercado"
    http_timeout: float = 300.0

    rag_top_k: int = 6
    chunk_max_chars: int = 2500

    @property
    def categories(self) -> list[str]:
        return [c.strip() for c in self.ipe_categories.split(",") if c.strip()]


settings = Settings()
