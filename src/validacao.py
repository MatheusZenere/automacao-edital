"""Validação anti-alucinação: o trecho citado pela IA existe no edital?"""
import re
import unicodedata


def normalizar(texto: str) -> str:
    """Remove diferenças irrelevantes: acentos de composição, hifenização, quebras e espaços."""
    texto = unicodedata.normalize("NFKC", texto)
    texto = texto.replace("\u00ad", "")                    # hífen suave
    texto = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", texto)   # palavra hifenizada na quebra de linha
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip().lower()


def trecho_existe(trecho: str, texto_fonte: str) -> bool:
    t = normalizar(trecho)
    if len(t) < 8:  # curto demais para ser evidência
        return False
    return t in normalizar(texto_fonte)
