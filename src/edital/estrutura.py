"""Estrutura do edital sem IA: seções, cronograma, documentos citados e requisitos.

As seções são reconhecidas pelo título (ex.: "DO CRONOGRAMA", "DA SUBMISSÃO DO PROJETO"),
não pelo número, porque a numeração muda de um edital para outro.
"""
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import re

from .leitura import ler_paginas_pdf

MESES = "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"

# Temas procurados no título das seções
TEMA_CRONOGRAMA = re.compile(r"CRONOGRAMA", re.I)
TEMA_SUBMISSAO = re.compile(r"SUBMISS|INSCRI", re.I)
TEMA_REQUISITOS = re.compile(r"REQUISIT", re.I)

_TITULO_SECAO = re.compile(r"^(\d{1,2})\.?\s+(\S.*)$")
_ITEM = re.compile(r"^(\d{1,2}(?:\.\d{1,2})+)\.?\s+(.*)$")
# Início de inciso/alínea/parágrafo: força quebra de parágrafo ao juntar linhas
_MARCADOR = re.compile(r"^([IVXLC]+\s*[-–]|[a-z]\)|§\s*\d+|Parágrafo único)")
_INICIO_DATA = re.compile(
    rf"^(até\b|a partir\b|do dia\b|no dia\b|em \d|\d{{1,2}}\s*[º°]?\s+de\s+({MESES})\b|\d{{1,2}}/\d{{1,2}})",
    re.I,
)
_ANEXO = re.compile(r"\(\s*ANEXO\s+([IVXL]+)\s*\)")
_UNIDADE = re.compile(r"^(COORDENAÇÃO|PRÓ-REITORIA|PRO-REITORIA|DIRETORIA|DEPARTAMENTO|GABINETE)\b", re.I)


@dataclass
class ItemEdital:
    numero: str  # "7.1"; vazio para o texto antes do primeiro item da seção
    paragrafos: list[str] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "\n".join(self.paragrafos)


@dataclass
class SecaoEdital:
    numero: int
    titulo: str
    itens: list[ItemEdital] = field(default_factory=list)
    linhas: list[str] = field(default_factory=list, repr=False)  # texto bruto, usado em tabelas


@dataclass
class LinhaCronograma:
    atividade: str
    data: str


@dataclass
class DocumentoCitado:
    anexo: str  # "II"
    descricao: str
    itens: list[str] = field(default_factory=list)  # onde é citado, ex.: ["11.1.2", "11.2.2"]
    na_submissao: bool = False


@dataclass
class EditalEstruturado:
    arquivo: str
    numero: str
    titulo: str
    unidade: str
    data_publicacao: str
    contato: str
    paginas: int
    escaneado: bool
    secoes: list[SecaoEdital] = field(default_factory=list)
    cronograma: list[LinhaCronograma] = field(default_factory=list)
    documentos: list[DocumentoCitado] = field(default_factory=list)

    def secoes_do_tema(self, tema: re.Pattern) -> list[SecaoEdital]:
        return [s for s in self.secoes if tema.search(s.titulo)]

    @property
    def prazo_submissao(self) -> str:
        for linha in self.cronograma:
            if TEMA_SUBMISSAO.search(linha.atividade):
                return linha.data
        return ""


def encontrar_edital(pasta: Path) -> Path | None:
    """PDF solto na raiz da pasta (ao lado das subpastas dos projetos).

    Com vários PDFs na raiz, prefere o que tem "edital" no nome; empate, o maior arquivo.
    """
    if not pasta.is_dir():
        return None
    pdfs = [f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() == ".pdf" and not f.name.startswith(".")]
    if not pdfs:
        return None
    return max(pdfs, key=lambda f: ("edital" in f.name.lower(), f.stat().st_size))


def analisar_edital(caminho: Path) -> EditalEstruturado:
    paginas, escaneado = ler_paginas_pdf(caminho)
    edital = estruturar_edital(paginas, arquivo=caminho.name)
    edital.escaneado = escaneado
    return edital


