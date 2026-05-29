@echo off
cd /d "%~dp0.."
REM Atualizar issues com detalhes completos (labels, milestones, observacoes de QA, etc)
REM Baseado no plano task_radar_guerra_v2.md

echo ============================================
echo  Atualizando Issues no GitHub CLI (gh)
echo  Adicionando Observacoes Tecnicas de QA
echo ============================================
echo.

set REPO=GilvanS/historico-clash-roayle

REM ===== Issue 6 - Task 1 =====
echo [1/5] Atualizando Issue 6 - Task 1 (data_coleta no CSV)...
gh api repos/%REPO%/issues/6 -X PATCH ^
  -f title="[Task 1] data_coleta no CSV - Revisar collect_river_race_full.py" ^
  -f body="## Descricao
Revisar collect_river_race_full.py para garantir que salva data_coleta em cada linha do CSV. O campo data_coleta deve ter formato YYYY-MM-DD para identificar quando cada jogador lutou.

> [!WARNING]
> **Observacao de QA (Resiliencia de Datas)**:
> Identificamos que o coletor de top decks (collect_war_top_decks.py) salva a data como DD/MM/YYYY, enquanto a inteligencia de guerra usa YYYY-MM-DD. Precisamos garantir a unificacao e normalizacao das datas para o formato ISO YYYY-MM-DD em todos os coletores, evitando falhas de sincronia na renderizacao do calendario interativo.

## Motivacao
Cada linha do CSV deve ter o campo data_coleta indicando a data da coleta. Isso permitira filtrar decks por dia especifico no calendario de guerra.

## Arquivos Envolvidos
- src/collect_river_race_full.py (script de coleta)
- src/collect_war_top_decks.py (coletor top decks)
- src/data_clan/inteligencia_guerra_*.csv (arquivos de inteligencia)

## Teste
Verificar arquivo inteligencia_guerra_*.csv se tem coluna data_coleta com formato YYYY-MM-DD.

## Checklist
- [ ] Abrir CSV e verificar coluna data_coleta
- [ ] Se nao existir, modificar collect_river_race_full.py
- [ ] Unificar formato de datas do collect_war_top_decks.py para YYYY-MM-DD
- [ ] Testar coleta e verificar dados atualizados

## Prioridade: HIGH" ^
  -f labels[]="radar-guerra" -f labels[]="backend" -f labels[]="coleta-dados"
echo.

REM ===== Issue 7 - Task 2 =====
echo [2/5] Atualizando Issue 7 - Task 2 (get_war_radar_data)...
gh api repos/%REPO%/issues/7 -X PATCH ^
  -f title="[Task 2] get_war_radar_data() - Processar todos arquivos por data" ^
  -f body="## Descricao
Modificar get_war_radar_data() em html_generator.py para processar TODOS os arquivos de inteligencia_guerra_* por data, nao apenas o mais recente.

