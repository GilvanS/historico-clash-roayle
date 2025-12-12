@echo off
REM ============================================
REM Script para executar relatorio de oponentes
REM ============================================

REM CONFIGURE AQUI SEU TOKEN E TAG
set CR_API_TOKEN=COLOQUE_SEU_TOKEN_AQUI
set CR_PLAYER_TAG=#COLOQUE_SUA_TAG_AQUI

REM Executa o script
echo Executando relatorio de oponentes...
echo.
python opponents_report.py

echo.
echo Relatorio gerado com sucesso!
pause

