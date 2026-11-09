"""Módulo de análise estruturada de editais e submissões de pesquisa.
Processa arquivos (PDFs, DOCX, imagens) informados pelo usuário via upload ou diretório,
classifica documentos, extrai metadados do projeto, analisa o mérito curricular,
valida a conformidade de documentos obrigatórios/faltantes e exporta via Pandas.
"""
from dataclasses import dataclass, field
import io
from pathlib import Path
import re
from typing import Any

import pandas as pd
import pymupdf

try:
    import docx
except ImportError:
    docx = None

# Só PDF/DOCX são lidos; acima deste tamanho o arquivo é listado mas não aberto (protege a memória)
EXTENSOES_ANALISADAS = {".pdf", ".docx"}
MAX_BYTES_ANALISE = 100 * 1024 * 1024


@dataclass
class CriterioMerito:
    item: str
    criterio: str
    valor_item: str
    maximo: str
    nota: str


@dataclass
class MembroProjeto:
    nome: str
    categoria: str
    ch_dedicada: str
    tipo_participacao: str
    cpf_mascarado: str = ""


@dataclass
class ArquivoProcessadoInfo:
    nome: str
    caminho: str
    extensao: str
    tamanho_kb: float
    num_paginas: int
    categoria: str
    descricao: str


@dataclass
class ProjetoEdital:
    pasta: str
    codigo: str
    titulo: str
    edital: str
    coordenador: str
    email_coordenador: str
    situacao: str
    cota_vigencia: str
    grande_area: str
    area: str
    subarea: str
    comite_etica: str
    resumo: str
    introducao: str
    metodologia: str
    resultados_esperados: str
    pontuacao_merito: float | None
    anexo_ii_nome: str | None
    tem_projeto_sigaa: bool
    tem_versao_tarja: bool
    tem_anexo_merito: bool
    tem_comprovantes: bool
    status_conformidade: str
    total_arquivos: int
    documentos_faltantes: list[str] = field(default_factory=list)
    documentos_entregues: list[str] = field(default_factory=list)
    membros: list[MembroProjeto] = field(default_factory=list)
    cronograma: list[dict[str, Any]] = field(default_factory=list)
    criterios_merito: list[CriterioMerito] = field(default_factory=list)
    arquivos: list[ArquivoProcessadoInfo] = field(default_factory=list)


def _texto_pdf(doc: pymupdf.Document) -> str:
    return "\n".join(p.get_text() for p in doc)


def _compactar(m: re.Match | None) -> str:
    """Primeiro grupo da busca com espaços/quebras normalizados ('' se não houve correspondência)."""
    return " ".join(m.group(1).split()) if m else ""


def _grupo(m: re.Match | None, padrao: str = "") -> str:
    """Primeiro grupo da busca sem espaços nas pontas (`padrao` se não houve correspondência)."""
    return m.group(1).strip() if m else padrao


def _numero(m: re.Match | None) -> float | None:
    """Primeiro grupo da busca como número ("12,5" vira 12.5); None se não houver."""
    try:
        return float(m.group(1).replace(",", ".")) if m else None
    except ValueError:
        return None


def _linhas(texto: str) -> list[str]:
    """Linhas não vazias, sem espaços nas pontas."""
    return [l.strip() for l in texto.split("\n") if l.strip()]


def mascarar_cpf(cpf: str) -> str:
    """Mascara o CPF para conformidade com a LGPD (ex: ***.456.789-**)."""
    cpf = cpf.strip()
    m = re.match(r"^(\d{3})\.(\d{3})\.(\d{3})-(\d{2})$", cpf)
    if m:
        return f"***.{m.group(2)}.{m.group(3)}-**"
    return "***"


