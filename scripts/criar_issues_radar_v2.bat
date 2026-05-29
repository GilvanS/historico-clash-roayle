@echo off
cd /d "%~dp0.."
REM Radar de Guerra v2 - Issues Baseadas no Plano Completo
REM Plano: plano_legado/task_radar_guerra_v2.md

set REPO=GilvanS/historico-clash-roayle

echo.
echo ============================================
echo  Radar de Guerra v2 - Criando Issues
echo  Baseado no plano task_radar_guerra_v2.md
echo ============================================
echo.

REM ===== Issue 1: Fase 1 - Coleta de Dados =====
echo [1/5] Criando Issue 1: Fase 1 - Coleta de Dados...
gh api repos/%REPO%/issues -X POST ^
  -f title="[Task 1] Fase 1: Coleta de Dados - data_coleta no CSV" ^
  -f body="## Objetivo
Revisar collect_river_race_full.py para garantir que salva data_coleta em cada linha do CSV.

## Estrutura de Dados
| Fonte | Top 3 por Cla | Dados Completos |
|-------|---------------|-----------------|
| Conta Principal | Sempre | Sempre |
| Conta Secundaria | Sempre | Sempre |
| TOP Global | Top 3 | Apenas top 3 |

## Fase 1: Coleta de Dados (API + CSV)

### 1.1 - Revisar collect_river_race_full.py
- Garantir que salva data_coleta em cada linha do CSV
- Formato: YYYY-MM-DD

### 1.2 - Script TOP Global
- Ja parcialmente implementado em collect_war_top_decks.py

