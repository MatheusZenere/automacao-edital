"""Caminhos do projeto. Dados e saídas ficam fora do repositório de código.

Layout esperado (pasta-mãe do repositório):

    bolsaIf/
    ├── automacaoEdital/   # código (este repositório)
    ├── editais/           # documentos de exemplo
    ├── contexto/          # contexto das conversas com agentes de IA
    ├── cache/             # downloads temporários por sessão
    └── saidas/            # CSVs e relatórios gerados

Cada pasta pode ser trocada por variável de ambiente (BOLSAIF_EDITAIS, BOLSAIF_CACHE, BOLSAIF_SAIDAS).
"""
import os
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
DADOS_DIR = REPO_DIR.parent


def _pasta(variavel: str, padrao: Path) -> Path:
    return Path(os.environ.get(variavel) or padrao).expanduser()


PASTA_EDITAIS = _pasta("BOLSAIF_EDITAIS", DADOS_DIR / "editais")
PASTA_CACHE = _pasta("BOLSAIF_CACHE", DADOS_DIR / "cache" / "downloads_drive")
PASTA_SAIDAS = _pasta("BOLSAIF_SAIDAS", DADOS_DIR / "saidas")
