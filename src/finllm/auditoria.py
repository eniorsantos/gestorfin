"""Persistência de consultas para auditoria (roadmap Fase 2)."""
from __future__ import annotations

import json
from typing import Any

def _connect():
    from .db import connect
    return connect()


def registrar_consulta(
    *,
    pergunta: str,
    modelo: str,
    temperatura: float | None = None,
    seed: int | None = None,
    num_ctx: int | None = None,
    filtros: dict[str, Any] | None = None,
    chunk_ids: list[int] | None = None,
    resposta: dict[str, Any] | None = None,
    validacao: dict[str, Any] | None = None,
) -> int:
    """Insere uma consulta na tabela auditoria e retorna o id."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO consultas
                    (pergunta, modelo, temperatura, seed, num_ctx, filtros,
                     chunk_ids, resposta, validacao)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
                RETURNING id
                """,
                (
                    pergunta,
                    modelo,
                    temperatura,
                    seed,
                    num_ctx,
                    json.dumps(filtros or {}),
                    json.dumps(chunk_ids or []),
                    json.dumps(resposta or {}),
                    json.dumps(validacao or {}),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return int(row[0])


def listar_consultas(limit: int = 20) -> list[dict[str, Any]]:
    """Lista as últimas consultas registradas."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, pergunta, modelo, temperatura, seed, num_ctx,
                       filtros, chunk_ids, resposta, validacao, criado_em
                FROM consultas
                ORDER BY criado_em DESC
                LIMIT %s
                """,
                (limit,),
            )
            colunas = [d.name for d in cur.description]
            return [dict(zip(colunas, row)) for row in cur.fetchall()]
