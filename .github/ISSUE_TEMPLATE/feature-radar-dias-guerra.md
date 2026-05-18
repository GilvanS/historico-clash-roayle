# [FEATURE] Melhorar visualização dos Dias de Guerra no Radar

## Problem Statement

O calendário atual dos dias de guerra no radar do projeto Historico Clash Royale apresenta limitações visuais que dificultam a análise rápida do desempenho durante a River Race. Os usuários precisam de uma interface mais intuitiva que exiba: posicionamento diário (1º, 2º, 3º lugar), fama acumulada por dia, status dos barcos (completo/em reparo), e timeline visual horizontal - elementos presentes na referência `diasdeguerra.jpg` mas ausentes na implementação atual.

A solução deve manter compatibilidade com o sistema multi-conta existente (Conta Principal #2QR292P e Conta Secundária #2220UQQ0UU) que utiliza arquivo unificado `inteligencia_guerra_YYYY-MM-DD.csv` com coluna `player_tag_conta`.

## Solution

Melhorar a experiência visual do calendário de guerra no componente Radar, implementando:
- Timeline horizontal com dias da semana (Quinta a Domingo)
- Indicadores de ranking diário (🥇🥈🥉) com nome do jogador e medals
- Cards informativos por dia com fame e status de barcos
- Layout responsivo para mobile
- Persistência de seleção de dia no localStorage

## User Stories

1. Como jogador, quero ver os dias de guerra em formato de timeline visual, para entender o progresso da corrida e identificar rapidamente em quais dias meu clã performou melhor
2. Como líder de clã, quero indicadores claros de posição (🥇🥈🥉) para cada dia, para saber quais jogadores contribuíram mais em cada fase da guerra
3. Como estrategista, quero ver a fama acumulada por dia, para entender a evolução do desempenho e comparar com clãs concorrentes
4. Como analista, quero poder clicar em um dia específico para filtrar os decks usados naquele período, para analisar quais estratégias foram mais eficazes
5. Como gerente de clã, quero indicadores visuais de participação (verde=lutou, cinza=não lutou) em cada dia, para identificar jogadores inativos rapidamente
6. Como historiador, quero histórico visual das últimas guerras, para comparar desempenho entre semanas e identificar padrões sazonais
7. Como competidor, quero comparar minha posição com competidores nos mesmos dias, para entender a rivalidade e calibrar expectativas
8. Como jogador, quero ver o status dos barcos (completo/reparando) por dia, para entender o progresso da corrida e planejar ataques
9. Como usuário mobile, quero layout responsivo que funcione bem em telas pequenas, para consultar dados durante deslocamentos
10. Como usuário frequente, quero que minha seleção de dia seja mantida ao trocar entre contas, para não perder contexto ao alternar entre Conta Principal e Secundária

## Implementation Decisions

### Módulos a construir/modificar

| Módulo | Responsabilidade | Arquivo |
|--------|-----------------|---------|
| WarCalendarRenderer | Componente de renderização do calendário com timeline | `src/html_generator.py` |
| WarDaySelector | Lógica de seleção e filtragem de dia | `src/html_generator.py` |
| BoatStatusMapper | Mapeamento de status de barcos para ícone visual | `src/html_generator.py` |
| CalendarStyles | Estilos CSS do novo calendário | `index.html` (seção `<style>`) |
| CalendarJS | JavaScript para interatividade e persistência | `index.html` (seção `<script>`) |

### Interfaces a modificar

**`src/html_generator.py`**:
```python
def generate_war_radar_html()  # Adicionar chamada ao novo componente de calendário
def get_war_calendar_data(player_tag: str) -> List[Dict]  # Retornar dados por dia com ranking
def _generate_war_calendar_html(data: List[Dict]) -> str  # Renderizar timeline visual
def _get_daily_ranking(clan_data: Dict, day_index: int) -> List[Dict]  # Calcular ranking diário
def _get_boat_status(player_tag: str, day_index: int) -> str  # Obter status de barco
```

**`index.html` (JavaScript)**:
```javascript
function selectWarDay(dayIndex)  // Filtrar decks por dia selecionado
function switchRadarTab(account)  // Navegação entre pri/sec mantendo seleção
function persistDaySelection()  // Salvar seleção no localStorage
function restoreDaySelection()  // Restaurar seleção ao carregar página
```

### Decisões técnicas

1. **Arquitetura**: Manter sistema de tabs existente (pri/sec), adicionar sub-tab de dias dentro de cada conta
2. **Layout**: Usar CSS Grid com `grid-template-columns: repeat(5, 1fr)` para 5 dias (Terça a Domingo)
3. **Responsividade**: Media queries para `max-width: 768px` com scroll horizontal no timeline
4. **Persistência**: `localStorage.setItem('selectedWarDay', dayIndex)` e restauração no `DOMContentLoaded`
5. **Performance**: Cache de dados de guerra em memória, atualização a cada coleta (30min)
6. **Escape de chaves**: JavaScript inline usa `{{` para escape de `{{` em f-strings Python (convenção do projeto)
7. **Coluna player_tag_conta**: Filtrar dados corretamente para cada conta no arquivo unificado

### Schema de dados (não alterar)

```csv
# Estrutura existente em inteligencia_guerra_YYYY-MM-DD.csv
data_coleta, player_tag_conta, clan_posicao, clan_nome, clan_tag, clan_fame,
player_posicao, player_nome, player_tag, player_fame, decks_usados, boat_attacks,
deck_1, deck_1_tipo, deck_2, deck_2_tipo, deck_3, deck_3_tipo, deck_4, deck_4_tipo
```

## Testing Decisions

### Critérios de validação (Definition of Done)

1. **Visual**: Timeline horizontal exibe 5 dias (Terça, Quarta, Quinta, Sexta, Sábado, Domingo)
2. **Ranking**: Cards mostram posição (🥇🥈🥉) com nome do jogador e medals para cada dia
3. **Fama**: Exibição correta da fame acumulada por dia em formato legível
4. **Filtro**: Seleção de dia filtra corretamente os decks exibidos
5. **Contas**: Troca entre pri/sec mantém dados específicos de cada conta
6. **Persistência**: Seleção de dia sobrevive a reload da página
7. **Mobile**: Layout responsivo sem quebra em telas de 375px de largura
8. **Performance**: Renderização do calendário completa em < 500ms

### Módulos a testar

- `get_war_calendar_data()`: Verificar dados retornados para cada conta
- `_generate_war_calendar_html()`: Verificar HTML gerado corresponde ao design
- `selectWarDay()`: Verificar filtros aplicados corretamente
- `switchRadarTab()`: Verificar manutenção de seleção entre contas
- Responsividade via browser DevTools (toggle device toolbar)

### Testes de regressão

- Sistema de tabs pri/sec continua funcionando
- Filtro por `player_tag_conta` mantém comportamento existing
- Arquivo CSV não é modificado pela visualização

## Out of Scope

- Modificar scripts de coleta de dados (`collect_river_race_full.py`)
- Alterar formato do arquivo `inteligencia_guerra_*.csv`
- Adicionar funcionalidade de edição de dados da guerra
- Implementar notificações push para novos dados
- Adicionar animação de carregamento (skeleton) - manter loading state atual

## Further Notes

### Prior Art
- Componente existente em `rd-calendar-container` com estilos `.rd-calendar-*`
- Sistema de tabs pri/sec implementado em `switchRadarTab()`
- Arquivos de dados: `inteligencia_guerra_YYYY-MM-DD.csv` e `status_barcos_*.csv`

### Context
- **Branch**: `feature/radar-dias-guerra`
- **Contas**: `#2QR292P` (Principal, Tropa Do Bruxo) e `#2220UQQ0UU` (Secundária, BLACK「DR4GON)
- **Skill do projeto**: `.agents/skills/historico-clash-roayle/SKILL.md`
- **Referência visual**: `diasdeguerra.jpg`

### Glossário do domínio
- **Fame**: Pontuação de contribuição de cada jogador na River Race
- **Boat Battle**: Batalha contra barco (tipo de batalha na guerra)
- **River Race**: Sistema de corrida de clãs do Clash Royale
- **War Day**: Dia de guerra (Quinta a Domingo)
- **Decks**: Combinações de 8 cartas usadas em batalhas