@echo off
cd /d "%~dp0.."
setlocal enabledelayedexpansion

echo ============================================================
echo [SINCRONIZACAO ELITE] Clash Royale - Local para Web
echo ============================================================

:: Verificar se estamos em um repositorio Git
if not exist .git (
    echo [ERRO] Este script deve ser executado na raiz do projeto.
    pause
    exit /b
)

:: 1. Sincronizar com o remoto para evitar conflitos
echo 1. Puxando alteracoes do GitHub (evitando conflitos)...
git pull --rebase -X theirs origin main

:: 2. Executar o pipeline completo
echo 2. Iniciando extracao e geracao do dashboard...
python src/main_sync.py

:: 3. Verificar se houve alteracoes para commitar
echo 3. Preparando envio para o Dashboard Web...
git add src/data_csv_oficial/ README.md index.html src/data_clan/

:: Verificar se ha algo para commitar
git diff --staged --quiet
if errorlevel 1 (
    echo [OK] Alteracoes detectadas. Enviando para o GitHub...
    git commit -m "chore: sincronizacao local Elite (%date% %time%)"
    
    :: Loop de push com retry (similar ao GitHub Action)
    for /L %%i in (1,1,3) do (
        git push origin main
        if !errorlevel! equ 0 (
            echo [SUCESSO] Web Dashboard atualizado!
            goto :end
        )
        echo [AVISO] Tentativa %%i/3 falhou, tentando rebase...
        git pull --rebase -X theirs origin main
    )
    echo [ERRO] Nao foi possivel sincronizar com o GitHub. Verifique sua conexao.
) else (
    echo [INFO] Nenhuma alteracao nova para enviar.
)

:end
echo ============================================================
echo PROCESSO CONCLUIDO!
echo ============================================================
pause
