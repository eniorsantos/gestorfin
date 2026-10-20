"""Avaliação contínua do LLM (roadmap Fase 8).

Executa o benchmark como regressão em CI comparando contra uma linha de base
salva. Gera alerta se alguma métrica crítica cair além do limiar.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MetricaReferencia:
    modelo: str
    tarefa: str
    acuracia: float
    ic95_lo: float
    ic95_hi: float
    json_valid: float
    resp_errada_confiante: float


@dataclass
class ResultadoRegressao:
    modelo: str
    tarefa: str
    acuracia_atual: float
    referencia: Optional[MetricaReferencia]
    regressou: bool
    diferenca: float
    limiar: float


def carregar_referencia(caminho: Path) -> dict[str, MetricaReferencia]:
    """Carrega o arquivo de referência (gerado por uma execução de benchmark aprovada)."""
    if not caminho.exists():
        return {}
    data = json.loads(caminho.read_text(encoding="utf-8"))
    saida: dict[str, MetricaReferencia] = {}
    for item in data.get("metricas", []):
        chave = f"{item['modelo']}::{item['tarefa']}"
        saida[chave] = MetricaReferencia(
            modelo=item["modelo"],
            tarefa=item["tarefa"],
            acuracia=float(item["acuracia"]),
            ic95_lo=float(item["ic95_lo"]),
            ic95_hi=float(item["ic95_hi"]),
            json_valid=float(item.get("json_valid", 1.0)),
            resp_errada_confiante=float(item.get("resp_errada_confiante", 0.0)),
        )
    return saida


def comparar_com_referencia(
    resumo_atual: list[dict],
    referencia: dict[str, MetricaReferencia],
    limiar_queda: float = 0.05,
) -> list[ResultadoRegressao]:
    """Compara o resumo atual do benchmark com a referência.

    `limiar_queda` = queda máxima tolerada na acurácia (ex.: 0.05 = 5 p.p.).
    """
    resultados: list[ResultadoRegressao] = []
    for linha in resumo_atual:
        modelo = linha.get("modelo")
        for tarefa in ("rag_fact", "rag_abstain", "rag_calc", "tools", "classif"):
            valor = linha.get(tarefa)
            if valor is None:
                continue
            chave = f"{modelo}::{tarefa}"
            ref = referencia.get(chave)
            regressou = False
            diferenca = 0.0
            if ref is not None:
                diferenca = float(valor) - ref.acuracia
                regressou = diferenca < -limiar_queda
            resultados.append(
                ResultadoRegressao(
                    modelo=modelo,
                    tarefa=tarefa,
                    acuracia_atual=float(valor),
                    referencia=ref,
                    regressou=regressou,
                    diferenca=round(diferenca, 4),
                    limiar=limiar_queda,
                )
            )
    return resultados


def gerar_relatorio_regressao(
    resultados: list[ResultadoRegressao],
    caminho_saida: Path,
) -> Path:
    """Gera report.md da regressão."""
    linhas = ["# Relatório de Regressão do Benchmark (Fase 8)", ""]
    regressoes = [r for r in resultados if r.regressou]
    if regressoes:
        linhas.append("## ⚠️ Regressões detectadas")
        for r in regressoes:
            ref = r.referencia
            linhas.append(
                f"- **{r.modelo} / {r.tarefa}**: {r.acuracia_atual:.3f} "
                f"(ref: {ref.acuracia:.3f}, Δ {r.diferenca:+.3f})"
            )
    else:
        linhas.append("## ✅ Sem regressões detectadas")
    linhas.append("")
    linhas.append("## Detalhe por modelo e tarefa")
    for r in resultados:
        ref = r.referencia
        ref_str = f"{ref.acuracia:.3f}" if ref else "n/d"
        status = "REGRESSÃO" if r.regressou else "ok"
        linhas.append(
            f"- {r.modelo} | {r.tarefa}: atual={r.acuracia_atual:.3f}, ref={ref_str}, "
            f"Δ={r.diferenca:+.3f} -> {status}"
        )
    caminho_saida.write_text("\n".join(linhas), encoding="utf-8")
    return caminho_saida


def salvar_referencia(
    resumo_atual: list[dict],
    caminho: Path,
) -> Path:
    """Salva o resumo atual como nova referência de regressão."""
    metricas = []
    for linha in resumo_atual:
        modelo = linha.get("modelo")
        for tarefa in ("rag_fact", "rag_abstain", "rag_calc", "tools", "classif"):
            valor = linha.get(tarefa)
            if valor is None:
                continue
            metricas.append({
                "modelo": modelo,
                "tarefa": tarefa,
                "acuracia": float(valor),
                "ic95_lo": float(linha.get(f"{tarefa}_lo", 0.0)),
                "ic95_hi": float(linha.get(f"{tarefa}_hi", 1.0)),
                "json_valid": float(linha.get("json_valid", 1.0)),
                "resp_errada_confiante": float(linha.get("resp_errada_confiante", 0.0)),
            })
    caminho.write_text(json.dumps({"metricas": metricas}, indent=2, ensure_ascii=False), encoding="utf-8")
    return caminho
