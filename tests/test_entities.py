from finllm.rag.entities import aliases, core, norm


def test_norm_e_core():
    assert norm("Petróleo Brasileiro S.A.") == "PETROLEO BRASILEIRO S A"
    assert core("AMBEV S.A.") == "AMBEV"
    assert core("ITAÚ UNIBANCO HOLDING S.A.") == "ITAU UNIBANCO"


def test_aliases_com_nome_fantasia():
    assert aliases("PETRÓLEO BRASILEIRO S.A. - PETROBRAS") == {"PETROLEO BRASILEIRO", "PETROBRAS"}


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        rows = self.rows

        class C:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def execute(s, q, *a): pass
            def fetchall(s): return rows
        return C()


def test_find_in_text_e_resolve():
    from finllm.rag.entities import find_in_text, resolve_empresa

    conn = FakeConn([(9512, "PETRÓLEO BRASILEIRO S.A. - PETROBRAS"), (4170, "VALE S.A."), (1, "VALE DO RIO DOCE ENERGIA S.A.")])
    assert find_in_text(conn, "Qual a receita da Petrobras em 2023?") == 9512
    assert find_in_text(conn, "lucro da VALE em 2022") == 4170
    assert find_in_text(conn, "o que a Magalu fez?") is None
    assert resolve_empresa(conn, "vale")[0] == 4170
