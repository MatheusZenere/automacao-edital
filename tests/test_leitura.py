from pathlib import Path

import pytest

from src.leitura import ler_arquivo

RAIZ = Path(__file__).resolve().parent.parent
EDITAIS = RAIZ / "editais"
EDITAL_77 = EDITAIS / "EDITAL-No-77-2026-ASSEG-GABI.pdf"
EDITAL_14 = EDITAIS / "editalExemplo" / "Edital_14-2022_Seleo_de_Bolsistas_Oficinas_4.0_-_Vaga_Remanescente.pdf"
ANEXO_II = EDITAIS / "editalExemplo" / "Anexo-II-Carta-de-Intencao.odt"


def requer(*arquivos: Path):
    """Pula o teste se os documentos reais (não versionados, por conterem dados pessoais) não existirem."""
    return pytest.mark.skipif(
        not all(a.exists() for a in arquivos), reason="documento de exemplo ausente (pasta editais/ não versionada)"
    )


@requer(EDITAL_77)
def test_pdf_com_texto_nao_e_escaneado():
    texto, escaneado = ler_arquivo(EDITAL_77)
    assert not escaneado
    assert "Art. 6º" in texto
    assert "Mapa de Tempo de Serviço" in texto


@requer(EDITAL_14)
def test_pdf_edital_14_numeracao_diferente():
    texto, escaneado = ler_arquivo(EDITAL_14)
    assert not escaneado
    assert "5.1" in texto and "Comprovante de matrícula" in texto


@requer(ANEXO_II)
def test_odt_real():
    texto, escaneado = ler_arquivo(ANEXO_II)
    assert not escaneado
    assert len(texto.strip()) > 20


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
    import fitz

    doc = fitz.open()
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
