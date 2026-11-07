"""Exportação segura de tabelas para CSV."""
import pandas as pd

_PREFIXOS_PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


def csv_seguro(df: pd.DataFrame) -> bytes:
    """CSV (UTF-8 com BOM) sem risco de injeção de fórmulas ao abrir no Excel/Planilhas.

    Os textos vêm de documentos de terceiros, então células iniciadas por =, +, -, @ são neutralizadas.
    """

    def _limpa(valor):
        if isinstance(valor, str) and valor[:1] in _PREFIXOS_PERIGOSOS:
            return "'" + valor
        return valor

    return df.map(_limpa).to_csv(index=False).encode("utf-8-sig")