def classificar_arquivo(nome: str, texto_inicial: str = "") -> tuple[str, str]:
    """Classifica o arquivo em categoria e descrição amigável a partir do nome e texto inicial."""
    nome_lower = nome.lower()
    texto_upper = texto_inicial.upper()
    ext = Path(nome).suffix.lower()

    if ext in [".jpg", ".jpeg", ".png"]:
        return "IMAGEM", "Figura / Imagem complementar"

    if "tarja" in nome_lower:
        return "PROJETO_TARJA", "Projeto de Pesquisa (Versão Tarjada / Avaliação às Cegas)"

    if any(k in nome_lower for k in ["anexo-ii", "anexo_ii", "merito", "pontua"]) or any(
        k in texto_upper for k in ["MÉRITO CURRICULAR", "ANALISE DE MERITO"]
    ):
        return "ANEXO_MERITO", "Anexo II - Formulário de Pontuação de Mérito Curricular"

    if any(k in nome_lower for k in ["certificado", "ceua", "comite"]):
        return "CERTIFICADO_ETICA", "Certificado de Comitê de Ética (CEUA / CEP)"

    if any(k in nome_lower for k in ["declara", "comprovante", "endosso", "carta"]):
        return "COMPROVANTE_DECLARACAO", "Comprovante / Declaração complementar"

    if "PROJETO DE PESQUISA" in texto_upper:  # cobre também "DADOS DO PROJETO DE PESQUISA"
        return "PROJETO_SIGAA", "Projeto de Pesquisa (Formulário SIGAA)"

    if ext in [".pdf", ".docx", ".odt"]:
        return "DOCUMENTO_ADICIONAL", "Documento / Anexo adicional do projeto"

    return "OUTROS", "Arquivo anexo"


def extrair_criterios_anexo_ii_stream(nome: str, conteudo: bytes) -> tuple[float | None, list[CriterioMerito]]:
    """Extrai nota total e critérios do Anexo II a partir de bytes (PDF ou DOCX)."""
    criterios: list[CriterioMerito] = []
    total: float | None = None
    ext = Path(nome).suffix.lower()

    if ext == ".docx" and docx is not None:
        try:
            doc = docx.Document(io.BytesIO(conteudo))
            for t in doc.tables:
                for row in t.rows:
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    if len(cells) >= 5 and cells[0].isdigit() and 1 <= int(cells[0]) <= 13:
                        criterios.append(
                            CriterioMerito(
                                item=cells[0],
                                criterio=cells[1],
                                valor_item=cells[2],
                                maximo=cells[3],
                                nota=cells[4],
                            )
                        )
                    elif len(cells) >= 2 and "TOTAL" in cells[0].upper():
                        valor = _numero(re.search(r"(\d+[\.,]?\d*)", " ".join(cells)))
                        if valor is not None:
                            total = valor
        except Exception:
            pass
        return total, criterios

    if ext == ".pdf":
        try:
            doc = pymupdf.open(stream=conteudo, filetype="pdf")
            texto = _texto_pdf(doc)

            total = _numero(re.search(r"TOTAL\s*[:\|]?\s*(\d+[\.,]?\d*)", texto, re.I))

            lines = _linhas(texto)
            i = 0
            while i < len(lines):
                if lines[i].isdigit() and 1 <= int(lines[i]) <= 13:
                    item_num = lines[i]
                    i += 1
                    desc_parts = []
                    while i < len(lines) and not (
                        lines[i].isdigit() and i + 2 < len(lines) and lines[i + 1].isdigit()
                    ):
                        desc_parts.append(lines[i])
                        i += 1
                    if i + 2 < len(lines):
                        valor = lines[i]
                        maximo = lines[i + 1]
                        nota = lines[i + 2]
                        i += 3
                        criterios.append(
                            CriterioMerito(
                                item=item_num,
                                criterio=" ".join(desc_parts),
                                valor_item=valor,
                                maximo=maximo,
                                nota=nota,
                            )
                        )
                    else:
                        break
                else:
                    i += 1
        except Exception:
            pass

    return total, criterios


