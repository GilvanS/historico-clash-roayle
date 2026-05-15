@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo [AUTO-SYNC] Clash Royale - Loop de 30 minutos
echo ============================================================
echo Pressione Ctrl+C para parar
echo.

:loop
echo [%time%] Iniciando sincronizacao...
git pull --rebase -X theirs origin main
python src/main_sync.py

git add src/data_csv_oficial/ README.md index.html clan.html member_*.html src/data_clan/

git diff --staged --quiet
if errorlevel 1 (
    git commit -m "chore: sincronizacao automatica Clash Royale %date% %time%"
    
    for /L %%i in (1,1,3) do (
        git push origin main
        if !errorlevel! equ 0 goto :push_ok
        echo Tentativa %%i falhou, rebase...
        git pull --rebase -X theirs origin main
    )
    :push_ok
)

echo [%time%] Sincronizacao concluida! Aguardando 30 minutos...
timeout /t 1800 /nobreak

goto :loop