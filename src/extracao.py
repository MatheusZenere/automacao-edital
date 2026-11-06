"""Extração de exigências com Gemini (saída estruturada)."""
from pathlib import Path

from .schemas import ExtracaoLLM

MODELO_PADRAO = "gemini-2.5-flash"

PROMPT = """Você analisa editais (processos seletivos, bolsas, concursos, afastamentos etc.).
Leia o documento e liste TUDO que o candidato precisa cumprir, entregar ou respeitar:
documentos exigidos, requisitos de elegibilidade, formatos de envio, prazos, declarações e
condições. Regras:
- Preserve a numeração original do edital em `referencia` (ex.: "Art. 6º, I", "5.1 a").
- `trecho_original` deve ser uma cópia LITERAL, palavra por palavra, do texto do edital.
  Não resuma nem corrija esse campo.
- Não invente exigências. Se algo não está no documento, não inclua.
- Marque `obrigatoria` como false apenas se o texto indicar que é opcional.
- Em `info`, preencha título, número, cronograma (etapa e data como escritas) e outros
  editais/normas citados como regentes ou complementares.
- Ignore informações apenas descritivas que não impõem nada ao candidato.
"""


def extrair_com_gemini(
    texto: str,
    arquivo: str,
    *,
    caminho: Path | None = None,
    escaneado: bool = False,
    api_key: str,
    modelo: str = MODELO_PADRAO,
) -> ExtracaoLLM:
    """Chama o Gemini para um arquivo. Se `escaneado`, envia o PDF direto (leitura multimodal)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    if escaneado and caminho is not None:
        conteudo = [
            types.Part.from_bytes(data=Path(caminho).read_bytes(), mime_type="application/pdf"),
            PROMPT,
        ]
    else:
        conteudo = [f"{PROMPT}\n\nARQUIVO: {arquivo}\n\n--- INÍCIO DO EDITAL ---\n{texto}\n--- FIM ---"]

    resposta = client.models.generate_content(
        model=modelo,
        contents=conteudo,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtracaoLLM,
            temperature=0,
        ),
    )
    if resposta.parsed is None:
        raise RuntimeError(f"Resposta do Gemini sem conteúdo estruturado para {arquivo}")
    return resposta.parsed
