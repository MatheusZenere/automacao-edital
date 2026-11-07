"""Processo = conjunto de arquivos de um edital (edital + anexos). Consolida o checklist."""
from collections.abc import Callable
from pathlib import Path

from .leitura import ler_arquivo
from .schemas import ArquivoProcessado, Checklist, Exigencia, ExtracaoLLM
from .validacao import trecho_existe

# (texto, nome_arquivo, caminho, escaneado) -> ExtracaoLLM
Extrator = Callable[[str, str, Path, bool], ExtracaoLLM]


def processar(caminhos: list[str | Path], extrator: Extrator) -> Checklist:
    """Lê cada arquivo, extrai exigências e valida os trechos contra o texto original."""
    arquivos: list[ArquivoProcessado] = []
    exigencias: list[Exigencia] = []

    for c in caminhos:
        caminho = Path(c)
        texto, escaneado = ler_arquivo(caminho)
        extracao = extrator(texto, caminho.name, caminho, escaneado)
        arquivos.append(ArquivoProcessado(arquivo=caminho.name, info=extracao.info))

        for e in extracao.exigencias:
            exigencias.append(
                Exigencia(
                    **e.model_dump(),
                    id=f"E{len(exigencias) + 1:03d}",
                    arquivo=caminho.name,
                    # Em PDF escaneado não há texto para conferir: fica não verificado.
                    verificado=(not escaneado) and trecho_existe(e.trecho_original, texto),
                )
            )

    return Checklist(arquivos=arquivos, exigencias=exigencias)
