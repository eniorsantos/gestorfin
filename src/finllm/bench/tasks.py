"""Tarefas embutidas (classificação e tool calling). Os itens de RAG vêm do dataset gerado do banco.

ATENÇÃO: as manchetes abaixo são SINTÉTICAS (inventadas) — substitua/estenda com seus próprios
rótulos antes de tirar conclusões sobre sentimento.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from finllm.rag.tools import TOOLS_REAIS


class Classificacao(BaseModel):
    sentimento: Literal["positivo", "neutro", "negativo"]
    relevancia: Literal["alta", "media", "baixa"]
    justificativa: str


CLASSIF_SYSTEM = (
    "Classifique o impacto da notícia/fato relevante para o acionista da companhia. "
    "Use apenas o texto fornecido. Responda no schema JSON."
)

CLASSIF_ITEMS = [
    ("Companhia anuncia lucro líquido recorde no trimestre, 35% acima do mesmo período do ano anterior.", "positivo"),
    ("Empresa comunica pedido de recuperação judicial após inadimplência de debêntures.", "negativo"),
    ("Companhia informa que a assembleia geral ordinária será realizada em 25 de abril.", "neutro"),
    ("Agência rebaixa o rating de crédito da companhia e revisa a perspectiva para negativa.", "negativo"),
    ("Empresa conclui venda de ativo não estratégico por R$ 2 bilhões e reduz a alavancagem para 1,2x dívida líquida/EBITDA.", "positivo"),
    ("Companhia informa a alteração do endereço da sede administrativa.", "neutro"),
    ("Operação policial investiga contratos da companhia; a empresa diz colaborar e vê risco de multas relevantes.", "negativo"),
    ("Empresa eleva a projeção de investimentos e de produção para o ano após resultados acima do esperado.", "positivo"),
    ("Companhia comunica a renúncia de membro do conselho fiscal por motivos pessoais.", "neutro"),
    ("Fábrica principal é paralisada por tempo indeterminado após acidente, comprometendo as entregas do trimestre.", "negativo"),
]

TOOLS = [
    {"type": "function", "function": {
        "name": "get_indicadores",
        "description": "Indicadores fundamentalistas calculados (P/L, ROE, margens, dívida líquida/EBITDA) de um ticker.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Ex.: WEGE3"}},
                       "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_cotacoes",
        "description": "Série histórica de preços (OHLCV) de um ticker.",
        "parameters": {"type": "object", "properties": {
            "ticker": {"type": "string"},
            "periodo": {"type": "string", "enum": ["1m", "6m", "1a", "5a"]}},
            "required": ["ticker", "periodo"]}}},
    {"type": "function", "function": {
        "name": "buscar_documentos",
        "description": "Busca semântica em fatos relevantes, releases e demonstrações da companhia.",
        "parameters": {"type": "object", "properties": {
            "ticker": {"type": "string"}, "pergunta": {"type": "string"}},
            "required": ["ticker", "pergunta"]}}},
    {"type": "function", "function": {
        "name": "get_macro",
        "description": "Série macroeconômica brasileira atual.",
        "parameters": {"type": "object", "properties": {
            "serie": {"type": "string", "enum": ["selic", "ipca", "cambio"]}},
            "required": ["serie"]}}},
]

TOOL_SYSTEM = "Você é um assistente de análise financeira. Use as ferramentas disponíveis para obter dados; nunca invente números."

TOOL_ITEMS = [
    ("Quais são o P/L e o ROE atuais de WEGE3?", {"name": "get_indicadores", "args": {"ticker": "WEGE3"}}),
    ("Me mostre a cotação de PETR4 nos últimos 6 meses.", {"name": "get_cotacoes", "args": {"ticker": "PETR4", "periodo": "6m"}}),
    ("O que a Vale (VALE3) disse no último fato relevante sobre dividendos?", {"name": "buscar_documentos", "args": {"ticker": "VALE3"}}),
    ("Qual é a Selic hoje?", {"name": "get_macro", "args": {"serie": "selic"}}),
    ("Preciso do histórico de preço de ITUB4 dos últimos 5 anos.", {"name": "get_cotacoes", "args": {"ticker": "ITUB4", "periodo": "5a"}}),
    ("Qual a dívida líquida/EBITDA da ABEV3?", {"name": "get_indicadores", "args": {"ticker": "ABEV3"}}),
    ("Como está o IPCA?", {"name": "get_macro", "args": {"serie": "ipca"}}),
    ("Procure nos documentos da MGLU3 menções a recuperação judicial.", {"name": "buscar_documentos", "args": {"ticker": "MGLU3"}}),
]


def executar_tool(nome: str, argumentos: dict) -> dict:
    """Executa uma tool real pelo nome."""
    fn = TOOLS_REAIS.get(nome)
    if fn is None:
        return {"erro": f"Tool não implementada: {nome}"}
    try:
        return fn(**argumentos)
    except TypeError as e:
        return {"erro": f"Argumentos inválidos para {nome}: {e}"}


def builtin_items() -> list[dict]:
    items = []
    for i, (text, label) in enumerate(CLASSIF_ITEMS, 1):
        items.append({"id": f"classif-{i:02d}", "task": "classif", "text": text, "gold": label})
    for i, (q, exp) in enumerate(TOOL_ITEMS, 1):
        items.append({"id": f"tool-{i:02d}", "task": "tools", "question": q, "expected": exp})
    return items
