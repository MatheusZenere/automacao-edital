"""Interface Web Streamlit para Análise e Verificação de Editais e Submissões.
Permite que o usuário utilize o seu próprio Google Drive através de:
1. Link ou ID compartilhado do Google Drive (download e sincronização automática).
2. Upload direto do arquivo compactado (.zip) baixado da pasta do Google Drive.
"""
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

import pandas as pd
import streamlit as st

# Configurações do layout da página com ícone nativo
st.set_page_config(
    page_title="Verificador de Editais & Submissões",
    page_icon=":material/fact_check:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Caminho base do projeto
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.analise_editais import (
    ProjetoEdital,
    analisar_todos_editais,
    gerar_dataframe_submissao,
    gerar_dataframes,
)
from src.drive_sync import (
    ErroDrivePersonalizado,
    baixar_pasta_drive_compartilhada,
    detectar_raiz_submissoes,
    extrair_zip_submissoes,
)

PASTA_CACHE_RAIZ = BASE_DIR / "downloads_drive"

# Cada sessão (aba do navegador) usa a sua própria pasta: usuários diferentes não se misturam.
if "sid" not in st.session_state:
    st.session_state["sid"] = uuid.uuid4().hex
    # Remove dados de sessões antigas (> 24h) para não acumular documentos pessoais no disco
    if PASTA_CACHE_RAIZ.exists():
        for _antiga in PASTA_CACHE_RAIZ.iterdir():
            if _antiga.is_dir() and time.time() - _antiga.stat().st_mtime > 24 * 3600:
                shutil.rmtree(_antiga, ignore_errors=True)
PASTA_CACHE_DOWNLOADS = PASTA_CACHE_RAIZ / st.session_state["sid"]


def esc(valor) -> str:
    """Escapa markdown/HTML de textos vindos dos documentos (evita imagens/links injetados)."""
    return re.sub(r"([\\`*_{}\[\]()#+!<>|~$:&-])", r"\\\1", str(valor or ""))


def csv_seguro(df: pd.DataFrame) -> bytes:
    """CSV sem risco de injeção de fórmulas (=, +, -, @) ao abrir no Excel/Planilhas."""
    def _limpa(v):
        if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + v
        return v
    return df.map(_limpa).to_csv(index=False).encode("utf-8-sig")


def assinatura_pasta(pasta: Path) -> tuple:
    """Identifica o conteúdo atual da pasta (invalida o cache quando ele muda)."""
    arqs = [f for f in pasta.rglob("*") if f.is_file()]
    return (len(arqs), sum(f.stat().st_size for f in arqs), max((f.stat().st_mtime_ns for f in arqs), default=0))

# --- FUNÇÃO DE CARREGAMENTO CACHEADA ---
@st.cache_data(show_spinner="Analisando subpastas de editais e anexos...")
def carregar_projetos(caminho_pasta: str, _assinatura: tuple) -> list[ProjetoEdital]:
    p = Path(caminho_pasta)
    if not p.exists() or not p.is_dir():
        return []
    return analisar_todos_editais(p)


# --- CABEÇALHO ---
st.title("Verificador de Editais e Submissões", icon=":material/fact_check:")
st.caption(
    "Conferência automatizada de documentos exigidos, mérito curricular e dados cadastrais, "
    "a partir da pasta do seu Google Drive."
)

col_menu, col_main = st.columns([1, 2.6], gap="large")
pasta_para_analisar: Path | None = None

# --- COLUNA ESQUERDA: ORIGEM DOS DADOS E MENU DE PROJETOS ---
with col_menu:
    with st.container(border=True):
        st.markdown("##### :material/cloud_sync: Origem dos dados")
        opcao_link = "Link do Drive"
        opcao_zip = "Arquivo ZIP"
        metodo_conexao = st.segmented_control(
            "Método",
            [opcao_link, opcao_zip],
            default=opcao_link,
            label_visibility="collapsed",
        ) or opcao_link

        if metodo_conexao == opcao_link:
            st.caption(
                "Compartilhe a pasta no Drive como **Qualquer pessoa com o link** (Leitor) e cole o link abaixo."
            )
            link_drive = st.text_input(
                "Link ou ID da pasta",
                placeholder="https://drive.google.com/drive/folders/1ABC...",
            )
            if st.button("Baixar e sincronizar", icon=":material/cloud_download:", width="stretch", type="primary"):
                if link_drive.strip():
                    try:
                        barra = st.progress(0.0, text="Listando arquivos da pasta...")

                        def _atualizar(feitos: int, total: int) -> None:
                            barra.progress(feitos / total if total else 1.0, text=f"Baixando arquivos: {feitos}/{total}")

                        pasta_dest = PASTA_CACHE_DOWNLOADS / "drive_compartilhado"
                        pasta_baixada, _fid = baixar_pasta_drive_compartilhada(
                            link_drive, pasta_dest, progresso=_atualizar
                        )
                        barra.empty()
                        st.session_state["pasta_drive_baixada"] = str(pasta_baixada)
                        st.session_state.pop("pasta_zip_extraida", None)
                        st.success("Pasta sincronizada.", icon=":material/check_circle:")
                    except ErroDrivePersonalizado as e:
                        st.error(f"**Não foi possível carregar a pasta.**\n\n{e}", icon=":material/error:")
                    except Exception:
                        st.error(
                            "**Algo deu errado ao baixar a pasta.**\n\n"
                            "Tente novamente. Se persistir, baixe a pasta pelo Drive (botão direito > Fazer download) "
                            "e use a opção Arquivo ZIP.",
                            icon=":material/error:",
                        )
                else:
                    st.warning("Cole o link ou ID da pasta antes de continuar.", icon=":material/warning:")

            if "pasta_drive_baixada" in st.session_state:
                p_baixada = Path(st.session_state["pasta_drive_baixada"])
                if p_baixada.exists():
                    pasta_para_analisar = p_baixada
        else:
            st.caption("No Drive, clique com o botão direito na pasta > **Fazer download** e envie o `.zip` abaixo.")
            zip_enviado = st.file_uploader("Arquivo .zip", type=["zip"], label_visibility="collapsed")
            if zip_enviado is not None:
                try:
                    with st.spinner("Descompactando e indexando submissões..."):
                        pasta_dest = PASTA_CACHE_DOWNLOADS / "zip_extraido"
                        pasta_para_analisar = extrair_zip_submissoes(
                            zip_enviado.getvalue(), pasta_dest, nome_arquivo=zip_enviado.name
                        )
                        st.session_state["pasta_zip_extraida"] = str(pasta_para_analisar)
                        st.session_state.pop("pasta_drive_baixada", None)
                except ErroDrivePersonalizado as e:
                    st.error(f"**Não foi possível usar esse arquivo.**\n\n{e}", icon=":material/error:")
                except Exception:
                    st.error(
                        "**Algo deu errado ao abrir o arquivo.**\n\n"
                        "Confira se o download foi concluído e envie novamente.",
                        icon=":material/error:",
                    )
            elif "pasta_zip_extraida" in st.session_state:
                p_zip = Path(st.session_state["pasta_zip_extraida"])
                if p_zip.exists():
                    pasta_para_analisar = p_zip

        if st.button("Limpar dados", icon=":material/refresh:", width="stretch"):
            st.cache_data.clear()
            shutil.rmtree(PASTA_CACHE_DOWNLOADS, ignore_errors=True)
            st.session_state.pop("pasta_drive_baixada", None)
            st.session_state.pop("pasta_zip_extraida", None)
            st.rerun()

    todos_projetos: list[ProjetoEdital] = []
    proj_sel: ProjetoEdital | None = None
    if pasta_para_analisar and pasta_para_analisar.exists():
        todos_projetos = carregar_projetos(str(pasta_para_analisar), assinatura_pasta(pasta_para_analisar))

    if todos_projetos:
        with st.container(border=True):
            st.markdown(f"##### :material/list_alt: Submissões ({len(todos_projetos)})")
            busca = st.text_input(
                "Buscar", placeholder="Buscar por código, título ou coordenador", label_visibility="collapsed"
            ).strip().lower()
            filtrados = [
                p for p in todos_projetos
                if not busca or busca in f"{p.codigo} {p.titulo} {p.coordenador or ''}".lower()
            ]
            if filtrados:
                por_codigo = {p.codigo: p for p in filtrados}

                def _rotulo(codigo: str) -> str:
                    p = por_codigo[codigo]
                    icone = ":green[:material/check_circle:]" if not p.documentos_faltantes else ":red[:material/error:]"
                    titulo = esc(p.titulo if len(p.titulo) <= 42 else p.titulo[:42] + "…")
                    return f"{icone} **{esc(p.codigo)}** · {titulo}"

                with st.container(height=480, border=False):
                    codigo_sel = st.radio(
                        "Submissão",
                        options=list(por_codigo.keys()),
                        format_func=_rotulo,
                        label_visibility="collapsed",
                    )
                proj_sel = por_codigo[codigo_sel]
            else:
                st.info("Nenhum resultado para a busca.", icon=":material/search_off:")

# --- COLUNA DIREITA: CONTEÚDO ---
with col_main:
    if not pasta_para_analisar or not pasta_para_analisar.exists():
        st.info("Para começar, carregue a pasta de editais no painel à esquerda.", icon=":material/info:")
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown(
                    "**Link compartilhado**  \nNo Google Drive, clique com o botão direito na pasta > **Compartilhar** > "
                    "**Qualquer pessoa com o link** e cole o link no painel."
                )
        with c2:
            with st.container(border=True):
                st.markdown(
                    "**Arquivo ZIP**  \nClique com o botão direito na pasta > **Fazer download** e envie "
                    "o arquivo `.zip` gerado no painel."
                )
        st.stop()

    if not todos_projetos:
        st.error("Nenhuma subpasta com editais ou projetos foi identificada.", icon=":material/error:")
        st.markdown(
            """
            **Possíveis causas:**
            1. **Estrutura de pastas**: a pasta principal deve conter uma subpasta por edital/projeto (ex.: `PVG2904-2025/`).
            2. **Arquivos ausentes**: cada subpasta precisa dos arquivos em PDF ou DOCX.
            3. **Download incompleto**: tente baixar a pasta como `.zip` e use a opção Arquivo ZIP.
            """
        )
        st.stop()

    if proj_sel is None:
        st.stop()

    st.caption(f":material/folder: Pasta ativa: `{pasta_para_analisar.name.replace(chr(96), "")}` · {len(todos_projetos)} submissão(ões)")

    # Gera DataFrames para exportação
    dfs_sel = gerar_dataframe_submissao(proj_sel)
    df_detalhes = dfs_sel["detalhes"]
    df_arquivos = dfs_sel["arquivos"]
    df_equipe = dfs_sel["equipe"]
    df_merito = dfs_sel["merito"]

    st.markdown("---")

    # --- DIAGNÓSTICO DE CONFORMIDADE E DOCUMENTOS FALTANTES ---
    if not proj_sel.documentos_faltantes:
        st.success(
            f"**Tudo Certo! Documentação Completa** — Foram analisados **{proj_sel.total_arquivos} arquivo(s)** nesta pasta e todos os documentos obrigatórios exigidos pelo edital estão presentes.",
            icon=":material/verified:",
        )
    else:
        st.error(
            f"**Atenção: Submissão Incompleta! Faltam {len(proj_sel.documentos_faltantes)} documento(s) obrigatório(s):**",
            icon=":material/warning:",
        )
        for doc in proj_sel.documentos_faltantes:
            st.markdown(f":material/cancel: **{doc}**")

    # --- BOTÕES DE DOWNLOAD DO CSV CONSOLIDADO ---
    st.markdown("### :material/download: Download do Relatório Consolidado")
    col_dl1, col_dl2, col_dl3 = st.columns([2, 1, 1])

    with col_dl1:
        csv_detalhes = csv_seguro(df_detalhes)
        st.download_button(
            label=f"Baixar Relatório do Projeto ({proj_sel.codigo}) em CSV",
            data=csv_detalhes,
            file_name=f"relatorio_edital_{proj_sel.codigo}.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
        )

    with col_dl2:
        if not df_merito.empty:
            csv_merito = csv_seguro(df_merito)
            st.download_button(
                label="Baixar Mérito Curricular (CSV)",
                data=csv_merito,
                file_name=f"merito_curricular_{proj_sel.codigo}.csv",
                mime="text/csv",
                icon=":material/table_chart:",
                width="stretch",
            )

    with col_dl3:
        dfs_todos = gerar_dataframes(todos_projetos)
        csv_todos = csv_seguro(dfs_todos["resumo"])
        st.download_button(
            label=f"Baixar Resumo de Todos ({len(todos_projetos)}) em CSV",
            data=csv_todos,
            file_name="resumo_geral_submissoes_drive.csv",
            mime="text/csv",
            icon=":material/dataset:",
            width="stretch",
            help="Baixa a planilha com o resumo de todas as submissões encontradas no Drive.",
        )

    st.markdown("---")

    # --- CARTÃO DE IDENTIFICAÇÃO DO PROJETO ---
    st.subheader(f"{esc(proj_sel.codigo)}: {esc(proj_sel.titulo)}")
    if proj_sel.documentos_faltantes:
        st.badge(f"{len(proj_sel.documentos_faltantes)} pendência(s)", icon=":material/error:", color="red")
    else:
        st.badge("Documentação completa", icon=":material/check_circle:", color="green")

    col_meta1, col_meta2, col_meta3 = st.columns(3)
    with col_meta1:
        st.write(f"**Coordenador(a):** {esc(proj_sel.coordenador)}")
        st.write(f"**E-mail:** {esc(proj_sel.email_coordenador) or 'Não informado'}")
        st.write(f"**Edital:** {esc(proj_sel.edital)}")
    with col_meta2:
        st.write(f"**Grande Área:** {esc(proj_sel.grande_area) or 'Não especificada'}")
        st.write(f"**Área:** {esc(proj_sel.area) or 'Não especificada'}")
        st.write(f"**Subárea:** {esc(proj_sel.subarea) or 'Não especificada'}")
    with col_meta3:
        st.write(f"**Vigência / Cota:** {esc(proj_sel.cota_vigencia) or 'Padrão do Edital'}")
        st.write(f"**Comitê de Ética:** {esc(proj_sel.comite_etica)}")
        st.write(
            f"**Pontuação de Mérito:** {proj_sel.pontuacao_merito if proj_sel.pontuacao_merito is not None else 'Pendente (Não informado)'}"
        )

    st.markdown("---")

    # --- ABAS DETALHADAS COM ÍCONES MATERIAL ---
    tab_resumo, tab_anexos, tab_merito, tab_equipe, tab_crono = st.tabs(
        [
            ":material/article: Resumo e Proposta",
            ":material/attach_file: Arquivos e Checklist",
            ":material/military_tech: Mérito Curricular (Anexo II)",
            ":material/group: Equipe do Projeto",
            ":material/calendar_month: Cronograma de Atividades",
        ]
    )

    # 1. ABA RESUMO E PROPOSTA
    with tab_resumo:
        if proj_sel.resumo:
            st.markdown("#### :material/description: Resumo do Projeto")
            st.info(esc(proj_sel.resumo), icon=":material/info:")
        else:
            st.warning("Resumo não identificado no documento principal.", icon=":material/warning:")

        if proj_sel.introducao:
            with st.expander("Introdução e Justificativa", expanded=False, icon=":material/menu_book:"):
                st.write(esc(proj_sel.introducao))

        if proj_sel.metodologia:
            with st.expander("Procedimentos Metodológicos", expanded=False, icon=":material/science:"):
                st.write(esc(proj_sel.metodologia))

        if proj_sel.resultados_esperados:
            with st.expander("Resultados Esperados", expanded=False, icon=":material/flag:"):
                st.write(esc(proj_sel.resultados_esperados))

    # 2. ABA ARQUIVOS E CHECKLIST
    with tab_anexos:
        st.markdown("#### :material/folder_open: Arquivos na Pasta e Análise de Conformidade")
        st.write(f"A pasta contém **{len(proj_sel.arquivos)}** arquivo(s) analisado(s):")
        st.dataframe(df_arquivos, width="stretch", hide_index=True)

        st.markdown("#### :material/fact_check: Checklist de Exigências do Edital")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Projeto SIGAA",
            "Entregue" if proj_sel.tem_projeto_sigaa else "Faltando",
            delta="Obrigatório",
            delta_color="normal" if proj_sel.tem_projeto_sigaa else "inverse",
        )
        c2.metric(
            "Versão Tarjada",
            "Entregue" if proj_sel.tem_versao_tarja else "Faltando",
            delta="Avaliação às Cegas",
            delta_color="normal" if proj_sel.tem_versao_tarja else "inverse",
        )
        c3.metric(
            "Anexo II (Mérito)",
            "Entregue" if proj_sel.tem_anexo_merito else "Faltando",
            delta="Pontuação Lattes",
            delta_color="normal" if proj_sel.tem_anexo_merito else "inverse",
        )
        c4.metric(
            "Comprovantes / Ética",
            "Anexado" if proj_sel.tem_comprovantes else "Não anexado",
            delta="Conforme Edital",
        )

    # 3. ABA MÉRITO CURRICULAR (ANEXO II)
    with tab_merito:
        st.markdown("#### :material/military_tech: Formulário de Pontuação de Mérito Curricular (Anexo II)")
        if proj_sel.tem_anexo_merito:
            st.success(
                f"Arquivo identificado: **`{str(proj_sel.anexo_ii_nome).replace(chr(96), "")}`** | Pontuação Total Declarada: **{proj_sel.pontuacao_merito} pontos**",
                icon=":material/task_alt:",
            )
            if not df_merito.empty:
                st.dataframe(df_merito, width="stretch", hide_index=True)
            else:
                st.info("Os critérios tabulares não puderam ser discriminados automaticamente.", icon=":material/info:")
        else:
            st.error(
                "Anexo II (Formulário de Mérito Curricular) NÃO encontrado nos arquivos desta pasta!",
                icon=":material/cancel:",
            )
            st.markdown(
                """
                O candidato não anexou a planilha ou formulário de mérito curricular.  
                Isso inviabiliza a conferência de pontuação do currículo Lattes para a classificação.
                """
            )

    # 4. ABA EQUIPE DO PROJETO
    with tab_equipe:
        st.markdown("#### :material/group: Membros Participantes do Projeto")
        if not df_equipe.empty:
            st.dataframe(df_equipe, width="stretch", hide_index=True)
            st.caption(":material/lock: CPFs anonimizados com máscara em conformidade com a LGPD.")
        else:
            st.info("Nenhum membro listado no formulário principal.", icon=":material/info:")

    # 5. ABA CRONOGRAMA
    with tab_crono:
        st.markdown("#### :material/calendar_month: Cronograma de Atividades")
        if proj_sel.cronograma:
            crono_df = pd.DataFrame([{"Atividade": item.get("atividade", "")} for item in proj_sel.cronograma])
            st.dataframe(crono_df, width="stretch", hide_index=True)
        else:
            st.info("Cronograma não discriminado no formulário padrão.", icon=":material/info:")
