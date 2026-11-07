#!/usr/bin/env python3
"""Script para leitura automatizada de editais e submissões a partir de pastas do Drive ou locais."""
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.analise_editais import (
    analisar_arquivos_submissao,
    analisar_todos_editais,
    gerar_dataframe_submissao,
    gerar_dataframes,
)
from src.drive_sync import ErroDrivePersonalizado, extrair_zip_submissoes


def main():
    args = sys.argv[1:]

    print("=" * 70)
    print("Verificador de Submissão de Editais & Projetos")
    print("=" * 70)

    # Caso 1: Usuário informou um arquivo compactado (.zip)
    if len(args) == 1 and Path(args[0]).is_file():
        caminho_arq = Path(args[0])
        if not caminho_arq.name.lower().endswith((".zip", ".tar.gz", ".tar", ".tgz")):
            print(f"[ERRO] Formato não permitido: '{caminho_arq.suffix}'!")
            print("O sistema aceita exclusivamente arquivos compactados (.zip) contendo as subpastas dos editais.")
            print("Não é permitido o envio de arquivos avulsos (como PDFs soltos).")
            sys.exit(1)

        print(f"[ZIP] Descompactando arquivo compactado: {caminho_arq.name}...")
        try:
            pasta_dest = BASE_DIR / "downloads_drive" / "zip_cli"
            pasta_alvo = extrair_zip_submissoes(caminho_arq.read_bytes(), pasta_dest, nome_arquivo=caminho_arq.name)
            projetos = analisar_todos_editais(pasta_alvo)
            print(f"[OK] {len(projetos)} submissões processadas com sucesso.\n")
            for p in projetos:
                status = "[OK] Completo" if not p.documentos_faltantes else f"[AVISO] Faltam: {len(p.documentos_faltantes)}"
                print(f"  • {p.codigo:14} | {p.coordenador:30} | {status:15} | Mérito: {p.pontuacao_merito}")

            dfs = gerar_dataframes(projetos)
            caminho_csv = BASE_DIR / "resumo_projetos_editais.csv"
            dfs["resumo"].to_csv(caminho_csv, index=False, encoding="utf-8-sig")
            print("\n" + "=" * 70)
            print(f"[EXPORTADO] Resumo consolidado exportado em: {caminho_csv}")
        except ErroDrivePersonalizado as e:
            print(f"[ERRO] {e}")
            sys.exit(1)

    # Caso 2: Usuário informou um diretório
    elif len(args) == 1 and Path(args[0]).is_dir():
        pasta_alvo = Path(args[0])
        print(f"[INFO] Analisando diretório: {pasta_alvo}")
        projetos = analisar_todos_editais(pasta_alvo)

        if not projetos:
            print("[AVISO] Nenhuma subpasta de edital encontrada no diretório informado.")
            sys.exit(0)

        print(f"[OK] {len(projetos)} submissões processadas com sucesso.")
        print("-" * 70)
        for p in projetos:
            status = "[OK] Completo" if not p.documentos_faltantes else f"[AVISO] Faltam: {len(p.documentos_faltantes)}"
            print(f"  • {p.codigo:14} | {p.coordenador:30} | {status:15} | Mérito: {p.pontuacao_merito}")

        dfs = gerar_dataframes(projetos)
        caminho_csv = BASE_DIR / "resumo_projetos_editais.csv"
        dfs["resumo"].to_csv(caminho_csv, index=False, encoding="utf-8-sig")
        print("\n" + "=" * 70)
        print(f"[EXPORTADO] Resumo consolidado exportado em: {caminho_csv}")

    # Caso 3: Usuário tentou passar múltiplos arquivos ou arquivos soltos
    elif args:
        print("[ERRO] Operação não permitida!")
        print("O sistema não permite o envio de arquivos avulsos não compactados.")
        print("Por favor, compacte os arquivos em formato (.zip) ou informe a pasta.")
        sys.exit(1)

    # Caso 4: Nenhum argumento informado
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
