"""Testes unitários para o módulo de análise de editais e submissões."""
import pytest

from src.config import PASTA_EDITAIS as PASTA_EDITAIS_RAIZ
from src.submissoes.analise_editais import (
    analisar_arquivos_submissao,
    analisar_pasta_pvg,
    extrair_criterios_anexo_ii_stream,
    gerar_dataframe_submissao,
    mascarar_cpf,
)

PASTA_EDITAIS = PASTA_EDITAIS_RAIZ / "ProjetosPesquisaAutomacao"

# Os documentos reais não são versionados (dados pessoais): sem eles, esses testes são pulados.
requer_editais = pytest.mark.skipif(
    not PASTA_EDITAIS.exists(), reason="documentos de exemplo ausentes (pasta editais/ fora do repositório)"
)


def test_mascarar_cpf_lgpd():
    assert mascarar_cpf("123.456.789-09") == "***.456.789-**"
    assert mascarar_cpf("123.456.789-00") == "***.456.789-**"
    assert mascarar_cpf("invalido") == "***"


@requer_editais
def test_analisar_arquivos_submissao_completo():
    pvg2904 = PASTA_EDITAIS / "PVG2904-2025"
    if not pvg2904.exists():
        pytest.skip("Pasta PVG2904-2025 não encontrada.")

    arquivos = [(f.name, f.read_bytes()) for f in pvg2904.iterdir() if f.is_file()]
    projeto = analisar_arquivos_submissao(arquivos, identificador_padrao="PVG2904-2025")

    assert projeto.codigo == "PVG2904-2025"
    assert "MICROBIOTA ORAL" in projeto.titulo
    assert projeto.coordenador == "MARCELLA ZAMPOLI DE ASSIS"
    assert projeto.tem_versao_tarja is True
    assert projeto.tem_anexo_merito is True
    assert projeto.pontuacao_merito == 84.0
    assert len(projeto.documentos_faltantes) == 0
    assert projeto.status_conformidade == "Completo"
    assert len(projeto.membros) >= 5
    assert len(projeto.criterios_merito) == 13


@requer_editais
def test_analisar_arquivos_submissao_faltando_merito():
    pvg2909 = PASTA_EDITAIS / "PVG2909-2025"
    if not pvg2909.exists():
        pytest.skip("Pasta PVG2909-2025 não encontrada.")

    arquivos = [(f.name, f.read_bytes()) for f in pvg2909.iterdir() if f.is_file()]
    projeto = analisar_arquivos_submissao(arquivos, identificador_padrao="PVG2909-2025")

    assert projeto.codigo == "PVG2909-2025"
    assert projeto.tem_versao_tarja is True
    assert projeto.tem_anexo_merito is False
    assert len(projeto.documentos_faltantes) >= 1
    assert any("Anexo II" in d for d in projeto.documentos_faltantes)
    assert projeto.pontuacao_merito is None


@requer_editais
def test_analise_anexo_ii_stream_docx():
    pvg2933 = PASTA_EDITAIS / "PVG2933-2025"
    anexo_docx = pvg2933 / "PVG2933-2025 - ANEXO-II-FORMULARIO-DE-PONTUACAO-DO-LATTES-MERITO-CURRICULAR.docx"
    if not anexo_docx.exists():
        pytest.skip("Arquivo docx do PVG2933 não encontrado.")

    total, criterios = extrair_criterios_anexo_ii_stream(anexo_docx.name, anexo_docx.read_bytes())
    assert total == 50.0
    assert len(criterios) == 13


@requer_editais
def test_gerar_dataframe_submissao():
    pvg2904 = PASTA_EDITAIS / "PVG2904-2025"
    if not pvg2904.exists():
        pytest.skip("Pasta PVG2904-2025 não encontrada.")

    projeto = analisar_pasta_pvg(pvg2904)
    dfs = gerar_dataframe_submissao(projeto)

    assert "detalhes" in dfs
    assert "arquivos" in dfs
    assert "equipe" in dfs
    assert "merito" in dfs

    df_det = dfs["detalhes"]
    assert len(df_det) == 1
    assert "Código" in df_det.columns
    assert "Documentos Faltantes" in df_det.columns
    assert "Equipe" in df_det.columns
    assert "Pontuação Mérito Curricular" in df_det.columns


def test_rejeitar_arquivo_nao_compactado(tmp_path):
    from src.submissoes.drive_sync import ErroDrivePersonalizado, extrair_zip_submissoes

    dados_falsos = b"%PDF-1.4 conteudo de um pdf solto"
    pasta_tmp = tmp_path / "teste_tmp"

    with pytest.raises(ErroDrivePersonalizado) as excinfo:
        extrair_zip_submissoes(dados_falsos, pasta_tmp, nome_arquivo="documento.pdf")

    assert "Formato não permitido" in str(excinfo.value) or "compactado" in str(excinfo.value)

