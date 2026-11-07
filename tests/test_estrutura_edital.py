"""Testes da estruturação do edital sem IA (texto sintético, sem depender do PDF real)."""
from src.edital.estrutura import (
    TEMA_REQUISITOS,
    TEMA_SUBMISSAO,
    encontrar_edital,
    estruturar_edital,
)

RODAPE = "05/12/2025, 16:12\nsig.ifc.edu.br/documento?id=1\n{n}/3\n"

PAGINAS = [
    """MINISTÉRIO DA EDUCAÇÃO
INSTITUTO FEDERAL CATARINENSE
Araquari-SC, 05 de dezembro de 2025.
EDITAL Nº 7/2026
COORDENAÇÃO DE PESQUISA E INOVAÇÃO - Campus ARAQUARI
SELEÇÃO DE PROJETOS DE PESQUISA PARA
EXECUÇÃO EM 2026
O Diretor-Geral torna público o Edital.
1 DO OBJETIVO
1.1 Selecionar projetos.
2 DOS REQUISITOS DO
COORDENADOR
2.1 São requisitos para atuação como coordenador:
I - ser servidor
ativo;
II - possuir diploma de graduação.
""" + RODAPE.format(n=1),
    """3 DO CRONOGRAMA
3.1 Este Edital é regido pelo Quadro 1.
Atividades
Data
Lançamento do Edital
5 de dezembro de 2025
Período de submissão dos
projetos
Do dia 10 de dezembro de 2025 até o dia 8 de
fevereiro de 2026
Entrega da documentação
Até 27 de fevereiro de 2026 (demais meses,
até o dia 10 de cada mês)
""" + RODAPE.format(n=2),
    """4 DA SUBMISSÃO
4.1 O proponente deverá enviar para contato@ifc.edu.br:
a) Projeto de Pesquisa (ANEXO I);
b) Formulário de Pontuação do Lattes preenchido (ANEXO II).
5 DA IMPLANTAÇÃO
5.1 Os contemplados deverão encaminhar:
I - Plano de Trabalho do bolsista (ANEXO IV);
II - nova via do Formulário do Lattes (ANEXO II).
""" + RODAPE.format(n=3),
]


def test_cabecalho_do_edital():
    e = estruturar_edital(PAGINAS, arquivo="edital.pdf")
    assert e.numero == "7/2026"
    assert e.titulo == "SELEÇÃO DE PROJETOS DE PESQUISA PARA EXECUÇÃO EM 2026"
    assert e.unidade.startswith("COORDENAÇÃO DE PESQUISA")
    assert e.data_publicacao == "05 de dezembro de 2025"
    assert e.contato == "contato@ifc.edu.br"
    assert e.paginas == 3


def test_secoes_por_titulo_sem_rodape():
    e = estruturar_edital(PAGINAS)
    assert [s.titulo for s in e.secoes] == [
        "DO OBJETIVO",
        "DOS REQUISITOS DO COORDENADOR",  # título quebrado em duas linhas
        "DO CRONOGRAMA",
        "DA SUBMISSÃO",
        "DA IMPLANTAÇÃO",
    ]
    texto = " ".join(p for s in e.secoes for i in s.itens for p in i.paragrafos)
    assert "16:12" not in texto and "sig.ifc" not in texto


def test_tema_independe_do_numero_da_secao():
    e = estruturar_edital(PAGINAS)
    assert [s.numero for s in e.secoes_do_tema(TEMA_SUBMISSAO)] == [4]
    assert [s.numero for s in e.secoes_do_tema(TEMA_REQUISITOS)] == [2]


def test_incisos_viram_paragrafos():
    e = estruturar_edital(PAGINAS)
    item = e.secoes_do_tema(TEMA_REQUISITOS)[0].itens[0]
    assert item.numero == "2.1"
    assert item.paragrafos == [
        "São requisitos para atuação como coordenador:",
        "I - ser servidor ativo;",
        "II - possuir diploma de graduação.",
    ]


def test_cronograma_com_quebras_de_linha():
    e = estruturar_edital(PAGINAS)
    assert [(c.atividade, c.data) for c in e.cronograma] == [
        ("Lançamento do Edital", "5 de dezembro de 2025"),
        ("Período de submissão dos projetos", "Do dia 10 de dezembro de 2025 até o dia 8 de fevereiro de 2026"),
        ("Entrega da documentação", "Até 27 de fevereiro de 2026 (demais meses, até o dia 10 de cada mês)"),
    ]
    assert e.prazo_submissao.startswith("Do dia 10 de dezembro")


def test_documentos_citados_agrupados_por_anexo():
    e = estruturar_edital(PAGINAS)
    docs = {d.anexo: d for d in e.documentos}
    assert list(docs) == ["I", "II", "IV"]
    assert docs["I"].descricao == "Projeto de Pesquisa"
    assert docs["II"].itens == ["4.1", "5.1"]
    assert docs["II"].na_submissao and docs["I"].na_submissao
    assert not docs["IV"].na_submissao


def test_edital_sem_secoes_reconhecidas_nao_quebra():
    e = estruturar_edital(["texto livre sem estrutura"])
    assert e.secoes == [] and e.cronograma == [] and e.documentos == []


def test_encontrar_edital_na_raiz(tmp_path):
    (tmp_path / "PVG1").mkdir()
    (tmp_path / "PVG1" / "projeto.pdf").write_bytes(b"x")
    assert encontrar_edital(tmp_path) is None
    (tmp_path / "anexo.pdf").write_bytes(b"x" * 10)
    (tmp_path / "EDITAL-13-2025.pdf").write_bytes(b"x")
    assert encontrar_edital(tmp_path).name == "EDITAL-13-2025.pdf"
