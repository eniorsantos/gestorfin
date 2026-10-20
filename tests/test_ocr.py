"""Testes do OCR (Fase 8)."""
from finllm.ocr import tem_texto, extrair_texto_pdf


def test_tem_texto_vazio():
    assert tem_texto(b"") is False


def test_extrair_texto_pdf_sem_pdf():
    # Não é um PDF válido; não deve quebrar
    resultado = extrair_texto_pdf(b"nao e um pdf")
    assert isinstance(resultado, str)