> [!CAUTION]
> **Observacao de QA (Bug do Filtro de Maio/2026)**:
> Encontramos um bug critico na linha 4136 do html_generator.py, onde o filtro \`and '_2026_05_' not in f\` descarta incorretamente os arquivos validos de maio de 2026. Esse filtro DEVE ser removido. Ademais, a funcao get_war_radar_data(target_date) deve aceitar uma data especifica e tratar as datas de forma resiliente tanto para hifen quanto para underline (YYYY_MM_DD vs YYYY-MM-DD).

## Motivacao
Adicionar campo data_coleta em cada jogador processado do CSV. Agregar dados por data ao inves de usar so o arquivo mais recente. Permite filtrar decks por dia especifico.

## Arquivos Envolvidos
- src/html_generator.py (funcao get_war_radar_data)
- src/html_generator.py (funcao generate_war_radar_html)

## Dependencies
- Issue #6 (Task 1) - Precisa do data_coleta no CSV

## Teste
Gerar novo HTML e verificar que cada .rd-player tem data-date correto.

## Checklist
- [ ] Modificar get_war_radar_data() para ler todos arquivos
- [ ] Remover o filtro limitador de data _2026_05_
- [ ] Extrair data_coleta de cada linha do CSV
- [ ] Adicionar campo 'date' em cada jogador (normalizado como YYYY_MM_DD)
- [ ] Atualizar generate_war_radar_html para usar data-date
- [ ] Testar geracao do HTML

## Prioridade: HIGH" ^
  -f labels[]="radar-guerra" -f labels[]="backend" -f labels[]="html-generator"
echo.

REM ===== Issue 8 - Task 3 =====
echo [3/5] Atualizando Issue 8 - Task 3 (selectWarDay e data-date)...
gh api repos/%REPO%/issues/8 -X PATCH ^
  -f title="[Task 3] selectWarDay() - Atualizar posicao do clan no cabecalho" ^
  -f body="## Descricao
Revisar funcao selectWarDay() para atualizar tambem posicao do clan no cabecalho quando dia e selecionado.

> [!IMPORTANT]
> **Observacao de QA (Bug de Visibilidade no JS)**:
> A funcao selectWarDay() no index.html usa querySelectorAll('.rd-player[style=\"block\"]') para gerenciar os jogadores visiveis de cada dia. Nos navegadores, o style.display block e renderizado como \`display: block;\` (com ponto e virgula), fazendo com que esse seletor CSS falhe silenciosamente e oculte os jogadores. A busca de visibilidade no JS deve ser alterada para validar o atributo \`data-date\` correspondente e gerenciar a visibilidade comparando \`style.display !== 'none'\`.

## Motivacao
Quando usuario clica em um dia do calendario, deve mostrar a posicao do clan naquele dia especifico, alem de filtrar os jogadores.

## Arquivos Envolvidos
- index.html (JavaScript funcao selectWarDay())
- src/html_generator.py (geracao do calendario)

## Dependencies
- Issue #7 (Task 2) - Precisa dos dados por data

## Teste
Clicar em diferentes dias e verificar mudanca na posicao do clan exibida.

## Checklist
- [ ] Revisar funcao selectWarDay() atual
- [ ] Corrigir seletor CSS de display de block no JS para comparacao explicita
- [ ] Identificar onde atualizar posicao do clan
- [ ] Adicionar logica para buscar e renderizar a posicao/fama por data
- [ ] Adicionar classe active-day no CSS para realce visual do dia selecionado
- [ ] Testar clique em cada dia

## Prioridade: MEDIUM" ^
  -f labels[]="radar-guerra" -f labels[]="frontend" -f labels[]="javascript"
echo.

REM ===== Issue 9 - Task 4 =====
echo [4/5] Atualizando Issue 9 - Task 4 (Testar calendario)...
gh api repos/%REPO%/issues/9 -X PATCH ^
  -f title="[Task 4] Testar calendario - Decks aparecem por data" ^
  -f body="## Descricao
Testar clique em cada dia do calendario e verificar que decks aparecem corretamente para cada data.

> [!TIP]
> **Observacao de QA (Plano de Testes Visual e Regressao)**:
> Como especialista ISTQB, a validacao deve seguir a piramide de testes. Focar no feedback ativo do calendario (.active-day com bordas #00ffcc e sombras fluidas no hover) e garantir que a alternancia dinamica de abas mantendo o dia selecionado persista corretamente, prevenindo qualquer regressao visual no painel.

## Motivacao
Validar que ao selecionar um dia especifico no calendario, os decks mostrados sao os decks usados naquele dia, permitindo ver a evolucao dos decks ao longo da guerra.

## Testes a realizar
1. Abrir index.html no navegador
2. Navegar ate secao Radar de Guerra
3. Clicar em cada dia do calendario
4. Verificar que decks aparecem corretamente para cada data
5. Verificar que data-date esta presente em cada .rd-player

## Dependencies
- Issues #7 e #8 (Tasks 2 e 3)

## Checklist
- [ ] Abrir index.html no navegador
- [ ] Clicar em cada dia do calendario
- [ ] Verificar que decks aparecem corretamente
- [ ] Validar data-date em cada .rd-player
- [ ] Verificar filtro por data funciona de forma pixel-perfect

## Prioridade: HIGH" ^
  -f labels[]="radar-guerra" -f labels[]="teste" -f labels[]="qa"
echo.

REM ===== Issue 10 - Task 5 =====
echo [5/5] Atualizando Issue 10 - Task 5 (TOP Global)...
gh api repos/%REPO%/issues/10 -X PATCH ^
  -f title="[Task 5] TOP Global - Limitar top 3 por clan" ^
  -f body="## Descricao
TOP Global deve mostrar apenas top 3 jogadores de cada clan para performance. Conta principal e secundaria mostram todos os dados.

> [!NOTE]
> **Observacao de QA (Otimizacao de Performance)**:
> Validar que os dados de TOP Global permanecam embutidos sob demanda sem sobrecarregar o Master Cache do backend, aplicando o limite de no maximo 3 jogadores por clan, enquanto as contas principal e secundaria mantem exibicao completa e detalhada de todas as lutas, otimizando o consumo de memoria do generator.

## Motivacao
Diferenciar logica: TOP_GLOBAL = top 3 por clan (performance), #2QR292P e #2220UQQ0UU = todos os dados (analise completa).

## Arquivos Envolvidos
- src/html_generator.py (get_war_radar_data - mode top-global)

## Dependencies
- Issue #7 (Task 2) - Precisa de processar arquivos por data

## Checklist
- [ ] Modificar get_war_radar_data() para detectar mode
- [ ] Se mode=top-global, limitar a 3 players por clan
- [ ] Se mode=my-war (contas), mostrar todos os dados completos
- [ ] Testar visualizacao TOP Global (3 players)
- [ ] Testar contas (todos os dados)

## Prioridade: MEDIUM" ^
  -f labels[]="radar-guerra" -f labels[]="backend" -f labels[]="performance"
echo.

echo ============================================
echo Concluido! Issues atualizadas com detalhes.
echo Verifique: https://github.com/%REPO%/issues
echo ============================================
pause
