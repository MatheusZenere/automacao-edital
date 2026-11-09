"""Testes das proteções contra entradas maliciosas."""
import io
import zipfile

import pandas as pd
import pytest

from src.submissoes import drive_sync
from src.submissoes.analise_editais import analisar_pasta_pvg
from src.submissoes.drive_sync import ErroDrivePersonalizado, extrair_zip_submissoes
from src.submissoes.exportacao import csv_seguro


class _RespostaFalsa:
    """Imita uma resposta do requests em streaming."""

    def __init__(self, blocos, content_type="application/pdf", status_code=200):
        self.blocos = blocos
        self.headers = {"content-type": content_type}
        self.status_code = status_code
        self.text = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from self.blocos


def test_csv_neutraliza_formulas():
    df = pd.DataFrame({"a": ["=HYPERLINK(\"http://x\")", "+1", "-1", "@SOMA(A1)", "normal"]})
    linhas = csv_seguro(df).decode("utf-8-sig").splitlines()[1:]
    assert all(l.lstrip('"').startswith("'") for l in linhas[:4])
    assert linhas[4] == "normal"


def test_zip_com_caminho_fora_do_destino_nao_escapa(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../fora.txt", "x")
        z.writestr("PVG1/projeto.pdf", "x")
    destino = tmp_path / "dest"
    extrair_zip_submissoes(buf.getvalue(), destino, nome_arquivo="a.zip")
    assert not (tmp_path / "fora.txt").exists()
    assert not (tmp_path.parent / "fora.txt").exists()


def test_zip_acima_do_limite_de_arquivos_e_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr("src.submissoes.drive_sync.MAX_ARQUIVOS", 2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(5):
            z.writestr(f"PVG{i}/a.pdf", "x")
    with pytest.raises(ErroDrivePersonalizado):
        extrair_zip_submissoes(buf.getvalue(), tmp_path / "d", nome_arquivo="a.zip")


def test_arquivo_do_drive_acima_do_limite_e_recusado_sem_plano_b(tmp_path, monkeypatch):
    monkeypatch.setattr(drive_sync, "MAX_BYTES_ARQUIVO_DRIVE", 10)
    chamadas = []

    def _get(*args, **kwargs):
        chamadas.append(args)
        return _RespostaFalsa([b"x" * 8, b"x" * 8])

    monkeypatch.setattr(drive_sync.requests, "get", _get)
    item = drive_sync.ArquivoDrive(id="abc", caminho_local=tmp_path / "grande.pdf")
    with pytest.raises(ErroDrivePersonalizado):
        drive_sync._baixar_arquivo(item, drive_sync._Cota())
    assert len(chamadas) == 1  # não tenta de novo nem cai em outro download sem limite
    assert list(tmp_path.iterdir()) == []


def test_pasta_do_drive_acima_do_limite_total_e_recusada(tmp_path, monkeypatch):
    monkeypatch.setattr(drive_sync.requests, "get", lambda *a, **k: _RespostaFalsa([b"x" * 6]))
    cota = drive_sync._Cota(limite=10)
    drive_sync._baixar_arquivo(drive_sync.ArquivoDrive(id="1", caminho_local=tmp_path / "a.pdf"), cota)
    with pytest.raises(ErroDrivePersonalizado):
        drive_sync._baixar_arquivo(drive_sync.ArquivoDrive(id="2", caminho_local=tmp_path / "b.pdf"), cota)
    assert not (tmp_path / "b.pdf").exists()


def test_link_de_confirmacao_fora_do_google_e_recusado(monkeypatch):
    import sys

    import gdown.download  # noqa: F401 (gdown.download é a função; o módulo fica em sys.modules)

    monkeypatch.setattr(
        sys.modules["gdown.download"], "get_url_from_gdrive_confirmation", lambda html: "https://evil.example/x"
    )
    with pytest.raises(RuntimeError):
        drive_sync._url_confirmacao("<html></html>")


def test_arquivo_grande_da_submissao_nao_e_lido(tmp_path, monkeypatch):
    monkeypatch.setattr("src.submissoes.analise_editais.MAX_BYTES_ANALISE", 10)
    (tmp_path / "grande.pdf").write_bytes(b"x" * 2048)
    projeto = analisar_pasta_pvg(tmp_path)
    assert projeto.arquivos[0].tamanho_kb == 2.0  # listado com o tamanho real, sem abrir
