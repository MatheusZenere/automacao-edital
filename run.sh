#!/usr/bin/env bash
# Atalho de execução para o Verificador de Editais & Submissões

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

comando="${1:-resumo}"

case "$comando" in
    resumo)
        echo "📊 Executando resumo via PDM..."
        pdm run resumo
        ;;
    app)
        echo "🚀 Iniciando Streamlit via PDM..."
        pdm run app
        ;;
    test)
        echo "🧪 Executando testes via PDM..."
        pdm run test
        ;;
    *)
        echo "Uso: ./run.sh [resumo|app|test]"
        echo "Ou diretamente com PDM:"
        echo "  pdm run resumo"
        echo "  pdm run app"
        echo "  pdm run test"
        exit 1
        ;;
esac
