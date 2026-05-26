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
    
    set PUSH_SUCCESS=0
    for /L %%i in (1,1,3) do (
        if !PUSH_SUCCESS! equ 0 (
            git push origin main
            if !errorlevel! equ 0 (
                set PUSH_SUCCESS=1
            ) else (
                echo Tentativa %%i falhou, rebase...
                git pull --rebase -X theirs origin main
            )
        )
    )
)

echo [%time%] Sincronizacao concluida! Aguardando 30 minutos...
timeout /t 1800 /nobreak

goto :loop