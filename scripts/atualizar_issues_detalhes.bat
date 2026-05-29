@echo off
cd /d "%~dp0.."
REM Atualizar issues com descrições detalhadas em PT-BR

echo ============================================
echo  Atualizando Issues - Radar de Guerra v2
echo  Com descricoes completas em PT-BR
echo ============================================
echo.

REM ===== Issue 6 - Task 1 =====
echo [1/5] Atualizando Issue 6...
gh api repos/GilvanS/historico-clash-roayle/issues/6 -X PATCH -f body="## Descricao
Revisar collect_river_race_full.py para garantir que salva data_coleta em cada linha do CSV. O campo data_coleta deve ter formato YYYY-MM-DD para identificar quando cada jogador lutou.

## Motivacao
Cada linha do CSV deve ter o campo data_coleta indicando a data da coleta. Isso permitira filtrar decks por dia especifico no calendario de guerra.

## Arquivo Envolvido
- src/collect_river_race_full.py

## Teste
Verificar arquivo inteligencia_guerra_*.csv se tem coluna data_coleta com formato YYYY-MM-DD.

## Prioridade: HIGH"
echo.

REM ===== Issue 7 - Task 2 =====
echo [2/5] Atualizando Issue 7...
gh api repos/GilvanS/historico-clash-roayle/issues/7 -X PATCH -f body="## Descricao
Modificar get_war_radar_data() em html_generator.py para processar TODOS os arquivos de inteligencia_guerra_* por data, nao apenas o mais recente.

## Motivacao
Adicionar campo data_coleta em cada jogador processado do CSV. Agregar dados por data ao inves de usar so o arquivo mais recente.

## Arquivo Envolvido
- src/html_generator.py (get_war_radar_data)

## Dependencies
Issue 6 (Task 1)

## Teste
Gerar novo HTML e verificar que cada .rd-player tem data-date correto.

## Prioridade: HIGH"
echo.

REM ===== Issue 8 - Task 3 =====
echo [3/5] Atualizando Issue 8...
gh api repos/GilvanS/historico-clash-roayle/issues/8 -X PATCH -f body="## Descricao
Revisar funcao selectWarDay() para atualizar tambem posicao do clan no cabecalho quando dia e selecionado.

## Motivacao
Quando usuario clica em um dia do calendario, deve mostrar a posicao do clan naquele dia especifico, alem de filtrar os jogadores.

## Arquivo Envolvido
- index.html (JavaScript selectWarDay())

## Dependencies
Issue 7 (Task 2)

## Teste
Clicar em diferentes dias e verificar mudanca na posicao do clan exibida.

## Prioridade: MEDIUM"
echo.

REM ===== Issue 9 - Task 4 =====
echo [4/5] Atualizando Issue 9...
gh api repos/GilvanS/historico-clash-roayle/issues/9 -X PATCH -f body="## Descricao
Testar clique em cada dia do calendario e verificar que decks aparecem corretamente para cada data.

## Motivacao
Validar que ao selecionar um dia especifico no calendario, os decks mostrados sao os decks usados naquele dia, permitindo ver a evolucao dos decks ao longo da guerra.

## Dependencies
Issues 7 e 8 (Task 2 e Task 3)

## Teste
1. Abrir index.html no navegador
2. Clicar em cada dia do calendario
3. Verificar que decks aparecem corretamente para cada data
4. Verificar que data-date esta presente em cada .rd-player

## Prioridade: HIGH"
echo.

REM ===== Issue 10 - Task 5 =====
echo [5/5] Atualizando Issue 10...
gh api repos/GilvanS/historico-clash-roayle/issues/10 -X PATCH -f body="## Descricao
TOP Global deve mostrar apenas top 3 jogadores de cada clan para performance. Conta principal e secundaria mostram todos os dados.

## Motivacao
Diferenciar logica: TOP_GLOBAL = top 3 por clan (performance), #2QR292P e #2220UQQ0UU = todos os dados (analise completa).

## Arquivo Envolvido
- src/html_generator.py (get_war_radar_data)

## Dependencies
Issue 7 (Task 2)

## Teste
1. Verificar que TOP Global tem so 3 players por clan
2. Verificar que contas principais tem todos os dados

## Prioridade: MEDIUM"
echo.

echo ============================================
echo Concluido! Issues atualizadas.
echo ============================================
pause
