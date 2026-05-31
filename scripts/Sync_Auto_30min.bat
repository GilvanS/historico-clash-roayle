@echo off
cd /d "%~dp0.."
setlocal enabledelayedexpansion

echo ============================================================
echo [AUTO-SYNC] Clash Royale - Loop de Sincronizacao Resiliente
echo ============================================================
echo Pressione Ctrl+C para parar
echo.

set CONSECUTIVE_FAILURES=0

:loop
echo [%time%] Iniciando sincronizacao...
git rebase --abort >nul 2>&1
git pull --rebase --autostash -X theirs origin main
set PYTHONPATH=%CD%\src;%CD%\src\api;%CD%\src\core;%CD%\src\generators;%CD%\src\utils
python src/main_sync.py

git add data/csv/  README.md docs/ data/json/ 

set PUSH_SUCCESS=1

git diff --staged --quiet
if errorlevel 1 (
    git commit -m "chore: sincronizacao automatica Clash Royale %date% %time%"
    
    set PUSH_SUCCESS=0
    for /L %%i in (1,1,3) do (
        if !PUSH_SUCCESS! equ 0 (
            if %%i gtr 1 (
                echo [INFO] Aguardando 10 segundos antes de tentar novamente...
                timeout /t 10 /nobreak >nul
            )
            git push origin main
            if !errorlevel! equ 0 (
                set PUSH_SUCCESS=1
                echo [SUCESSO] Dados enviados e unificados no GitHub com sucesso!
            ) else (
                echo.
                echo [AVISO] A nuvem contem dados novos. Tentativa %%i/3 falhou.
                echo [INFO] Puxando dados mais recentes do GitHub e realizando o rebase local...
                git rebase --abort >nul 2>&1
                git pull --rebase --autostash -X theirs origin main
            )
        )
    )
    if !PUSH_SUCCESS! equ 0 (
        echo.
        echo =======================================================================
        echo [AVISO DE CONCORRENCIA GIT]
        echo Nao foi possivel enviar os dados para a nuvem apos 3 tentativas.
        echo Isso acontece porque o GitHub Actions remoto ou outro computador
        echo comitou dados novos no mesmo instante.
        echo Fique tranquilo! Seus dados locais estao salvos com seguranca.
        echo =======================================================================
        echo.
    )
)

if !PUSH_SUCCESS! equ 0 (
    set /A CONSECUTIVE_FAILURES+=1
    if !CONSECUTIVE_FAILURES! leq 3 (
        echo [%time%] Sincronizacao falhou (Falhas consecutivas: !CONSECUTIVE_FAILURES!/3). Tentando rodada de emergencia em 1 minuto...
        timeout /t 60 /nobreak
    ) else (
        echo [%time%] Sincronizacao falhou por 3 vezes seguidas. Retornando ao fallback de seguranca de 30 minutos...
        set CONSECUTIVE_FAILURES=0
        timeout /t 1800 /nobreak
    )
) else (
    set CONSECUTIVE_FAILURES=0
    echo [%time%] Sincronizacao concluida! Aguardando 30 minutos...
    timeout /t 1800 /nobreak
)

goto :loop
