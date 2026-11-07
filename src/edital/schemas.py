"""Modelos de dados da análise de editais."""
from typing import Literal

from pydantic import BaseModel, Field

Categoria = Literal["documento", "requisito", "prazo", "formato", "declaracao", "outro"]


class ExigenciaLLM(BaseModel):
    """Campos que a IA deve preencher (sem campos controlados pelo código)."""

    referencia: str = Field(
        description="Numeração original do trecho no edital, ex.: 'Art. 6º, I' ou '5.1 a'."
    )
    categoria: Categoria
    descricao: str = Field(description="O que o candidato precisa cumprir, entregar ou respeitar.")
    obrigatoria: bool
    condicao: str | None = Field(default=None, description="Condição para a exigência valer, se houver.")
    prazo: str | None = Field(default=None, description="Prazo/data como escrito no edital.")
    consequencia: str | None = Field(default=None, description="O que acontece se não cumprir.")
    trecho_original: str = Field(
        description="Cópia LITERAL, palavra por palavra, do trecho do edital que origina a exigência."
    )


class EtapaCronograma(BaseModel):
    etapa: str
    data: str


class InfoEdital(BaseModel):
    titulo: str
    numero: str | None = None
    cronograma: list[EtapaCronograma] = Field(default_factory=list)
    documentos_dependentes: list[str] = Field(
        default_factory=list,
        description="Outros editais, leis ou normas citados como regentes ou complementares.",
    )


class ExtracaoLLM(BaseModel):
    """Resposta estruturada esperada do modelo para um arquivo."""

    info: InfoEdital
    exigencias: list[ExigenciaLLM]


class Exigencia(ExigenciaLLM):
    id: str
    arquivo: str
    verificado: bool = False


class ArquivoProcessado(BaseModel):
    arquivo: str
    info: InfoEdital


class Checklist(BaseModel):
    arquivos: list[ArquivoProcessado]
    exigencias: list[Exigencia]