def extrair_metadados_sigaa(doc: pymupdf.Document, identificador_padrao: str = "") -> dict[str, Any]:
    """Extrai informações cadastrais detalhadas do formulário SIGAA."""
    texto = _texto_pdf(doc)

    # Código
    m_cod = re.search(r"Código:\s*([A-Z0-9\-]+)", texto, re.I)
    codigo = m_cod.group(1).strip() if m_cod else ""
    if not codigo or codigo == "PVG":
        codigo = identificador_padrao.strip() or "PVG-Identificado"

    # Título
    m_tit = re.search(
        r"Titulo do Projeto:\s*(.*?)(?=\n(?:Tipo do Projeto|Natureza|Tipo de Pesquisa|Situação))",
        texto,
        re.S | re.I,
    )
    titulo = _compactar(m_tit)
    if not titulo:
        titulo = _compactar(re.search(r"Título:\s*(.*?)(?=\n(?:Resumo|Introdução|\d+\.))", texto, re.S | re.I))

    # Edital
    edital = _compactar(re.search(r"Edital:\s*(.*?)(?=\n(?:Cota|Objetivos|Área))", texto, re.S | re.I)) or "Não especificado"

    # Cota / Vigência
    cota = _compactar(re.search(r"Cota:\s*(.*?)(?=\n(?:Objetivos|Área|Grande Área))", texto, re.S | re.I))

    # Área de conhecimento
    grande_area = _grupo(re.search(r"Grande Área:\s*(.*?)(?=\n(?:Área:|Subárea:))", texto, re.I))
    area = _grupo(re.search(r"Área:\s*(.*?)(?=\n(?:Subárea:|Especialidade:|Grupo))", texto, re.I))
    subarea = _grupo(re.search(r"Subárea:\s*(.*?)(?=\n(?:Especialidade:|Grupo))", texto, re.I))

    # E-mail
    email = _grupo(re.search(r"E-mail:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", texto, re.I))

    # Situação
    situacao = _grupo(re.search(r"Situação do Projeto:\s*(.*?)(?=\n|$)", texto, re.I), "SUBMETIDO")

    # Comitê de ética
    comite_etica = _grupo(
        re.search(r"N° Protocolo:\s*(.*?)(?=\n(?:Corpo do Projeto|Resumo))", texto, re.I), "Não informado / Isento"
    )

    # Seções de texto
    resumo = _compactar(re.search(r"Resumo\s*(.*?)(?=\n(?:Palavras-chave|Introdução))", texto, re.S | re.I))
    introducao = _compactar(re.search(
        r"Introdução.*?\n(.*?)(?=\n(?:Procedimentos Metodológicos|Metodologia|Resultados))",
        texto,
        re.S | re.I,
    ))
    metodologia = _compactar(re.search(
        r"(?:Procedimentos Metodológicos|Metodologia).*?\n(.*?)(?=\n(?:Resultados Esperados|Referências|Cronograma))",
        texto,
        re.S | re.I,
    ))
    resultados = _compactar(re.search(
        r"Resultados Esperados.*?\n(.*?)(?=\n(?:Referências|Membros do Projeto|Cronograma))",
        texto,
        re.S | re.I,
    ))

    # Membros da equipe
    membros: list[MembroProjeto] = []
    coordenador = ""

    bloco_membros = re.search(
        r"Membros do Projeto.*?(?=Cronograma de Atividades|Histórico do Projeto)",
        texto,
        re.S | re.I,
    )
    if bloco_membros:
        linhas = _linhas(bloco_membros.group(0))
        idx = 0
        while idx < len(linhas):
            linha = linhas[idx]
            if re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", linha):
                cpf = linha
                nome = linhas[idx + 1] if idx + 1 < len(linhas) else ""
                cat = linhas[idx + 2] if idx + 2 < len(linhas) else ""
                ch_part = linhas[idx + 3] if idx + 3 < len(linhas) else ""
                idx += 4

                ch = ""
                tipo_part = ch_part
                m_ch = re.match(r"^(\d+)\s*(.*)$", ch_part)
                if m_ch:
                    ch = m_ch.group(1)
                    tipo_part = m_ch.group(2)

                membro = MembroProjeto(
                    nome=nome,
                    categoria=cat,
                    ch_dedicada=f"{ch}h" if ch else "",
                    tipo_participacao=tipo_part,
                    cpf_mascarado=mascarar_cpf(cpf),
                )
                membros.append(membro)
                if "COORDENADOR" in tipo_part.upper():
                    coordenador = nome
            else:
                idx += 1

    # Fallbacks para o Coordenador
    if not coordenador:
        coordenador = _grupo(re.search(r"Coordenador do Projeto:\s*(.*?)(?=\n|$)", texto, re.I))

    if not coordenador:
        m_hist = re.search(
            r"(?:SUBMETIDO|CADASTRO EM ANDAMENTO)\s*\n([A-Z\s]+)\s*\(([a-z0-9._]+)\)",
            texto,
            re.I,
        )
        if m_hist:
            coordenador = m_hist.group(1).strip()
            if not email:
                email = f"{m_hist.group(2).strip()}@ifc.edu.br"

    # Cronograma
    cronograma: list[dict[str, Any]] = []
    bloco_crono = re.search(
        r"Cronograma de Atividades.*?(?=Histórico do Projeto|\n\s*Rua das Missões)",
        texto,
        re.S | re.I,
    )
    if bloco_crono:
        for l in _linhas(bloco_crono.group(0)):
            if len(l) > 15 and not any(k in l.upper() for k in ["CRONOGRAMA", "ATIVIDADE", "2026", "MAR", "ABR", "HISTÓRICO"]):
                if not l.startswith("X") and not l.startswith(" "):
                    cronograma.append({"atividade": l})

    return {
        "codigo": codigo,
        "titulo": titulo,
        "edital": edital,
        "coordenador": coordenador,
        "email_coordenador": email,
        "situacao": situacao,
        "cota_vigencia": cota,
        "grande_area": grande_area,
        "area": area,
        "subarea": subarea,
        "comite_etica": comite_etica,
        "resumo": resumo,
        "introducao": introducao,
        "metodologia": metodologia,
        "resultados_esperados": resultados,
        "membros": membros,
        "cronograma": cronograma,
    }