def estruturar_edital(paginas: list[str], arquivo: str = "") -> EditalEstruturado:
    linhas = _limpar_linhas(paginas)
    inicio_secoes, secoes = _separar_secoes(linhas)
    preambulo = linhas[:inicio_secoes]
    texto = "\n".join(linhas)

    m_num = re.search(r"EDITAL\s+N[º°o.]*\s*(\d+)\s*/\s*(\d{4})", texto, re.I)
    m_data = re.search(rf"\b(\d{{1,2}}\s+de\s+(?:{MESES})\s+de\s+\d{{4}})", "\n".join(preambulo), re.I)
    m_email = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", texto)
    unidade, titulo = _titulo_e_unidade(preambulo)

    edital = EditalEstruturado(
        arquivo=arquivo,
        numero=f"{m_num.group(1)}/{m_num.group(2)}" if m_num else "",
        titulo=titulo,
        unidade=unidade,
        data_publicacao=m_data.group(1) if m_data else "",
        contato=m_email.group(0) if m_email else "",
        paginas=len(paginas),
        escaneado=False,
        secoes=secoes,
    )
    edital.cronograma = _extrair_cronograma(edital.secoes_do_tema(TEMA_CRONOGRAMA))
    edital.documentos = _extrair_documentos(secoes)
    return edital


# --- etapas internas -------------------------------------------------------------------------


def _limpar_linhas(paginas: list[str]) -> list[str]:
    """Junta as páginas sem cabeçalhos/rodapés repetidos (data de impressão, URL, "3/18")."""
    por_pagina = [[l.strip() for l in p.splitlines()] for p in paginas]
    repetidas: set[str] = set()
    if len(paginas) >= 3:
        contagem = Counter(l for pag in por_pagina for l in set(pag) if l)
        repetidas = {l for l, n in contagem.items() if n >= len(paginas) / 2}
    return [
        l for pag in por_pagina for l in pag
        if l and l not in repetidas and not re.fullmatch(r"\d{1,3}\s*/\s*\d{1,3}", l)
    ]


