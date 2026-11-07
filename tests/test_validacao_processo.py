from pathlib import Path

import docx
import pytest

from src.edital.processo import processar
from src.edital.relatorio_edital import para_markdown, salvar
from src.edital.schemas import ExigenciaLLM, ExtracaoLLM, InfoEdital
from src.edital.validacao import normalizar, trecho_existe

TEXTO = "5.1 As inscrições deverão ser realizadas\nvia manifestação de interesse enca-\nminhada através de e-mail."


def test_trecho_literal_aceito_mesmo_com_quebras_e_hifenizacao():
    assert trecho_existe("As inscrições deverão ser realizadas via manifestação de interesse encaminhada", TEXTO)


def test_trecho_inventado_rejeitado():
    assert not trecho_existe("Apresentar certidão de nascimento autenticada", TEXTO)


def test_trecho_curto_rejeitado():
    assert not trecho_existe("5.1", TEXTO)


def test_normalizar_ignora_caixa_e_espacos():
    assert normalizar("  Olá   MUNDO\n") == "olá mundo"


@pytest.fixture
def edital_14(tmp_path):
    """Edital sintético em DOCX (os documentos reais não são versionados)."""
    d = docx.Document()
    d.add_paragraph("5.1 a) Comprovante de matrícula do aluno no semestre corrente.")
    caminho = tmp_path / "edital_14.docx"
    d.save(caminho)
    return caminho


def _extrator_falso(texto, arquivo, caminho, escaneado):
    """Simula o Gemini: uma exigência real (copiada do PDF) e uma inventada."""
    return ExtracaoLLM(
        info=InfoEdital(titulo="Edital teste", numero="14/2022"),
        exigencias=[
            ExigenciaLLM(
                referencia="5.1 a",
                categoria="documento",
                descricao="Comprovante de matrícula",
                obrigatoria=True,
                trecho_original="Comprovante de matrícula do aluno no semestre corrente",
            ),
            ExigenciaLLM(
                referencia="9.9",
                categoria="documento",
                descricao="Exigência inventada",
                obrigatoria=True,
                trecho_original="Apresentar certidão de nascimento autenticada em cartório",
            ),
        ],
    )


def test_processar_marca_verificado_e_inventado(edital_14):
    cl = processar([edital_14], _extrator_falso)
    assert [e.id for e in cl.exigencias] == ["E001", "E002"]
    assert cl.exigencias[0].verificado is True
    assert cl.exigencias[1].verificado is False
    assert cl.exigencias[0].arquivo == edital_14.name


def test_processar_varios_arquivos_ids_sequenciais(edital_14):
    cl = processar([edital_14, edital_14], _extrator_falso)
    assert [e.id for e in cl.exigencias] == ["E001", "E002", "E003", "E004"]
    assert len(cl.arquivos) == 2


def test_markdown_alerta_nao_verificadas_e_salvar(edital_14, tmp_path):
    cl = processar([edital_14], _extrator_falso)
    md = para_markdown(cl)
    assert "Comprovante de matrícula" in md
    assert "1 exigência(s) com trecho não confirmado" in md
    js, mdp = salvar(cl, tmp_path)
    assert Path(js).exists() and Path(mdp).exists()
