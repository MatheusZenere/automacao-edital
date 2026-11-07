"""Cruzamento sem IA entre as exigências do edital e os arquivos de cada submissão.

Cada anexo exigido na etapa de submissão é ligado às categorias de arquivo do verificador
pela descrição do anexo (ex.: "Formulário de Pontuação do Lattes"), não pelo número,
porque a numeração dos anexos muda de um edital para outro.
"""
from dataclasses import dataclass, field
import re

import pandas as pd

from src.edital.estrutura import DocumentoCitado, EditalEstruturado
from src.submissoes.analise_editais import ArquivoProcessadoInfo

ENTREGUE = "Entregue"
FALTANDO = "Faltando"
VERIFICAR = "Verificar manualmente"

# Descrição do anexo -> categorias de arquivo que o atendem. A primeira regra que casar vale.
REGRAS: list[tuple[re.Pattern, set[str]]] = [
    (re.compile(r"lattes|pontua[çc][ãa]o|m[ée]rito", re.I), {"ANEXO_MERITO"}),
    # "Projeto de Pesquisa", mas não "Dados complementares do projeto de pesquisa"
    (re.compile(r"^\s*projeto\s+de\s+pesquisa\b", re.I), {"PROJETO_SIGAA", "PROJETO_TARJA"}),
]


@dataclass
class ItemConformidade:
    anexo: str
    documento: str
    situacao: str
    itens_edital: list[str] = field(default_factory=list)
    arquivos: list[str] = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        return f"Anexo {self.anexo} - {self.documento}"


def exigencias_da_submissao(edital: EditalEstruturado | None) -> list[DocumentoCitado]:
    """Anexos exigidos na submissão. Vazio quando não há edital ou ele não foi reconhecido."""
    if edital is None or edital.escaneado:
        return []
    return [d for d in edital.documentos if d.na_submissao]


def _categorias(documento: DocumentoCitado) -> set[str] | None:
    for padrao, categorias in REGRAS:
        if padrao.search(documento.descricao):
            return categorias
    return None


def verificar_submissao(
    edital: EditalEstruturado | None, arquivos: list[ArquivoProcessadoInfo]
) -> list[ItemConformidade]:
    resultado: list[ItemConformidade] = []
    for doc in exigencias_da_submissao(edital):
        categorias = _categorias(doc)
        if categorias is None:
            situacao, encontrados = VERIFICAR, []
        else:
            encontrados = [a.nome for a in arquivos if a.categoria in categorias]
            situacao = ENTREGUE if encontrados else FALTANDO
        resultado.append(ItemConformidade(doc.anexo, doc.descricao, situacao, list(doc.itens), encontrados))
    return resultado


def pendencias(itens: list[ItemConformidade]) -> list[ItemConformidade]:
    return [i for i in itens if i.situacao == FALTANDO]


def tabela_conformidade(por_projeto: dict[str, list[ItemConformidade]]) -> pd.DataFrame:
    """Uma linha por projeto e uma coluna por anexo exigido."""
    linhas = []
    for codigo, itens in por_projeto.items():
        linha = {"Projeto": codigo}
        linha.update({i.rotulo: i.situacao for i in itens})
        linha["Pendências"] = len(pendencias(itens))
        linhas.append(linha)
    return pd.DataFrame(linhas)
