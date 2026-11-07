"""Detecção da pasta raiz das submissões."""
from src.submissoes.drive_sync import detectar_raiz_submissoes


def _arquivo(caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"x")


def test_desce_pelo_embrulho_e_para_na_raiz_com_edital(tmp_path):
    raiz = tmp_path / "zip" / "ProjetosPesquisa"
    _arquivo(raiz / "EDITAL-13-2025.pdf")
    _arquivo(raiz / "PVG1" / "projeto.pdf")
    _arquivo(raiz / "PVG2" / "projeto.pdf")
    assert detectar_raiz_submissoes(tmp_path / "zip") == raiz


def test_desce_pelo_embrulho_sem_edital(tmp_path):
    raiz = tmp_path / "zip" / "ProjetosPesquisa"
    _arquivo(raiz / "PVG1" / "projeto.pdf")
    assert detectar_raiz_submissoes(tmp_path / "zip") == raiz


def test_pasta_com_um_unico_projeto_nao_e_embrulho(tmp_path):
    _arquivo(tmp_path / "PVG1" / "projeto.pdf")
    assert detectar_raiz_submissoes(tmp_path) == tmp_path


def test_ignora_marcador_oculto_do_cache(tmp_path):
    raiz = tmp_path / "drive" / "Pasta"
    _arquivo(tmp_path / "drive" / ".folder_id")
    _arquivo(raiz / "PVG1" / "projeto.pdf")
    assert detectar_raiz_submissoes(tmp_path / "drive") == raiz
