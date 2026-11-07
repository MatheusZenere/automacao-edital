import pytest

from src.edital.leitura import ler_arquivo


def test_docx_gerado(tmp_path):
    import docx

    d = docx.Document()
    d.add_paragraph("Art. 1º Apresentar comprovante de residência.")
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "Etapa"
    t.rows[0].cells[1].text = "10/01/2030"
    caminho = tmp_path / "x.docx"
    d.save(caminho)

    texto, escaneado = ler_arquivo(caminho)
    assert not escaneado
    assert "comprovante de residência" in texto
    assert "Etapa | 10/01/2030" in texto


def test_pdf_escaneado_detectado(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()  # página sem texto = simula escaneado
    caminho = tmp_path / "scan.pdf"
    doc.save(caminho)
    doc.close()

    _, escaneado = ler_arquivo(caminho)
    assert escaneado


def test_formato_nao_suportado(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        ler_arquivo(f)
