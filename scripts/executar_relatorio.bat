@echo off
REM ============================================
REM Script para executar relatorio de oponentes
REM ============================================

REM Os tokens e tags agora sao gerenciados pelo arquivo .env na raiz do projeto.
REM Isso garante que suas credenciais nao fiquem expostas em scripts.

REM Executa o script a partir da pasta src
echo Executando relatorio de oponentes...
echo.

REM Ajuste: chamando o script que esta na pasta legacy, mantendo a compatibilidade
python legacy/opponents_report.py

echo.
echo Relatorio gerado com sucesso! (Verifique a pasta raiz ou src para os CSVs)
pause