def _maiusculo(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return len(letras) >= 2 and sum(c.isupper() for c in letras) / len(letras) >= 0.8


def _separar_secoes(linhas: list[str]) -> tuple[int, list[SecaoEdital]]:
    """Seções = linhas "N TÍTULO EM MAIÚSCULAS" com N crescente de 1 em 1."""
    secoes: list[SecaoEdital] = []
    corpos: list[list[str]] = []
    inicio = len(linhas)
    i = 0
    while i < len(linhas):
        m = _TITULO_SECAO.match(linhas[i])
        esperado = secoes[-1].numero + 1 if secoes else None
        if m and _maiusculo(m.group(2)) and (esperado is None or int(m.group(1)) == esperado):
            titulo = m.group(2)
            # título quebrado em duas linhas ("... DOS MEMBROS DO" / "PROJETO")
            while i + 1 < len(linhas) and _maiusculo(linhas[i + 1]) and not linhas[i + 1][0].isdigit():
                i += 1
                titulo += " " + linhas[i]
            if not secoes:
                inicio = i
            secoes.append(SecaoEdital(numero=int(m.group(1)), titulo=" ".join(titulo.split())))
            corpos.append([])
        elif corpos:
            corpos[-1].append(linhas[i])
        i += 1

    for secao, corpo in zip(secoes, corpos):
        secao.linhas = corpo
        secao.itens = _separar_itens(corpo)
    return inicio, secoes


def _separar_itens(linhas: list[str]) -> list[ItemEdital]:
    itens: list[ItemEdital] = []
    atual: tuple[str, list[str]] = ("", [])
    for linha in linhas:
        m = _ITEM.match(linha)
        if m:
            if atual[1]:
                itens.append(ItemEdital(atual[0], _reflow(atual[1])))
            atual = (m.group(1), [m.group(2)])
        else:
            atual[1].append(linha)
    if atual[1]:
        itens.append(ItemEdital(atual[0], _reflow(atual[1])))
    return itens


def _reflow(linhas: list[str]) -> list[str]:
    """Junta as linhas quebradas pelo PDF, mantendo incisos e alíneas como parágrafos."""
    paragrafos: list[str] = []
    for linha in linhas:
        if paragrafos and not _MARCADOR.match(linha):
            paragrafos[-1] += " " + linha
        else:
            paragrafos.append(linha)
    return [" ".join(p.split()) for p in paragrafos]


def _titulo_e_unidade(preambulo: list[str]) -> tuple[str, str]:
    """Título = bloco em maiúsculas logo após a linha "EDITAL Nº x/aaaa"."""
    pos = max((i for i, l in enumerate(preambulo) if re.match(r"EDITAL\s+N", l, re.I)), default=-1)
    unidade, titulo = "", []
    for linha in preambulo[pos + 1:]:
        if not _maiusculo(linha):
            break
        if not titulo and not unidade and _UNIDADE.match(linha):
            unidade = linha
        else:
            titulo.append(linha)
    return unidade, " ".join(titulo)


def _extrair_cronograma(secoes: list[SecaoEdital]) -> list[LinhaCronograma]:
    """Lê a tabela atividade/data da seção de cronograma.

    Uma data começa por "Até", "A partir", "10 de dezembro"... e continua nas linhas seguintes
    que começam com minúscula, dígito ou parêntese; o resto é texto da atividade.
    """
    if not secoes:
        return []
    tabela = secoes[0].linhas
    cab = next((i for i, l in enumerate(tabela) if l.lower() in ("data", "datas", "prazo", "prazos", "período")), None)
    if cab is None:
        return []

    resultado: list[LinhaCronograma] = []
    atividade: list[str] = []
    data: list[str] = []
    for linha in tabela[cab + 1:]:
        if _ITEM.match(linha) or linha.lower().startswith("quadro"):
            break
        continua_data = data and (linha[0].islower() or linha[0].isdigit() or linha[0] == "(")
        if continua_data:
            data.append(linha)
        elif atividade and not data and _INICIO_DATA.match(linha):
            data.append(linha)
        else:
            if atividade and data:
                resultado.append(LinhaCronograma(" ".join(atividade), " ".join(data)))
                atividade, data = [], []
            atividade.append(linha)
    if atividade and data:
        resultado.append(LinhaCronograma(" ".join(atividade), " ".join(data)))
    return resultado


def _extrair_documentos(secoes: list[SecaoEdital]) -> list[DocumentoCitado]:
    """Anexos citados como "Nome do documento (ANEXO II)", agrupados pelo número do anexo."""
    por_anexo: dict[str, DocumentoCitado] = {}
    for secao in secoes:
        na_submissao = bool(TEMA_SUBMISSAO.search(secao.titulo))
        for item in secao.itens:
            for paragrafo in item.paragrafos:
                for m in _ANEXO.finditer(paragrafo):
                    trecho = re.split(r"[:;]", paragrafo[: m.start()])[-1]
                    descricao = _MARCADOR.sub("", trecho.strip()).strip(" -–")
                    doc = por_anexo.setdefault(m.group(1), DocumentoCitado(anexo=m.group(1), descricao=descricao))
                    if descricao and (not doc.descricao or len(descricao) < len(doc.descricao)):
                        doc.descricao = descricao
                    ref = item.numero or str(secao.numero)
                    if ref not in doc.itens:
                        doc.itens.append(ref)
                    doc.na_submissao = doc.na_submissao or na_submissao
    return sorted(por_anexo.values(), key=lambda d: _romano(d.anexo))


def _romano(valor: str) -> int:
    numeros = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for atual, seguinte in zip(valor, valor[1:] + " "):
        n = numeros.get(atual, 0)
        total += -n if numeros.get(seguinte, 0) > n else n
    return total
