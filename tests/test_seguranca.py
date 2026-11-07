"""Testes das proteções contra entradas maliciosas."""
import io
import zipfile

import pandas as pd
import pytest

from src.submissoes.drive_sync import ErroDrivePersonalizado, extrair_zip_submissoes
from src.submissoes.exportacao import csv_seguro


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
