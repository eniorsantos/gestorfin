"""Cliente mínimo da API REST do Ollama (httpx). Ver docs/adr/0004."""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import settings


class OllamaError(RuntimeError):
    pass


def timings(resp: dict) -> dict[str, float]:
    """Converte os campos de duração (ns) do Ollama em métricas legíveis."""
    ns = 1e9
    ev_n, ev_d = resp.get("eval_count", 0), resp.get("eval_duration", 0)
    pe_n, pe_d = resp.get("prompt_eval_count", 0), resp.get("prompt_eval_duration", 0)
    return {
        "load_s": resp.get("load_duration", 0) / ns,
        "total_s": resp.get("total_duration", 0) / ns,
        "prompt_tokens": pe_n,
        "gen_tokens": ev_n,
        "prompt_tps": (pe_n / (pe_d / ns)) if pe_d else 0.0,
        "gen_tps": (ev_n / (ev_d / ns)) if ev_d else 0.0,
    }


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.http = httpx.Client(
            base_url=base_url or settings.ollama_base_url,
            timeout=timeout or settings.http_timeout,
        )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=1, max=5),
        reraise=True,
    )
    def _post(self, path: str, payload: dict) -> dict:
        r = self.http.post(path, json=payload)
        if r.status_code >= 400:
            raise OllamaError(f"POST {path} -> {r.status_code}: {r.text[:500]}")
        return r.json()

    def _get(self, path: str) -> dict:
        r = self.http.get(path)
        if r.status_code >= 400:
            raise OllamaError(f"GET {path} -> {r.status_code}: {r.text[:500]}")
        return r.json()

    # ---- API ----
    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        schema: dict | None = None,
        tools: list[dict] | None = None,
        options: dict | None = None,
        think: bool | None = None,
        keep_alive: str | None = None,
    ) -> dict[str, Any]:
        opts = {
            "temperature": settings.llm_temperature,
            "seed": settings.llm_seed,
            "num_ctx": settings.llm_num_ctx,
        }
        opts.update(options or {})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": opts,
            "keep_alive": keep_alive or settings.llm_keep_alive,
        }
        if schema is not None:
            payload["format"] = schema
        if tools:
            payload["tools"] = tools
        if think is None:
            think = settings.llm_think
        if think is not None:
            payload["think"] = think
        return self._post("/api/chat", payload)

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        out = self._post("/api/embed", {"model": model, "input": texts, "keep_alive": settings.llm_keep_alive})
        return out["embeddings"]

    def tags(self) -> list[str]:
        return [m["name"] for m in self._get("/api/tags").get("models", [])]

    def ps(self) -> list[dict]:
        return self._get("/api/ps").get("models", [])

    def version(self) -> str:
        try:
            return self._get("/api/version").get("version", "?")
        except Exception:
            return "?"

    def unload(self, model: str) -> None:
        try:
            self._post("/api/generate", {"model": model, "keep_alive": 0})
        except Exception:
            pass

    def pull(self, model: str) -> None:
        self._post("/api/pull", {"model": model, "stream": False})