### 1.3 - Dados por Conta
- Garantir que dados de Account Principal (#2QR292P) e Secundaria (#2220UQQ0UU) sao salvos com:
  - player_tag_conta
  - data_coleta

## Arquivos Envolvidos
- src/collect_river_race_full.py (Coleta dados de guerra das contas)
- src/collect_war_top_decks.py (Coleta TOP Global)
- src/data_clan/inteligencia_guerra_*.csv

## Teste
Verificar arquivo inteligencia_guerra_*.csv se tem coluna data_coleta com formato YYYY-MM-DD.

## Prioridade: ALTA" ^
  -f labels[]="radar-guerra" -f labels[]="coleta" -f labels[]="backend" -f labels[]="priority-high"
echo.

REM ===== Issue 2: Fase 2 - Processamento HTML =====
echo [2/5] Criando Issue 2: Fase 2 - Processamento HTML...
gh api repos/%REPO%/issues -X POST ^
  -f title="[Task 2] Fase 2: Processamento HTML - get_war_radar_data()" ^
  -f body="## Objetivo
Modificar get_war_radar_data() para processar TODOS os arquivos de inteligencia_guerra_* por data, nao apenas o mais recente.

## Fase 2: Processamento no HTML Generator

### 2.1 - Processar todos arquivos por data
- Modificar get_war_radar_data() para ler todos arquivos
- Nao usar apenas o mais recente

### 2.2 - Adicionar campo data_coleta
- Processar data_coleta do CSV em cada jogador
- Extrair e formatar corretamente

### 2.3 - Modificar filtragem
- Agregar dados por data ao inves de arquivo unico
- Permitir filtragem por dia especifico

## Arquivos Envolvidos
- src/html_generator.py (get_war_radar_data)
- src/html_generator.py (generate_war_radar_html)

## Dependencies
- Task 1 (Issue #1) - Precisa do data_coleta no CSV

## Teste
Gerar novo HTML e verificar que cada .rd-player tem data-date correto.

## Prioridade: ALTA" ^
  -f labels[]="radar-guerra" -f labels[]="html-generator" -f labels[]="backend" -f labels[]="priority-high"
echo.

REM ===== Issue 3: Fase 3 - Frontend =====
echo [3/5] Criando Issue 3: Fase 3 - Frontend JavaScript...
gh api repos/%REPO%/issues -X POST ^
  -f title="[Task 3] Fase 3: Frontend - selectWarDay() e data-date" ^
  -f body="## Objetivo
Garantir que cada .rd-player tem data-date correto e funcao selectWarDay() atualiza posicao do clan.

## Fase 3: Frontend (HTML + JS)

### 3.1 - Garantir data-date em cada jogador
- Garantir que cada .rd-player tem data-date={data_coleta} correto
- Renderizar no HTML gerado

### 3.2 - Revisar selectWarDay()
- Atualizar posicao do clan no cabecalho quando dia e selecionado
- Mostrar posicao do clan naquele dia especifico

### 3.3 - Indicador visual
- Adicionar indicador visual de qual dia esta selecionado no calendario

## Arquivos Envolvidos
- src/html_generator.py (geracao do calendario)
- index.html (JavaScript selectWarDay())

## Dependencies
- Task 2 (Issue #2) - Precisa dos dados processados por data

## Teste
Verificar no HTML se cada .rd-player tem data-date correto.

## Prioridade: ALTA" ^
  -f labels[]="radar-guerra" -f labels[]="frontend" -f labels[]="javascript" -f labels[]="priority-high"
echo.

REM ===== Issue 4: Fase 4 - Testes =====
echo [4/5] Criando Issue 4: Fase 4 - Testes e Validacao...
gh api repos/%REPO%/issues -X POST ^
  -f title="[Task 4] Fase 4: Testes e Validacao - Calendario interativo" ^
  -f body="## Objetivo
Testar clique em cada dia do calendario e verificar que decks aparecem corretamente para cada data.

## Fase 4: Testes e Validacao

### 4.1 - Testar clique no calendario
- Abrir index.html no navegador
- Clicar em cada dia do calendario
- Verificar interacao funciona

### 4.2 - Verificar decks por data
- Verificar que decks aparecem corretamente para cada data
- Validar que ao selecionar dia, mostra decks daquele dia

### 4.3 - Validar position/fame
- Validar que position/fame do clan atualiza corretamente
- Mostrar posicao do clan no dia selecionado

## Dependencies
- Tasks 2 e 3 (Issues #2 e #3)

## Teste Manual
1. Abrir index.html no navegador
2. Navegar ate secao Radar de Guerra
3. Clicar em cada dia do calendario
4. Verificar decks e posicoes

## Prioridade: ALTA" ^
  -f labels[]="radar-guerra" -f labels[]="teste" -f labels[]="qa" -f labels[]="priority-high"
echo.

REM ===== Issue 5: TOP Global vs Contas =====
echo [5/5] Criando Issue 5: TOP Global - Limite 3 por clan...
gh api repos/%REPO%/issues -X POST ^
  -f title="[Task 5] TOP Global vs Contas - Limite de players por clan" ^
  -f body="## Objetivo
Diferenciar visualizacao: TOP Global = top 3 por clan (performance), Contas = todos os dados.

## Estrutura de Dados (reforco)
| Fonte | Top 3 por Cla | Dados Completos |
|-------|---------------|-----------------|
| Conta Principal (#2QR292P) | Sempre | Sempre |
| Conta Secundaria (#2220UQQ0UU) | Sempre | Sempre |
| TOP Global | Top 3 | Apenas top 3 |

## Implementacao

### TOP Global
- Limitar a top 3 jogadores por clan
- Otimizar performance

### Contas Principal e Secundaria
- Mostrar todos os dados (independentemente de posicao)
- Permitir analise completa

## Arquivo Envolvido
- src/html_generator.py (get_war_radar_data - mode top-global vs my-war)

## Dependencies
- Task 2 (Issue #2)

## Teste
1. Verificar que TOP Global tem so 3 players por clan
2. Verificar que contas principais tem todos os dados
3. Validar alternancia entre visualizacoes

## Prioridade: MEDIUM" ^
  -f labels[]="radar-guerra" -f labels[]="performance" -f labels[]="backend"
echo.

echo ============================================
echo Concluido! Verifique: https://github.com/%REPO%/issues
echo ============================================
pause
