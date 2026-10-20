from finllm.rag.guardrails import numbers_in, parse_number, validate_numbers


def test_parse_ptbr():
    assert parse_number("1.234.567") == 1234567
    assert parse_number("1.234,56") == 1234.56
    assert parse_number("-12,5") == -12.5
    assert parse_number("1234.56") == 1234.56


def test_valida_numero_presente_e_ausente():
    ctx = ["3.01 | Receita | 511.994.000\n3.11 | Lucro | 124.461.000"]
    assert validate_numbers("A receita foi 511.994.000 em 2023 [1].", ctx).ok
    v = validate_numbers("A receita foi 600.000.000.", ctx)
    assert not v.ok and v.unsupported == [600000000.0]


def test_ignora_anos_e_inteiros_pequenos_mas_nao_valores_grandes():
    ctx = ["x | 1.000"]
    assert validate_numbers("No 2º trimestre de 2024, 3 empresas [1]", ctx).ok
    assert not validate_numbers("Foram 4.500", ctx).ok


def test_numbers_in_ignora_citacoes():
    assert numbers_in("valor 1.000 [12]") == [1000.0]
