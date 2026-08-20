@echo off
cd /d "%~dp0.."
setlocal enabledelayedexpansion

set SILENT=0
if "%~1"=="silent" set SILENT=1

echo ============================================================
echo [SINCRONIZACAO ELITE] Clash Royale - Local para Web
echo ============================================================

:: Verificar se estamos em um repositorio Git
if not exist .git (
    echo [ERRO] Este script deve ser executado na raiz do projeto.
    if %SILENT%==0 pause
    exit /b 1
)

:: 1. Sincronizar com o remoto para evitar conflitos
echo 1. Puxando alteracoes do GitHub (evitando conflitos)...
git pull --rebase -X theirs origin main

:: 2. Executar o pipeline completo
echo 2. Iniciando extracao e geracao do dashboard...
python src/main_sync.py

:: 3. Verificar se houve alteracoes para commitar
echo 3. Preparando envio para o Dashboard Web...
git add data/csv/ README.md docs/ data/json/

:: Verificar se ha algo para commitar
git diff --staged --quiet
if errorlevel 1 (
    echo [OK] Alteracoes detectadas. Enviando para o GitHub...
    git commit -m "chore: sincronizacao local Elite (%date% %time%)"
    
    :: Loop de push com retry (similar ao GitHub Action)
    set PUSH_SUCCESS=0
    for /L %%i in (1,1,3) do (
        if !PUSH_SUCCESS! equ 0 (
            git push origin main
            if !errorlevel! equ 0 (
                echo [SUCESSO] Web Dashboard atualizado!
                set PUSH_SUCCESS=1
            ) else (
                echo.
                echo [AVISO] A nuvem contem dados novos. Tentativa %%i/3 falhou.
                echo [INFO] Puxando dados novos do GitHub e unificando localmente...
                git pull --rebase -X theirs origin main
            )
        )
    )
    if !PUSH_SUCCESS! equ 0 (
        echo.
        echo =======================================================================
        echo [AVISO DE CONCORRENCIA GIT]
        echo Nao foi possivel atualizar o Dashboard Web apos 3 tentativas.
        echo Isso ocorre quando o GitHub Actions remoto envia dados no mesmo segundo.
        echo O seu banco de dados local esta 100%% seguro e atualizado.
        echo Tente rodar o script novamente em alguns minutos para sincronizar!
        echo =======================================================================
        echo.
    )
) else (
    echo [INFO] Nenhuma alteracao nova para enviar.
)

:end
echo ============================================================
echo PROCESSO CONCLUIDO!
echo ============================================================
if %SILENT%==0 pause
