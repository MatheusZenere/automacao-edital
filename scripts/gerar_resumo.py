#!/usr/bin/env python3
"""Script para leitura automatizada de editais e submissões a partir de pastas do Drive ou locais."""
from pathlib import Path
import sys
import uuid

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from src.config import PASTA_CACHE, PASTA_SAIDAS
from src.submissoes.analise_editais import analisar_todos_editais, gerar_dataframes
from src.submissoes.drive_sync import ErroDrivePersonalizado, extrair_zip_submissoes
from src.submissoes.exportacao import csv_seguro

EXTENSOES_COMPACTADAS = (".zip", ".tar.gz", ".tar", ".tgz")


def resumir(pasta_alvo: Path) -> None:
    """Analisa as subpastas, imprime o status de cada submissão e exporta o resumo em CSV."""
    projetos = analisar_todos_editais(pasta_alvo)
    if not projetos:
        print("[AVISO] Nenhuma subpasta de edital encontrada no diretório informado.")
        return

    print(f"[OK] {len(projetos)} submissões processadas com sucesso.\n")
    for p in projetos:
        status = "[OK] Completo" if not p.documentos_faltantes else f"[AVISO] Faltam: {len(p.documentos_faltantes)}"
        print(f"  • {p.codigo:14} | {p.coordenador:30} | {status:15} | Mérito: {p.pontuacao_merito}")

    PASTA_SAIDAS.mkdir(parents=True, exist_ok=True)
    caminho_csv = PASTA_SAIDAS / "resumo_projetos_editais.csv"
    caminho_csv.write_bytes(csv_seguro(gerar_dataframes(projetos)["resumo"]))
    print("\n" + "=" * 70)
    print(f"[EXPORTADO] Resumo consolidado exportado em: {caminho_csv}")


def main():
    args = sys.argv[1:]

    print("=" * 70)
    print("Verificador de Submissão de Editais & Projetos")
    print("=" * 70)

    if len(args) == 1 and Path(args[0]).is_file():
        # Arquivo compactado (.zip)
        caminho_arq = Path(args[0])
        if not caminho_arq.name.lower().endswith(EXTENSOES_COMPACTADAS):
            print(f"[ERRO] Formato não permitido: '{caminho_arq.suffix}'!")
            print("O sistema aceita exclusivamente arquivos compactados (.zip) contendo as subpastas dos editais.")
            print("Não é permitido o envio de arquivos avulsos (como PDFs soltos).")
            sys.exit(1)

        print(f"[ZIP] Descompactando arquivo compactado: {caminho_arq.name}...")
        try:
            pasta_dest = PASTA_CACHE / f"cli_{uuid.uuid4().hex}"
            pasta_alvo = extrair_zip_submissoes(caminho_arq.read_bytes(), pasta_dest, nome_arquivo=caminho_arq.name)
            resumir(pasta_alvo)
        except ErroDrivePersonalizado as e:
            print(f"[ERRO] {e}")
            sys.exit(1)

    elif len(args) == 1 and Path(args[0]).is_dir():
        # Diretório com uma subpasta por submissão
        print(f"[INFO] Analisando diretório: {args[0]}")
        resumir(Path(args[0]))

    elif args:
        print("[ERRO] Operação não permitida!")
        print("O sistema não permite o envio de arquivos avulsos não compactados.")
        print("Por favor, compacte os arquivos em formato (.zip) ou informe a pasta.")
        sys.exit(1)

    else:
        print("[INFO] Nenhuma pasta ou arquivo compactado informado.")
        print("Para analisar um arquivo compactado (.zip) dos editais, execute:")
        print("  pdm run resumo /caminho/para/arquivo.zip")
        print("Ou para um diretório:")
        print("  pdm run resumo /caminho/para/pasta")

    print("=" * 70)
    print("[DICA] Para iniciar a interface visual web:")
    print("   pdm run app")
    print("=" * 70)


if __name__ == "__main__":
    main()
