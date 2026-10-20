"""Orquestração de agentes (roadmap Fase 5).

Agentes: fundamentalista, técnico, risco ('advogado do diabo') e sintetizador,
com score composto. Cada agente recebe o contexto (RAG + tools) e emite um
parecer; o sintetizador consolida em uma recomendação estruturada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParecerAgente:
    nome: str
    papel: str
    sinal: str  # compra, venda, neutro, abster-se
    confianca: float  # 0-1
    justificativa: str
    evidencias: list[str] = field(default_factory=list)
    riscos: list[str] = field(default_factory=list)


@dataclass
class ResultadoAgentes:
    ticker: str
    pareceres: list[ParecerAgente] = field(default_factory=list)
    sinal_final: str = "abster-se"
    confianca_final: float = 0.0
    score_composto: float = 0.0
    justificativa_sintese: str = ""
    riscos_principais: list[str] = field(default_factory=list)


class AgenteFundamentalista:
    """Avalia indicadores fundamentalistas (P/L, ROE, ROIC, dívida/EBITDA, F-Score)."""

    def avaliar(self, indicadores: dict) -> ParecerAgente:
        sinais = 0
        justificativas = []
        riscos = []

        pl = indicadores.get("pl")
        roe = indicadores.get("roe")
        roic = indicadores.get("roic")
        div_ebitda = indicadores.get("divida_liquida_ebitda")
        f_score = indicadores.get("f_score")

        if pl is not None:
            if pl < 15:
                sinais += 1
                justificativas.append(f"P/L {pl:.2f} abaixo de 15 (barato)")
            elif pl > 30:
                sinais -= 1
                riscos.append(f"P/L {pl:.2f} elevado (>30)")
        if roe is not None:
            if roe > 0.15:
                sinais += 1
                justificativas.append(f"ROE {roe:.1%} acima de 15%")
            elif roe < 0:
                sinais -= 1
                riscos.append("ROE negativo")
        if roic is not None:
            if roic > 0.12:
                sinais += 1
                justificativas.append(f"ROIC {roic:.1%} acima de 12%")
        if div_ebitda is not None:
            if div_ebitda < 3:
                sinais += 1
                justificativas.append(f"Dív.Líq./EBITDA {div_ebitda:.2f} abaixo de 3x")
            elif div_ebitda > 6:
                sinais -= 1
                riscos.append(f"Alavancagem elevada ({div_ebitda:.2f}x)")
        if f_score is not None:
            if f_score >= 7:
                sinais += 1
                justificativas.append(f"F-Score Piotroski {f_score}/9 (forte)")
            elif f_score <= 3:
                sinais -= 1
                riscos.append(f"F-Score Piotroski {f_score}/9 (fraco)")

        if sinais >= 2:
            sinal = "compra"
            confianca = min(0.9, 0.5 + sinais * 0.15)
        elif sinais <= -2:
            sinal = "venda"
            confianca = min(0.9, 0.5 + abs(sinais) * 0.15)
        else:
            sinal = "neutro"
            confianca = 0.4

        return ParecerAgente(
            nome="fundamentalista",
            papel="Analisa demonstrações financeiras e indicadores de valor",
            sinal=sinal,
            confianca=confianca,
            justificativa="; ".join(justificativas) or "Indicadores mistos ou insuficientes",
            evidencias=justificativas,
            riscos=riscos,
        )


class AgenteTecnico:
    """Avalia indicadores técnicos (RSI, MACD, médias móveis, suporte/resistência)."""

    def avaliar(self, tecnicos: dict) -> ParecerAgente:
        sinais = 0
        justificativas = []
        riscos = []

        sinal = tecnicos.get("sinal", "neutro")
        rsi = tecnicos.get("rsi_14")
        macd_hist = tecnicos.get("macd_hist")
        sma20 = tecnicos.get("sma_20")
        sma50 = tecnicos.get("sma_50")

        if sinal == "compra":
            sinais += 1
        elif sinal == "venda":
            sinais -= 1

        if rsi is not None:
            if rsi < 30:
                sinais += 1
                justificativas.append(f"RSI {rsi:.1f} em sobrevenda")
            elif rsi > 70:
                sinais -= 1
                riscos.append(f"RSI {rsi:.1f} em sobrecompra")
        if macd_hist is not None:
            if macd_hist > 0:
                sinais += 1
                justificativas.append("MACD histograma positivo")
            elif macd_hist < 0:
                sinais -= 1
                justificativas.append("MACD histograma negativo")
        if sma20 is not None and sma50 is not None:
            if sma20 > sma50:
                justificativas.append("SMA20 acima da SMA50 (tendência de alta)")
            else:
                justificativas.append("SMA20 abaixo da SMA50 (tendência de baixa)")
                sinais -= 1

        if sinais >= 2:
            sinal_final = "compra"
            confianca = min(0.85, 0.5 + sinais * 0.15)
        elif sinais <= -2:
            sinal_final = "venda"
            confianca = min(0.85, 0.5 + abs(sinais) * 0.15)
        else:
            sinal_final = "neutro"
            confianca = 0.4

        return ParecerAgente(
            nome="tecnico",
            papel="Analisa preço, volume e indicadores técnicos de curto prazo",
            sinal=sinal_final,
            confianca=confianca,
            justificativa="; ".join(justificativas) or "Indicadores técnicos mistos",
            evidencias=justificativas,
            riscos=riscos,
        )


class AgenteRisco:
    """'Advogado do diabo': destaca riscos e argumentos contra a tese."""

    def avaliar(self, contexto: dict) -> ParecerAgente:
        riscos = []
        sinais = 0

        div_ebitda = contexto.get("divida_liquida_ebitda")
        if div_ebitda is not None and div_ebitda > 4:
            riscos.append(f"Alavancagem elevada ({div_ebitda:.2f}x EBITDA)")
            sinais -= 1
        pl = contexto.get("pl")
        if pl is not None and pl > 25:
            riscos.append(f"P/L elevado ({pl:.2f}), possível sobreavaliação")
            sinais -= 1
        rsi = contexto.get("rsi_14")
        if rsi is not None and rsi > 75:
            riscos.append(f"RSI {rsi:.1f} em zona de sobrecompra extrema")
            sinais -= 1
        # Sempre lista pelo menos um risco genérico de mercado
        riscos.append("Risco de mercado e setorial não capturado pelos dados históricos")
        riscos.append("Dados da CVM podem não refletir eventos recentes não divulgados")

        if sinais <= -1:
            sinal_final = "venda"
            confianca = min(0.9, 0.5 + abs(sinais) * 0.2)
        else:
            sinal_final = "neutro"
            confianca = 0.5

        return ParecerAgente(
            nome="risco",
            papel="Advogado do diabo: identifica riscos e pontos fracos da tese",
            sinal=sinal_final,
            confianca=confianca,
            justificativa="; ".join(riscos),
            riscos=riscos,
        )


class AgenteSintetizador:
    """Consolida os pareceres em um score composto e recomendação final."""

    PESOS = {
        "fundamentalista": 0.4,
        "tecnico": 0.3,
        "risco": 0.3,
    }

    SINAL_SCORE = {"compra": 1, "neutro": 0, "venda": -1, "abster-se": 0}

    def sintetizar(self, ticker: str, pareceres: list[ParecerAgente]) -> ResultadoAgentes:
        mapa = {p.nome: p for p in pareceres}
        score = 0.0
        peso_total = 0.0
        riscos_principais = []
        justificativas = []

        for papel, peso in self.PESOS.items():
            p = mapa.get(papel)
            if p is None:
                continue
            score += self.SINAL_SCORE.get(p.sinal, 0) * peso * p.confianca
            peso_total += peso * p.confianca
            if p.riscos:
                riscos_principais.extend(p.riscos[:2])
            justificativas.append(f"[{p.nome}] {p.justificativa}")

        if peso_total > 0:
            score_composto = score / peso_total
        else:
            score_composto = 0.0

        if score_composto >= 0.3:
            sinal_final = "compra"
        elif score_composto <= -0.3:
            sinal_final = "venda"
        else:
            sinal_final = "neutro"

        confianca_final = min(0.95, abs(score_composto) + 0.3)

        return ResultadoAgentes(
            ticker=ticker,
            pareceres=pareceres,
            sinal_final=sinal_final,
            confianca_final=round(confianca_final, 2),
            score_composto=round(score_composto, 3),
            justificativa_sintese=" | ".join(justificativas),
            riscos_principais=list(dict.fromkeys(riscos_principais))[:5],
        )


def executar_agentes(
    ticker: str,
    indicadores: Optional[dict] = None,
    tecnicos: Optional[dict] = None,
    contexto: Optional[dict] = None,
) -> ResultadoAgentes:
    """Executa todos os agentes e retorna o resultado consolidado."""
    indicadores = indicadores or {}
    tecnicos = tecnicos or {}
    contexto = contexto or {}

    p_fund = AgenteFundamentalista().avaliar(indicadores)
    p_tec = AgenteTecnico().avaliar(tecnicos)
    p_risco = AgenteRisco().avaliar({**indicadores, **tecnicos, **contexto})

    return AgenteSintetizador().sintetizar(ticker, [p_fund, p_tec, p_risco])
