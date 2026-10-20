"""Descoberta de hardware. A verdade sobre offload é /api/ps do Ollama (size_vram/size)."""
from __future__ import annotations

import platform
import shutil
import subprocess

import psutil

from ..ollama_client import OllamaClient


def detect(client: OllamaClient | None = None) -> dict:
    info: dict = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_logical": psutil.cpu_count(logical=True),
        "cpu_physical": psutil.cpu_count(logical=False),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "gpus": [],
        "note": "Dentro do Docker, CPU/RAM são do host/VM; GPU só aparece se nvidia-smi estiver disponível.",
    }
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout
            for line in out.strip().splitlines():
                name, mem = [x.strip() for x in line.split(",")]
                info["gpus"].append({"name": name, "vram_gb": round(float(mem) / 1024, 1)})
        except Exception:  # noqa: BLE001
            pass
    if client is not None:
        info["ollama_version"] = client.version()
    return info
