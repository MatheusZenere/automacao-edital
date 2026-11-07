# Análise de editais (Fase 1)

Lê os arquivos de um edital (PDF, DOCX, ODT) e gera um checklist do que o candidato precisa cumprir. Funciona para qualquer tipo de edital, sem regras específicas.

## Estrutura

```text
bolsaIf/
├── automacaoEdital/        # este repositório (somente código)
│   ├── app/streamlit_app.py        # interface web
│   ├── scripts/gerar_resumo.py     # linha de comando
│   ├── src/
│   │   ├── config.py               # caminhos de dados/saídas
│   │   ├── edital/                 # Fase 1: checklist de um edital com Gemini
│   │   └── submissoes/             # verificação das submissões (Drive/ZIP)
│   ├── notebooks/                  # Colab
│   └── tests/
├── editais/                # documentos de exemplo (dados pessoais, fora do git)
├── contexto/               # contexto das conversas com agentes de IA
├── cache/                  # downloads temporários por sessão
└── saidas/                 # CSVs e relatórios gerados
```

Os caminhos podem ser trocados com `BOLSAIF_EDITAIS`, `BOLSAIF_CACHE` e `BOLSAIF_SAIDAS`.

### `src/edital`
- `leitura.py`: PDF/DOCX/ODT para texto; detecta PDF escaneado.
- `extracao.py`: extração com Gemini (saída estruturada).
- `validacao.py`: confere se o trecho citado pela IA existe no edital.
- `processo.py`: junta os arquivos de um processo e consolida o checklist.
- `relatorio_edital.py`: gera `checklist.json` e `checklist.md`.

### `src/submissoes`
- `analise_editais.py`: classifica documentos, extrai metadados/mérito e confere pendências.
- `drive_sync.py`: download de pasta do Drive e extração segura de ZIP.
- `exportacao.py`: CSV sem injeção de fórmulas.

Execução: `pdm run app`, `pdm run resumo <zip|pasta>`, `pdm run test`.

## Testes (não dependem da API)
```bash
uv venv .venv && uv pip install -r requirements.txt --python .venv/bin/python
.venv/bin/python -m pytest tests -v
```

## Usar no Colab
1. Gere uma chave em aistudio.google.com e guarde em 🔑 *Secrets* como `GEMINI_API_KEY`.
2. Compacte a pasta `src` (o notebook usa só `src/edital`) (`zip -r src.zip src`).
3. Abra `notebooks/analise_editais.ipynb` no Colab e execute as células na ordem.

> A parte que chama o Gemini ainda não foi testada com a API real.
