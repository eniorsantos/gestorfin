"""Testes dos agentes (Fase 5)."""
from finllm.agentes import executar_agentes, ParecerAgente


def test_executar_agentes_sem_dados():
    resultado = executar_agentes("PETR4")
    assert resultado.ticker == "PETR4"
    assert resultado.sinal_final in ("compra", "venda", "neutro")
    assert 0 <= resultado.confianca_final <= 1
    assert -1 <= resultado.score_composto <= 1


def test_executar_agentes_com_dados():
    indicadores = {"pl": 10.0, "roe": 0.2, "roic": 0.15,
                   "divida_liquida_ebitda": 2.0, "f_score": 8}
    tecnicos = {"sinal": "compra", "rsi_14": 25.0, "macd_hist": 0.5,
                "sma_20": 11.0, "sma_50": 10.0}
    contexto = {}
    resultado = executar_agentes("WEGE3", indicadores=indicadores,
                                 tecnicos=tecnicos, contexto=contexto)
    assert resultado.ticker == "WEGE3"
    assert len(resultado.pareceres) == 3
    nomes = {p.nome for p in resultado.pareceres}
    assert nomes == {"fundamentalista", "tecnico", "risco"}


def test_parecer_agente_campos():
    p = ParecerAgente(nome="fundamentalista", papel="valor", sinal="compra",
                      confianca=0.8, justificativa="barato",
                      evidencias=["P/L baixo"], riscos=["risco de mercado"])
    assert p.sinal == "compra"
    assert p.confianca == 0.8