def analisar_arquivos_submissao(
    arquivos: list[tuple[str, bytes]], identificador_padrao: str = "", tamanhos: dict[str, int] | None = None
) -> ProjetoEdital:
    """Analisa um conjunto de arquivos (nome, bytes) informados pelo usuário.
    Detecta projeto principal, tarja, mérito e determina documentos faltantes.
    `tamanhos` informa o tamanho real dos arquivos passados sem conteúdo.
    """
    tamanhos = tamanhos or {}
    arquivos_info: list[ArquivoProcessadoInfo] = []
    sigaa_bytes: tuple[str, bytes] | None = None
    tarja_bytes: tuple[str, bytes] | None = None
    anexo_ii_bytes: tuple[str, bytes] | None = None
    tem_comprovantes = False

    # Primeiro passe: varre arquivos e identifica tipos
    for nome, conteudo in arquivos:
        ext = Path(nome).suffix.lower()
        tamanho_kb = round(tamanhos.get(nome, len(conteudo)) / 1024, 1)
        num_paginas = 1
        texto_inicial = ""

        if ext == ".pdf":
            try:
                doc = pymupdf.open(stream=conteudo, filetype="pdf")
                num_paginas = len(doc)
                if num_paginas > 0:
                    texto_inicial = doc[0].get_text()[:400]
            except Exception:
                pass
        elif ext == ".docx" and docx is not None:
            try:
                doc = docx.Document(io.BytesIO(conteudo))
                texto_inicial = "\n".join(p.text for p in doc.paragraphs[:5])
            except Exception:
                pass

        categoria, descricao = classificar_arquivo(nome, texto_inicial)

        if categoria == "PROJETO_TARJA":
            tarja_bytes = (nome, conteudo)
        elif categoria == "ANEXO_MERITO" and not anexo_ii_bytes:
            anexo_ii_bytes = (nome, conteudo)
        elif categoria == "PROJETO_SIGAA" and not sigaa_bytes:
            sigaa_bytes = (nome, conteudo)
        elif categoria in ["CERTIFICADO_ETICA", "COMPROVANTE_DECLARACAO"]:
            tem_comprovantes = True

        arquivos_info.append(
            ArquivoProcessadoInfo(
                nome=nome,
                caminho=nome,
                extensao=ext,
                tamanho_kb=tamanho_kb,
                num_paginas=num_paginas,
                categoria=categoria,
                descricao=descricao,
            )
        )

    # Se não achou SIGAA categorizado explicitamente, pega o primeiro PDF que não seja tarja nem anexo
    if not sigaa_bytes:
        for nome, conteudo in arquivos:
            ext = Path(nome).suffix.lower()
            if ext == ".pdf" and "_tarja" not in nome.lower() and "anexo" not in nome.lower() and "merito" not in nome.lower():
                sigaa_bytes = (nome, conteudo)
                # Atualiza na lista de arquivos
                for a in arquivos_info:
                    if a.nome == nome:
                        a.categoria = "PROJETO_SIGAA"
                        a.descricao = "Projeto de Pesquisa Principal"
                break

    # Extrai metadados do projeto principal
    if sigaa_bytes:
        try:
            doc = pymupdf.open(stream=sigaa_bytes[1], filetype="pdf")
            dados_projeto = extrair_metadados_sigaa(doc, identificador_padrao)
        except Exception:
            dados_projeto = _dados_projeto_vazio(identificador_padrao)
    else:
        dados_projeto = _dados_projeto_vazio(identificador_padrao)

    # Análise do Anexo II (Formulário de Mérito Curricular)
    pontuacao_merito: float | None = None
    criterios_merito: list[CriterioMerito] = []
    anexo_ii_nome: str | None = None

    if anexo_ii_bytes:
        anexo_ii_nome = anexo_ii_bytes[0]
        pontuacao_merito, criterios_merito = extrair_criterios_anexo_ii_stream(
            anexo_ii_bytes[0], anexo_ii_bytes[1]
        )
        if not dados_projeto["coordenador"] or dados_projeto["coordenador"] == "Não identificado":
            m_c = re.search(r"MERITO-CURRICULAR[_\-]([A-Za-z_]+)\.", anexo_ii_bytes[0], re.I)
            if m_c:
                dados_projeto["coordenador"] = m_c.group(1).replace("_", " ").title()

    # Validação e Checagem de Documentos Faltantes: (arquivo, texto se entregue, texto se faltar)
    obrigatorios = [
        (
            sigaa_bytes,
            "Projeto de Pesquisa Principal (SIGAA)",
            "Projeto de Pesquisa Principal (Formulário SIGAA contendo dados da proposta, objetivos, equipe e cronograma)",
        ),
        (
            tarja_bytes,
            "Versão Tarjada do Projeto (Avaliação às Cegas)",
            "Versão Tarjada do Projeto (Exigência para avaliação às cegas - sem identificação dos autores)",
        ),
        (
            anexo_ii_bytes,
            "Anexo II - Formulário de Pontuação de Mérito Curricular",
            "Anexo II (Formulário de Pontuação de Mérito Curricular / Lattes preenchido)",
        ),
    ]
    documentos_entregues = [f"{entregue}: {arq[0]}" for arq, entregue, _ in obrigatorios if arq]
    documentos_faltantes = [faltando for arq, _, faltando in obrigatorios if not arq]

    if tem_comprovantes:
        documentos_entregues.append("Comprovantes / Declarações / Certificado de Ética anexados")

    if not documentos_faltantes:
        status_conf = "Completo"
    else:
        status_conf = f"Incompleto (Faltam {len(documentos_faltantes)} documento(s))"

    # As chaves de dados_projeto têm os mesmos nomes dos campos de ProjetoEdital
    return ProjetoEdital(
        pasta=identificador_padrao or dados_projeto["codigo"],
        **dados_projeto,
        pontuacao_merito=pontuacao_merito,
        anexo_ii_nome=anexo_ii_nome,
        tem_projeto_sigaa=sigaa_bytes is not None,
        tem_versao_tarja=tarja_bytes is not None,
        tem_anexo_merito=anexo_ii_bytes is not None,
        tem_comprovantes=tem_comprovantes,
        status_conformidade=status_conf,
        total_arquivos=len(arquivos_info),
        documentos_faltantes=documentos_faltantes,
        documentos_entregues=documentos_entregues,
        criterios_merito=criterios_merito,
        arquivos=arquivos_info,
    )


