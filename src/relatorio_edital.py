"""Geração do checklist em JSON e Markdown."""
import json
from pathlib import Path

from .schemas import Checklist

ROTULOS = {
    "documento": "Documentos",
    "requisito": "Requisitos",
    "prazo": "Prazos",
    "formato": "Formato de envio",
    "declaracao": "Declarações",
    "outro": "Outros",
}


def para_markdown(cl: Checklist) -> str:
    linhas = ["# Checklist do edital", ""]
    for a in cl.arquivos:
        linhas.append(f"- **{a.arquivo}** — {a.info.titulo}" + (f" (nº {a.info.numero})" if a.info.numero else ""))
        for etapa in a.info.cronograma:
            linhas.append(f"    - {etapa.etapa}: {etapa.data}")
        for dep in a.info.documentos_dependentes:
            linhas.append(f"    - Documento dependente: {dep}")
    linhas.append("")

    nao_verificadas = [e for e in cl.exigencias if not e.verificado]
    if nao_verificadas:
        linhas += [
            f"> ⚠️ {len(nao_verificadas)} exigência(s) com trecho não confirmado no texto "
            "(marcadas com ⚠️). Revisar manualmente.",
            "",
        ]

    for categoria, rotulo in ROTULOS.items():
        itens = [e for e in cl.exigencias if e.categoria == categoria]
        if not itens:
            continue
        linhas += [f"## {rotulo}", ""]
        for e in itens:
            marca = "☐" if e.obrigatoria else "☐ *(opcional)*"
            alerta = "" if e.verificado else " ⚠️"
            linhas.append(f"- {marca} **{e.referencia}** — {e.descricao}{alerta}")
            if e.condicao:
                linhas.append(f"    - Condição: {e.condicao}")
            if e.prazo:
                linhas.append(f"    - Prazo: {e.prazo}")
            if e.consequencia:
                linhas.append(f"    - Consequência: {e.consequencia}")
            linhas.append(f"    - Origem: {e.arquivo} ({e.id})")
        linhas.append("")
    return "\n".join(linhas)


def salvar(cl: Checklist, pasta: str | Path) -> tuple[Path, Path]:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    js = pasta / "checklist.json"
    md = pasta / "checklist.md"
    js.write_text(json.dumps(cl.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    md.write_text(para_markdown(cl), encoding="utf-8")
    return js, md
