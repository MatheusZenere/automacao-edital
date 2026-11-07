"""Leitura de arquivos de edital (PDF, DOCX, ODT) para texto."""
from pathlib import Path

# Abaixo disso (caracteres por página) o PDF é tratado como escaneado.
MIN_CHARS_POR_PAGINA = 100

EXTENSOES_SUPORTADAS = {".pdf", ".docx", ".odt"}


def ler_paginas_pdf(caminho: Path) -> tuple[list[str], bool]:
    """Retorna (texto de cada página, escaneado)."""
    import pymupdf

    with pymupdf.open(caminho) as doc:
        paginas = [p.get_text() for p in doc]
    total = sum(len(p.strip()) for p in paginas)
    escaneado = total / max(len(paginas), 1) < MIN_CHARS_POR_PAGINA
    return paginas, escaneado


def ler_pdf(caminho: Path) -> tuple[str, bool]:
    """Retorna (texto, escaneado)."""
    paginas, escaneado = ler_paginas_pdf(caminho)
    return "\n".join(paginas), escaneado


def ler_docx(caminho: Path) -> str:
    import docx

    d = docx.Document(str(caminho))
    partes = [p.text for p in d.paragraphs]
    for tabela in d.tables:
        for linha in tabela.rows:
            partes.append(" | ".join(c.text.strip() for c in linha.cells))
    return "\n".join(partes)


def ler_odt(caminho: Path) -> str:
    from odf import teletype
    from odf.opendocument import load
    from odf.text import H, P

    doc = load(str(caminho))
    partes = [teletype.extractText(e) for e in doc.getElementsByType(H) + doc.getElementsByType(P)]
    return "\n".join(partes)


def ler_arquivo(caminho: str | Path) -> tuple[str, bool]:
    """Lê um arquivo de edital. Retorna (texto, escaneado)."""
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    if ext not in EXTENSOES_SUPORTADAS:
        raise ValueError(f"Formato não suportado: {ext} ({caminho.name})")
    if ext == ".pdf":
        return ler_pdf(caminho)
    if ext == ".docx":
        return ler_docx(caminho), False
    return ler_odt(caminho), False