def _dados_projeto_vazio(identificador_padrao: str = "") -> dict[str, Any]:
    return {
        "codigo": identificador_padrao or "Não identificado",
        "titulo": "Não identificado",
        "edital": "Não especificado",
        "coordenador": "Não identificado",
        "email_coordenador": "",
        "situacao": "PENDENTE",
        "cota_vigencia": "",
        "grande_area": "",
        "area": "",
        "subarea": "",
        "comite_etica": "Não informado",
        "resumo": "",
        "introducao": "",
        "metodologia": "",
        "resultados_esperados": "",
        "membros": [],
        "cronograma": [],
    }


def analisar_pasta_pvg(pvg_dir: Path) -> ProjetoEdital:
    """Compatibilidade: lê os arquivos de um diretório e chama analisar_arquivos_submissao."""
    arquivos: list[tuple[str, bytes]] = []
    tamanhos: dict[str, int] = {}
    for f in sorted(list(pvg_dir.iterdir()), key=lambda x: x.name):
        if f.is_file():
            tamanho = f.stat().st_size
            ler = f.suffix.lower() in EXTENSOES_ANALISADAS and tamanho <= MAX_BYTES_ANALISE
            arquivos.append((f.name, f.read_bytes() if ler else b""))
            tamanhos[f.name] = tamanho
    return analisar_arquivos_submissao(arquivos, identificador_padrao=pvg_dir.name.strip(), tamanhos=tamanhos)


