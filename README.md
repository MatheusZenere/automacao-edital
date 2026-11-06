# Análise de editais (Fase 1)

Lê os arquivos de um edital (PDF, DOCX, ODT) e gera um checklist do que o candidato precisa cumprir. Funciona para qualquer tipo de edital, sem regras específicas.

## Estrutura
- `src/leitura.py`: PDF/DOCX/ODT para texto; detecta PDF escaneado.
- `src/extracao.py`: extração com Gemini (saída estruturada).
- `src/validacao.py`: confere se o trecho citado pela IA existe no edital.
- `src/processo.py`: junta os arquivos de um processo e consolida o checklist.
- `src/relatorio_edital.py`: gera `checklist.json` e `checklist.md`.
- `notebooks/analise_editais.ipynb`: notebook do Colab.

## Testes (não dependem da API)
```bash
uv venv .venv && uv pip install -r requirements.txt --python .venv/bin/python
.venv/bin/python -m pytest tests -v
```

## Usar no Colab
1. Gere uma chave em aistudio.google.com e guarde em 🔑 *Secrets* como `GEMINI_API_KEY`.
2. Compacte a pasta `src` (`zip -r src.zip src`).
3. Abra `notebooks/analise_editais.ipynb` no Colab e execute as células na ordem.

> A parte que chama o Gemini ainda não foi testada com a API real.
