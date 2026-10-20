"""OCR para PDFs escaneados (roadmap Fase 8).

Tenta extrair texto com PyMuPDF; se o PDF for escaneado (sem texto),
disponibiliza OCR via pytesseract (opcional). Retorna o texto extraído
ou um aviso de que OCR não está disponível.
"""
from __future__ import annotations

from io import BytesIO


def _fitz():
    import fitz  # pymupdf (dependência direta do projeto)
    return fitz


def tem_texto(pdf_bytes: bytes) -> bool:
    """Verifica se o PDF contém texto extraível."""
    try:
        fitz = _fitz()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for pagina in doc:
                if pagina.get_text().strip():
                    return True
    except Exception:
        return False
    return False


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrai texto de um PDF. Se escaneado e OCR disponível, aplica OCR."""
    texto = ""
    try:
        fitz = _fitz()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            texto = "\n\n".join(pagina.get_text() for pagina in doc)
    except Exception:
        texto = ""

    if texto.strip():
        return texto

    # PDF escaneado: tenta OCR
    return _ocr_pdf(pdf_bytes)


def _ocr_pdf(pdf_bytes: bytes) -> str:
    """Aplica OCR página por página se pytesseract estiver instalado."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return (
            "[OCR não disponível] O PDF parece ser escaneado e não contém texto extraível. "
            "Instale pytesseract + tesseract-ocr para habilitar OCR (roadmap Fase 8)."
        )

    partes = []
    try:
        fitz = _fitz()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for i, pagina in enumerate(doc):
                pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(BytesIO(pix.tobytes("png")))
                texto_pagina = pytesseract.image_to_string(img, lang="por")
                partes.append(f"--- Página {i + 1} ---\n{texto_pagina}")
    except Exception as e:  # noqa: BLE001
        return f"[Erro no OCR] {e}"
    return "\n\n".join(partes)