def analisar_todos_editais(diretorio_base: str | Path) -> list[ProjetoEdital]:
    """Varre todas as pastas PVG em diretorio_base."""
    caminho = Path(diretorio_base)
    if not caminho.exists() or not caminho.is_dir():
        return []

    projetos: list[ProjetoEdital] = []
    pastas = sorted([d for d in caminho.iterdir() if d.is_dir()], key=lambda d: d.name)
    for pvg_dir in pastas:
        try:
            proj = analisar_pasta_pvg(pvg_dir)
            projetos.append(proj)
        except Exception as e:
            print(f"Erro ao processar {pvg_dir.name}: {e}")
    return projetos


def _linha_membro(m: MembroProjeto) -> dict[str, str]:
    return {
        "Nome": m.nome,
        "Categoria": m.categoria,
        "Carga Horária": m.ch_dedicada,
        "Participação": m.tipo_participacao,
        "CPF (LGPD)": m.cpf_mascarado,
    }


def gerar_dataframe_submissao(projeto: ProjetoEdital) -> dict[str, pd.DataFrame]:
    """Gera DataFrames consolidados para exportação CSV de uma submissão individual."""
    # 1. Resumo da Submissão (Metadados + Conformidade)
    faltantes_txt = " | ".join(projeto.documentos_faltantes) if projeto.documentos_faltantes else "Nenhum (Tudo certo)"
    entregues_txt = " | ".join(projeto.documentos_entregues)
    arquivos_txt = " | ".join(f"{a.nome} ({a.descricao})" for a in projeto.arquivos)
    membros_txt = " | ".join(f"{m.nome} ({m.categoria}, {m.ch_dedicada})" for m in projeto.membros)

    df_detalhes = pd.DataFrame(
        [
            {
                "Código": projeto.codigo,
                "Título do Projeto": projeto.titulo,
                "Edital de Referência": projeto.edital,
                "Coordenador": projeto.coordenador,
                "E-mail": projeto.email_coordenador,
                "Situação": projeto.situacao,
                "Grande Área": projeto.grande_area,
                "Área": projeto.area,
                "Subárea": projeto.subarea,
                "Vigência / Cota": projeto.cota_vigencia,
                "Comitê de Ética": projeto.comite_etica,
                "Status Geral": projeto.status_conformidade,
                "Documentos Faltantes": faltantes_txt,
                "Documentos Entregues": entregues_txt,
                "Arquivos Anexados": arquivos_txt,
                "Total de Arquivos": projeto.total_arquivos,
                "Pontuação Mérito Curricular": (
                    projeto.pontuacao_merito if projeto.pontuacao_merito is not None else "Não informado"
                ),
                "Equipe": membros_txt,
            }
        ]
    )

    # 2. Arquivos Anexados
    df_arquivos = pd.DataFrame(
        [
            {
                "Arquivo": a.nome,
                "Tipo / Descrição": a.descricao,
                "Extensão": a.extensao,
                "Tamanho (KB)": a.tamanho_kb,
                "Páginas": a.num_paginas,
            }
            for a in projeto.arquivos
        ]
    )

    # 3. Equipe
    df_equipe = pd.DataFrame([_linha_membro(m) for m in projeto.membros])

    # 4. Critérios de Mérito
    df_merito = pd.DataFrame(
        [
            {
                "Item": c.item,
                "Critério": c.criterio,
                "Valor Unitário": c.valor_item,
                "Pontuação Máxima": c.maximo,
                "Nota Declarada": c.nota,
            }
            for c in projeto.criterios_merito
        ]
    )

    return {
        "detalhes": df_detalhes,
        "arquivos": df_arquivos,
        "equipe": df_equipe,
        "merito": df_merito,
    }


