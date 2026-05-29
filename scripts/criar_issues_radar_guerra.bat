@echo off
cd /d "%~dp0.."
REM Criar Issues para Radar de Guerra v2 - GitHub CLI
REM Execute: .\criar_issues_radar_guerra.bat

echo Criando Issues no GitHub...

REM Issue 1: Revisar collect_river_race_full.py
gh api repos/GilvanS/historico-clash-roayle/issues -X POST ^
  -f title="[Task 1] Revisar collect_river_race_full.py - garantir data_coleta no CSV" ^
  -f body="# Task 1: Revisar collect_river_race_full.py

## Descricao
Revisar collect_river_race_full.py para garantir que salva data_coleta em cada linha do CSV. O campo data_coleta deve ter formato YYYY-MM-DD para identificar quando cada jogador lutou.

## Motivacao
Cada linha do CSV deve ter o campo data_coleta indicando a data da coleta. Isso permitira filtrar decks por dia especifico no calendario de guerra.

## Teste
Verificar arquivo inteligencia_guerra_*.csv se tem coluna data_coleta com formato YYYY-MM-DD.

## Prioridade: HIGH" ^
  -f labels[]="radar-guerra" ^
  --jq '{number, title}'

REM Issue 2: Modificar get_war_radar_data()
gh api repos/GilvanS/historico-clash-roayle/issues -X POST ^
  -f title="[Task 2] Modificar get_war_radar_data() - processar todos por data" ^
  -f body="# Task 2: Modificar get_war_radar_data()

## Descricao
Modificar get_war_radar_data() em html_generator.py para processar TODOS os arquivos de inteligencia_guerra_* por data, nao apenas o mais recente.

## Motivacao
Adicionar campo data_coleta em cada jogador processado do CSV. Agregar dados por data ao inves de usar so o arquivo mais recente.

## Dependencies
Task 1

## Teste
Gerar novo HTML e verificar que cada .rd-player tem data-date correto.

## Prioridade: HIGH" ^
  -f labels[]="radar-guerra" ^
  --jq '{number, title}'

REM Issue 3: Revisar selectWarDay()
gh api repos/GilvanS/historico-clash-roayle/issues -X POST ^
  -f title="[Task 3] Revisar selectWarDay() - atualizar posicao do clan" ^
  -f body="# Task 3: Revisar selectWarDay()

## Descricao
Revisar funcao selectWarDay() para atualizar tambem posicao do clan no cabecalho quando dia e selecionado.

## Motivacao
Quando usuario clica em um dia, deve mostrar posicao do clan naquele dia especifico.

## Dependencies
Task 2

## Teste
Clicar em diferentes dias e verificar mudanca na posicao do clan.

## Prioridade: MEDIUM" ^
  -f labels[]="radar-guerra" ^
  --jq '{number, title}'

REM Issue 4: Testar clique no calendario
gh api repos/GilvanS/historico-clash-roayle/issues -X POST ^
  -f title="[Task 4] Testar clique no calendario - decks aparecem por data" ^
  -f body="# Task 4: Testar clique no calendario

## Descricao
Testar clique em cada dia do calendario e verificar que decks aparecem corretamente para cada data.

## Dependencies
Task 2, Task 3

## Teste
Abrir index.html no navegador, clicar em cada dia do calendario e verificar os decks.

## Prioridade: HIGH" ^
  -f labels[]="radar-guerra" ^
  --jq '{number, title}'

REM Issue 5: TOP Global com top 3 por clan
gh api repos/GilvanS/historico-clash-roayle/issues -X POST ^
  -f title="[Task 5] TOP Global com top 3 por clan" ^
  -f body="# Task 5: TOP Global com top 3 por clan

## Descricao
TOP Global deve mostrar apenas top 3 jogadores de cada clan para performance. Conta principal e secundaria mostram todos os dados.

## Motivacao
Diferenciar logica: TOP_GLOBAL = top 3 por clan, #2QR292P e #2220UQQ0UU = todos os dados.

## Dependencies
Task 2

## Teste
Verificar que TOP Global tem so 3 players por clan, mas contas tem todos.

## Prioridade: MEDIUM" ^
  -f labels[]="radar-guerra" ^
  --jq '{number, title}'

echo.
echo Issues criadas com sucesso!
echo Verifique: https://github.com/GilvanS/historico-clash-roayle/issues
pause
