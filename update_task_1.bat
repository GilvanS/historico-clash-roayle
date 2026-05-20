@echo off
setlocal enabledelayedexpansion

echo [INFO] Atualizando a Issue #13 no GitHub via gh api usando a autenticacao global do seu sistema...

:: Chamada da API do GitHub via PATCH herdando a credencial ativa do host do usuario
"C:\Program Files\GitHub CLI\gh.exe" api repos/GilvanS/historico-clash-roayle/issues/13 -X PATCH -f state="closed" -f title="[Task 1] Fase 1: Coleta de Dados - data_coleta no CSV (Concluido)" -f body="Task 1 finalizada com sucesso. Modificacoes aplicadas nos arquivos collect_river_race_full.py e collect_war_top_decks.py para consistencia de formato de data ISO YYYY-MM-DD e remocao de filtros restritivos no mes de maio de 2026."

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCESSO] Issue #13 atualizada e fechada no GitHub com sucesso!
) else (
    echo.
    echo [INFO] Tentando usar o token local do .env devido a falha na autenticacao global...
    :: Buscar o token GITHUB_API_KEY no arquivo .env
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        set "key=%%A"
        set "value=%%B"
        for /f "tokens=* delims= " %%i in ("!key!") do set "key=%%i"
        for /f "tokens=* delims= " %%i in ("!value!") do set "value=%%i"
        set "value=!value:"=!"
        if "!key!"=="GITHUB_API_KEY" (
            set "GH_TOKEN=!value!"
        )
    )
    
    if defined GH_TOKEN (
        "C:\Program Files\GitHub CLI\gh.exe" api repos/GilvanS/historico-clash-roayle/issues/13 -X PATCH -f state="closed" -f title="[Task 1] Fase 1: Coleta de Dados - data_coleta no CSV (Concluido)" -f body="Task 1 finalizada com sucesso."
    ) else (
        echo [ERRO] Nao foi possivel encontrar GITHUB_API_KEY no arquivo .env!
    )
)

pause
