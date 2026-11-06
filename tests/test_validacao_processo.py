from pathlib import Path

from src.leitura import ler_arquivo
from src.processo import processar
from src.relatorio_edital import para_markdown, salvar
from src.schemas import ExigenciaLLM, ExtracaoLLM, InfoEdital
from src.validacao import normalizar, trecho_existe

from .test_leitura import EDITAL_14, requer

TEXTO = "5.1 As inscrições deverão ser realizadas\nvia manifestação de interesse enca-\nminhada através de e-mail."


def test_trecho_literal_aceito_mesmo_com_quebras_e_hifenizacao():
    assert trecho_existe("As inscrições deverão ser realizadas via manifestação de interesse encaminhada", TEXTO)


def test_trecho_inventado_rejeitado():
    assert not trecho_existe("Apresentar certidão de nascimento autenticada", TEXTO)


def test_trecho_curto_rejeitado():
    assert not trecho_existe("5.1", TEXTO)


def test_normalizar_ignora_caixa_e_espacos():
    assert normalizar("  Olá   MUNDO\n") == "olá mundo"


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


@requer(EDITAL_14)
def test_processar_marca_verificado_e_inventado():
    cl = processar([EDITAL_14], _extrator_falso)
    assert [e.id for e in cl.exigencias] == ["E001", "E002"]
    assert cl.exigencias[0].verificado is True
    assert cl.exigencias[1].verificado is False
    assert cl.exigencias[0].arquivo == EDITAL_14.name


@requer(EDITAL_14)
def test_processar_varios_arquivos_ids_sequenciais():
    cl = processar([EDITAL_14, EDITAL_14], _extrator_falso)
    assert [e.id for e in cl.exigencias] == ["E001", "E002", "E003", "E004"]
    assert len(cl.arquivos) == 2


@requer(EDITAL_14)
def test_markdown_alerta_nao_verificadas_e_salvar(tmp_path):
    cl = processar([EDITAL_14], _extrator_falso)
    md = para_markdown(cl)
    assert "Comprovante de matrícula" in md
    assert "1 exigência(s) com trecho não confirmado" in md
    js, mdp = salvar(cl, tmp_path)
    assert Path(js).exists() and Path(mdp).exists()


@requer(EDITAL_14)
def test_texto_do_edital_real_contem_trechos_esperados():
    """Garante que a validação funciona contra a extração real de PDF (quebras de linha do layout)."""
    texto, _ = ler_arquivo(EDITAL_14)
    assert trecho_existe("Não possuir mais de três reprovações em disciplinas caso o curso seja de Graduação", texto)
