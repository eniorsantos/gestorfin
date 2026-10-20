from finllm.rag.text import chunk_lines, chunk_text


def test_chunk_lines_repete_cabecalho_e_numera_partes():
    header = "Empresa: X | DFP | Valores em R$ mil"
    lines = [f"3.{i:02d} | Conta {i} | {i*1000}" for i in range(1, 80)]
    chunks = chunk_lines(header, lines, max_chars=600)
    assert len(chunks) > 1
    assert all(c.startswith(header) for c in chunks)
    assert all("Parte" in c.splitlines()[0] for c in chunks)
    assert sum(c.count("\n") for c in chunks) == len(lines)  # nenhuma linha perdida
    assert all(len(c) <= 600 + 60 for c in chunks)


def test_chunk_lines_unico_sem_parte():
    c = chunk_lines("H", ["a | b | 1"], 1000)
    assert c == ["H\na | b | 1"]


def test_chunk_text_respeita_limite():
    text = "\n\n".join(f"Parágrafo {i}. " + "texto " * 80 for i in range(20))
    chunks = chunk_text(text, max_chars=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert "Parágrafo 0" in chunks[0] and "Parágrafo 19" in chunks[-1]


def test_chunk_text_paragrafo_gigante():
    chunks = chunk_text("palavra " * 2000, max_chars=800, overlap=100)
    assert len(chunks) > 5 and all(len(c) <= 800 for c in chunks)
