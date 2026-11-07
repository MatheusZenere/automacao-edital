"""Testes do cruzamento edital x submissão (sem documentos reais)."""
from src.conformidade import (
    ENTREGUE,
    FALTANDO,
    VERIFICAR,
    exigencias_da_submissao,
    tabela_conformidade,
    verificar_submissao,
)
from src.edital.estrutura import DocumentoCitado, EditalEstruturado
from src.submissoes.analise_editais import ArquivoProcessadoInfo


def _edital(*documentos: DocumentoCitado) -> EditalEstruturado:
    return EditalEstruturado(
        arquivo="edital.pdf", numero="7/2026", titulo="", unidade="", data_publicacao="",
        contato="", paginas=3, escaneado=False, documentos=list(documentos),
    )


def _arquivo(nome: str, categoria: str) -> ArquivoProcessadoInfo:
    return ArquivoProcessadoInfo(nome, nome, ".pdf", 10.0, 1, categoria, "")


PROJETO = DocumentoCitado("I", "Projeto de Pesquisa", ["4.1"], na_submissao=True)
LATTES = DocumentoCitado("II", "Formulário de Pontuação do Lattes preenchido", ["4.1"], na_submissao=True)
COMPLEMENTARES = DocumentoCitado("III", "Dados complementares do projeto de pesquisa", ["13.3"])
PLANO = DocumentoCitado("IV", "Plano de Trabalho do bolsista", ["5.1"])


def test_so_entram_os_anexos_da_etapa_de_submissao():
    edital = _edital(PROJETO, LATTES, COMPLEMENTARES, PLANO)
    assert [d.anexo for d in exigencias_da_submissao(edital)] == ["I", "II"]


def test_sem_edital_ou_sem_anexos_nao_ha_exigencias():
    assert exigencias_da_submissao(None) == []
    assert exigencias_da_submissao(_edital(PLANO)) == []
    escaneado = _edital(PROJETO)
    escaneado.escaneado = True
    assert exigencias_da_submissao(escaneado) == []


def test_submissao_completa():
    edital = _edital(PROJETO, LATTES)
    arquivos = [_arquivo("projeto.pdf", "PROJETO_SIGAA"), _arquivo("anexo-ii.pdf", "ANEXO_MERITO")]
    itens = verificar_submissao(edital, arquivos)
    assert [(i.anexo, i.situacao) for i in itens] == [("I", ENTREGUE), ("II", ENTREGUE)]
    assert itens[1].arquivos == ["anexo-ii.pdf"]
    assert itens[1].itens_edital == ["4.1"]


def test_versao_tarjada_tambem_vale_como_projeto():
    itens = verificar_submissao(_edital(PROJETO), [_arquivo("p_tarja.pdf", "PROJETO_TARJA")])
    assert itens[0].situacao == ENTREGUE


def test_anexo_faltando():
    itens = verificar_submissao(_edital(PROJETO, LATTES), [_arquivo("projeto.pdf", "PROJETO_SIGAA")])
    assert itens[1].situacao == FALTANDO
    assert itens[1].arquivos == []


def test_documento_sem_regra_vai_para_revisao_humana():
    declaracao = DocumentoCitado("V", "Declaração de anuência da chefia", ["4.1"], na_submissao=True)
    itens = verificar_submissao(_edital(declaracao), [_arquivo("x.pdf", "COMPROVANTE_DECLARACAO")])
    assert itens[0].situacao == VERIFICAR


def test_tabela_conformidade_uma_coluna_por_anexo():
    edital = _edital(PROJETO, LATTES)
    por_projeto = {
        "PVG1": verificar_submissao(edital, [_arquivo("a.pdf", "PROJETO_SIGAA")]),
        "PVG2": verificar_submissao(edital, [_arquivo("a.pdf", "PROJETO_SIGAA"), _arquivo("b.pdf", "ANEXO_MERITO")]),
    }
    df = tabela_conformidade(por_projeto)
    assert list(df.columns) == ["Projeto", "Anexo I - Projeto de Pesquisa",
                                "Anexo II - Formulário de Pontuação do Lattes preenchido", "Pendências"]
    assert df.loc[0, "Pendências"] == 1
    assert df.loc[1, "Pendências"] == 0
    assert df.loc[0, "Anexo II - Formulário de Pontuação do Lattes preenchido"] == FALTANDO
