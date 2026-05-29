@echo off
cd /d "%~dp0.."
REM Radar Guerra v2 - Criar Issues com Sub-tasks
set REPO=GilvanS/historico-clash-roayle

echo.
echo === Criando 5 Issues + Sub-tasks Radar Guerra v2 ===
echo.

REM ========== ISSUE 1 - Coleta de Dados ==========
echo [1] Criando Issue 1 + Sub-tasks...
(
echo {"title":"[Task 1] Fase 1: Coleta de Dados - data_coleta no CSV","body":"**OBJETIVO:** Revisar collect_river_race_full.py para garantir data_coleta em cada linha do CSV.\n\n**ARQUIVOS:** src/collect_river_race_full.py, src/data_clan/inteligencia_guerra_*.csv\n\n**SUB-TASKS:**\n- [ ] 1.1 Verificar se data_coleta ja existe no CSV\n- [ ] 1.2 Se nao existir, adicionar campo data_coleta com formato YYYY-MM-DD\n- [ ] 1.3 Testar coleta e verificar dados\n\n**TESTE:** Abrir inteligencia_guerra_*.csv e verificar coluna data_coleta\n\n**DEPENDENCIES:** Nenhuma","labels":["radar-guerra","coleta","backend","priority-high"]}
) > issue1.json
gh api repos/%REPO%/issues -X POST --input issue1.json
del issue1.json
echo.

REM ========== ISSUE 2 - Processamento HTML ==========
echo [2] Criando Issue 2 + Sub-tasks...
(
echo {"title":"[Task 2] Fase 2: get_war_radar_data() - processar todos arquivos por data","body":"**OBJETIVO:** Modificar get_war_radar_data() para processar TODOS os arquivos por data.\n\n**ARQUIVOS:** src/html_generator.py (get_war_radar_data, generate_war_radar_html)\n\n**SUB-TASKS:**\n- [ ] 2.1 Modificar get_war_radar_data() para ler todos arquivos inteligencia_guerra_*\n- [ ] 2.2 Extrair data_coleta do CSV e adicionar campo 'date' em cada jogador\n- [ ] 2.3 Atualizar generate_war_radar_html para usar data-date\n\n**DEPENDENCIES:** Task 1\n\n**TESTE:** Gerar HTML e verificar data-date em cada .rd-player","labels":["radar-guerra","html-generator","backend","priority-high"]}
) > issue2.json
gh api repos/%REPO%/issues -X POST --input issue2.json
del issue2.json
echo.

REM ========== ISSUE 3 - Frontend ==========
echo [3] Criando Issue 3 + Sub-tasks...
(
echo {"title":"[Task 3] Fase 3: selectWarDay() - atualizar posicao do clan","body":"**OBJETIVO:** Revisar selectWarDay() para atualizar posicao do clan no cabecalho.\n\n**ARQUIVOS:** index.html (JavaScript selectWarDay()), src/html_generator.py\n\n**SUB-TASKS:**\n- [ ] 3.1 Garantir que cada .rd-player tem data-date={data_coleta}\n- [ ] 3.2 Modificar selectWarDay() para atualizar posicao do clan no cabecalho\n- [ ] 3.3 Adicionar indicador visual do dia selecionado\n\n**DEPENDENCIES:** Task 2\n\n**TESTE:** Clicar em diferentes dias e verificar mudanca na posicao do clan","labels":["radar-guerra","frontend","javascript","priority-high"]}
) > issue3.json
gh api repos/%REPO%/issues -X POST --input issue3.json
del issue3.json
echo.

REM ========== ISSUE 4 - Testes ==========
echo [4] Criando Issue 4 + Sub-tasks...
(
echo {"title":"[Task 4] Fase 4: Testes - Calendario interativo","body":"**OBJETIVO:** Testar clique no calendario e verificar decks por data.\n\n**ARQUIVOS:** index.html\n\n**SUB-TASKS:**\n- [ ] 4.1 Abrir index.html no navegador\n- [ ] 4.2 Clicar em cada dia do calendario\n- [ ] 4.3 Verificar que decks aparecem corretamente\n- [ ] 4.4 Validar data-date em cada .rd-player\n- [ ] 4.5 Verificar filtro por data funciona\n\n**DEPENDENCIES:** Tasks 2 e 3\n\n**TESTE MANUAL:** Abrir navegador, navegar Radar Guerra, clicar em cada dia","labels":["radar-guerra","teste","qa","priority-high"]}
) > issue4.json
gh api repos/%REPO%/issues -X POST --input issue4.json
del issue4.json
echo.

REM ========== ISSUE 5 - TOP Global ==========
echo [5] Criando Issue 5 + Sub-tasks...
(
echo {"title":"[Task 5] TOP Global - Limitar top 3 por clan","body":"**OBJETIVO:** Diferenciar visualizacao - TOP Global = top 3, Contas = todos.\n\n**ARQUIVO:** src/html_generator.py (get_war_radar_data)\n\n**SUB-TASKS:**\n- [ ] 5.1 Modificar get_war_radar_data() para detectar mode (top-global vs my-war)\n- [ ] 5.2 Se mode=top-global, limitar a 3 players por clan\n- [ ] 5.3 Se mode=my-war (contas), mostrar todos os dados\n- [ ] 5.4 Testar visualizacao TOP Global\n- [ ] 5.5 Testar contas\n\n**ESTRUTURA:**\n- Conta Principal (#2QR292P): Dados Completos\n- Conta Secundaria (#2220UQQ0UU): Dados Completos\n- TOP Global: Apenas top 3 por clan\n\n**DEPENDENCIES:** Task 2\n\n**TESTE:** Validar visualizacoes diferentes entre TOP Global e Contas","labels":["radar-guerra","performance","backend"]}
) > issue5.json
gh api repos/%REPO%/issues -X POST --input issue5.json
del issue5.json
echo.

echo === Concluido! Verifique: https://github.com/%REPO%/issues ===
echo.
pause
