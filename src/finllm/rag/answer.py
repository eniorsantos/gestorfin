"""Geração da resposta com citações, validação numérica e function calling (tools reais)."""
from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from ..auditoria import registrar_consulta
from ..ollama_client import OllamaClient, timings
from .guardrails import validate_numbers
from .retrieve import Hit, retrieve


class Resposta(BaseModel):
    nao_encontrado: bool = Field(description="true se o contexto não contém a informação pedida")
    resposta: str = Field(description="resposta curta em português, citando [n] dos trechos usados")
    valor: float | None = Field(default=None, description="valor numérico único, se aplicável (ponto decimal)")
    unidade: str | None = Field(default=None, description="ex.: 'R$ mil', '%'")
    citacoes: list[int] = Field(default_factory=list, description="números dos trechos usados")


SYSTEM = """Você é um assistente de análise financeira. Responda usando EXCLUSIVAMENTE os trechos de contexto numerados.

Regras:
1. Nunca use conhecimento externo nem invente números. Copie os valores exatamente como aparecem no contexto.
2. Os valores das demonstrações financeiras estão em R$ mil, salvo indicação contrária. Só converta unidades se a pergunta pedir.
3. Confira empresa, documento (DFP anual / ITR trimestral), consolidação (Consolidado x Individual), período e código da conta do trecho.
4. Se o contexto não contiver a informação pedida (empresa, período ou conta diferentes), use nao_encontrado=true, valor=null e explique em 'resposta'.
5. Liste em 'citacoes' os números dos trechos usados.
6. Se a resposta for um único valor, preencha 'valor' (número sem separador de milhar, ponto decimal) e 'unidade'.
7. Isto é apoio à análise, não recomendação de investimento."""

TOOL_SYSTEM = """Você é um assistente de análise financeira. Use as ferramentas disponíveis para obter dados; nunca invente números.
Se a pergunta puder ser respondida com os trechos de contexto, responda diretamente. Caso contrário, use a tool adequada."""


def build_messages(question: str, contexts: list[str]) -> list[dict]:
    ctx = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, 1)) or "(sem contexto)"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Contexto:\n{ctx}\n\nPergunta: {question}"},
    ]


def parse_resposta(content: str) -> Resposta | None:
    try:
        return Resposta.model_validate(json.loads(content))
    except Exception:  # noqa: BLE001
        return None


def answer(
    conn,
    client: OllamaClient,
    question: str,
    *,
    model: str,
    cd_cvm: int | None = None,
    k: int | None = None,
    think: bool | None = None,
    max_retries: int = 1,
    use_tools: bool = True,
    registro_auditoria: bool = True,
    data_entrega_max=None,
) -> dict:
    """Responde uma pergunta com RAG + guardrails, opcionalmente via function calling.

    Fluxo:
    1. Recupera contexto híbrido.
    2. Tenta responder com RAG + validação numérica.
    3. Se o LLM solicitar uma tool (function calling), executa a tool real e incorpora o resultado.
    4. Registra na auditoria (se habilitado).

    `data_entrega_max` ativa o modo point-in-time: só considera documentos entregues
    na CVM até aquela data, evitando look-ahead bias.
    """
    from .tools import executar_tool, TOOL_DEFINICOES

    t0 = time.perf_counter()
    hits, filters = retrieve(
        conn, client, question, k=k, cd_cvm=cd_cvm, data_entrega_max=data_entrega_max
    )
    contexts = [h.content for h in hits]
    messages = build_messages(question, contexts)
    attempts = []
    parsed: Resposta | None = None
    validation = None
    tool_result: dict | None = None
    tool_called: str | None = None

    for attempt in range(max_retries + 1):
        if use_tools and attempt == 0:
            resp = client.chat(
                model,
                messages,
                tools=TOOL_DEFINICOES,
                think=think,
            )
            tool_calls = resp["message"].get("tool_calls")
            if tool_calls:
                call = tool_calls[0]
                fn_name = call["function"]["name"]
                args = call["function"].get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                tool_called = fn_name
                tool_result = executar_tool(fn_name, args)
                # Incorpora o resultado da tool e pede ao modelo para formatar a resposta final
                messages = messages + [
                    {"role": "assistant", "content": "", "tool_calls": tool_calls},
                    {"role": "tool", "content": json.dumps(tool_result, ensure_ascii=False)},
                ]
                continue

        resp = client.chat(model, messages, schema=Resposta.model_json_schema(), think=think)
        parsed = parse_resposta(resp["message"]["content"])
        attempts.append(timings(resp))
        if parsed is None:
            break
        validation = validate_numbers(parsed.resposta, contexts)
        if validation.ok or attempt == max_retries:
            break
        messages = messages + [
            {"role": "assistant", "content": resp["message"]["content"]},
            {"role": "user", "content": (
                f"Os números {validation.unsupported} não aparecem no contexto. Refaça usando apenas "
                "valores presentes nos trechos, ou marque nao_encontrado=true."
            )},
        ]

    # Se a tool retornou dados, monta a resposta final com eles
    if tool_result is not None and parsed is not None:
        parsed.resposta = f"{parsed.resposta}\n\nDados via tool '{tool_called}': {json.dumps(tool_result, ensure_ascii=False)}"

    resultado = {
        "question": question,
        "model": model,
        "answer": parsed,
        "hits": hits,
        "filters": filters,
        "validation": validation,
        "tool_called": tool_called,
        "tool_result": tool_result,
        "attempts": attempts,
        "elapsed_s": time.perf_counter() - t0,
    }

    if registro_auditoria and parsed is not None:
        try:
            registrar_consulta(
                pergunta=question,
                modelo=model,
                temperatura=0.0,
                seed=42,
                num_ctx=None,
                filtros=filters,
                chunk_ids=[h.id for h in hits],
                resposta=parsed.model_dump() if parsed else {},
                validation={"ok": validation.ok if validation else None,
                            "unsupported": validation.unsupported if validation else None},
            )
        except Exception:  # noqa: BLE001 - auditoria não deve quebrar o fluxo
            pass

    return resultado


def format_hit(i: int, h: Hit) -> str:
    return f"[{i}] ({h.via}, score {h.score:.4f}) {h.title or h.doc_type} — {h.denom}"