def gerar_dataframes(projetos: list[ProjetoEdital]) -> dict[str, pd.DataFrame]:
    """Gera DataFrames com o resumo consolidado de todos os projetos analisados."""
    linhas_resumo = []
    for p in projetos:
        linhas_resumo.append(
            {
                "Código": p.codigo,
                "Título": p.titulo,
                "Coordenador": p.coordenador,
                "E-mail": p.email_coordenador,
                "Grande Área": p.grande_area,
                "Área": p.area,
                "Edital": p.edital,
                "Total Arquivos": p.total_arquivos,
                "Possui Tarja": "Sim" if p.tem_versao_tarja else "Não",
                "Possui Mérito (Anexo II)": "Sim" if p.tem_anexo_merito else "Não",
                "Pontos Mérito": p.pontuacao_merito if p.pontuacao_merito is not None else "N/A",
                "Comprovantes / CEUA": "Sim" if p.tem_comprovantes else "Não",
                "Status Conformidade": p.status_conformidade,
                "Documentos Faltantes": " | ".join(p.documentos_faltantes) if p.documentos_faltantes else "Nenhum",
            }
        )
    df_resumo = pd.DataFrame(linhas_resumo)

    linhas_arquivos = []
    for p in projetos:
        for a in p.arquivos:
            linhas_arquivos.append(
                {
                    "Código": p.codigo,
                    "Arquivo": a.nome,
                    "Categoria": a.categoria,
                    "Descrição": a.descricao,
                    "Tamanho (KB)": a.tamanho_kb,
                    "Páginas": a.num_paginas,
                    "Extensão": a.extensao,
                }
            )
    df_arquivos = pd.DataFrame(linhas_arquivos)

    linhas_membros = []
    for p in projetos:
        for m in p.membros:
            linhas_membros.append({"Código": p.codigo, "Título Projeto": p.titulo, **_linha_membro(m)})
    df_membros = pd.DataFrame(linhas_membros)

    return {
        "resumo": df_resumo,
        "arquivos": df_arquivos,
        "membros": df_membros,
    }

