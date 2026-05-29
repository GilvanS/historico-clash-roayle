@echo off
cd /d "%~dp0.."
set REPO=GilvanS/historico-clash-roayle
set LABELS=radar-guerra

echo.
echo ========================================
echo  Criando Issues - Radar de Guerra v2
echo ========================================
echo.

REM ===== Issue 1 =====
echo [1/5] Criando Task 1...
gh api repos/%REPO%/issues -X POST -f title="[Task 1] data_coleta no CSV" -f body="Revisar collect_river_race_full.py para garantir data_coleta no CSV com formato YYYY-MM-DD" -f labels[]=%LABELS%
echo.

REM ===== Issue 2 =====
echo [2/5] Criando Task 2...
gh api repos/%REPO%/issues -X POST -f title="[Task 2] get_war_radar_data() por data" -f body="Modificar get_war_radar_data() para processar TODOS os arquivos por data" -f labels[]=%LABELS%
echo.

REM ===== Issue 3 =====
echo [3/5] Criando Task 3...
gh api repos/%REPO%/issues -X POST -f title="[Task 3] selectWarDay() atualizar posicao" -f body="Revisar selectWarDay() para atualizar posicao do clan no cabecalho" -f labels[]=%LABELS%
echo.

REM ===== Issue 4 =====
echo [4/5] Criando Task 4...
gh api repos/%REPO%/issues -X POST -f title="[Task 4] Testar calendario" -f body="Testar clique no calendario e verificar decks por data" -f labels[]=%LABELS%
echo.

REM ===== Issue 5 =====
echo [5/5] Criando Task 5...
gh api repos/%REPO%/issues -X POST -f title="[Task 5] TOP Global top 3" -f body="TOP Global = top 3 por clan. Contas = todos os dados" -f labels[]=%LABELS%
echo.

echo ========================================
echo Concluido!
echo Verifique: https://github.com/%REPO%/issues
echo ========================================
pause
