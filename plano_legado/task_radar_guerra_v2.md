# Task: Radar de Guerra v2 - Histórico de Batalhas por Dia

## Tracking de Progresso

| # | Task | Status | Responsável |
|---|------|--------|--------------|
| 1 | Revisar collect_river_race_full.py - data_coleta | ✅ | Antigravity |
| 2 | Modificar get_war_radar_data() - processar todos por data | ⏳ | - |
| 3 | Revisar selectWarDay() - atualizar posição do clã | ⏳ | - |
| 4 | Testar clique no calendário - decks por data | ⏳ | - |
| 5 | TOP Global - top 3 por clã (contas mostram todos) | ⏳ | - |

## Objetivo
Consultar e salvar dados das lutas durante a guerra (decks usados, posição do clã) para Conta Principal, Conta Secundária e TOP Global, permitindo visualização histórica ao clicar no calendário.

## Estrutura de Dados

| Fonte | Top 3 por Clã | Dados Completos |
|-------|---------------|-----------------|
| **Conta Principal** | ✅ Sempre | ✅ Sempre (independentemente de posição) |
| **Conta Secundária** | ✅ Sempre | ✅ Sempre (independentemente de posição) |
| **TOP Global** | ✅ Top 3 | ❌ Apenas top 3 para manter performance |

## 🔍 Observações Técnicas e Análise de QA (Adicionado em 20/05/2026)

Durante a revisão estática do código, identificamos três pontos críticos que precisam de correção direta nesta task:

1. **Bug no Filtro de Arquivos (Backend)**: Em `src/html_generator.py` (linha 4136), o filtro `and '_2026_05_' not in f` descarta incorretamente todos os arquivos válidos de maio de 2026. Esse filtro deve ser removido.
2. **Inconsistência de Datas**: Os arquivos em `src/data_clan/` alternam nomes entre hífen (`inteligencia_guerra_2026-05-18.csv`) e underline (`inteligencia_guerra_2026_05_01.csv`). Devemos normalizar todas as chaves e caminhos internamente usando a regex `\d{4}[-_]\d{2}[-_]\d{2}` para o formato unificado `YYYY_MM_DD`.
3. **Bug de Visibilidade no JavaScript (Frontend)**: O seletor da função `selectWarDay()` faz buscas por `.rd-player[style="block"]` para ocultar jogadores inativos de outros dias. Como os navegadores renderizam a string de estilo como `display: block;`, a busca falha silenciosamente. A lógica deve ser alterada para validar o atributo `data-date` correspondente e gerenciar a visibilidade comparando `style.display !== 'none'`.

---

## Plano de Implementação

### Fase 1: Coleta de Dados (API + CSV)

- [x] **1.1** - Revisar `collect_river_race_full.py` para garantir que salva data_coleta em cada linha do CSV
- [x] **1.2** - Criar script de coleta para TOP Global (já parcialmente implementado em `collect_war_top_decks.py`)
- [x] **1.3** - Garantir que dados de Account Principal e Secundária são salvos com `player_tag_conta` e `data_coleta`

### Fase 2: Processamento no HTML Generator

- [ ] **2.1** - Modificar `get_war_radar_data(target_date)` para aceitar a data alvo e processar os arquivos de inteligencia_guerra_* correspondentes
- [ ] **2.2** - Adicionar campo `data_coleta` em cada jogador (normalizado no formato `YYYY_MM_DD`)
- [ ] **2.3** - Modificar filtragem: remover o filtro impeditivo `_2026_05_` do `html_generator.py`

### Fase 3: Frontend (HTML + JS)

- [ ] **3.1** - Garantir que cada elemento `.rd-player` tenha o atributo `data-date="{data_coleta}"` normalizado
- [ ] **3.2** - Refatorar a função JavaScript `selectWarDay(tabId, dateStr, element)` para usar correspondência robusta por atributo e atualizar a posição/fama do clã dinamicamente no cabeçalho superior
- [ ] **3.3** - Adicionar o indicador de estilo visual `.active-day` (CSS com destaque em `#00ffcc` e transições suaves) ao dia do calendário ativo

### Fase 4: Testes e Validação

- [ ] **4.1** - Testar clique interativo em todos os dias disponíveis no calendário
- [ ] **4.2** - Verificar integridade visual e se os decks corretos aparecem sob cada aba de conta por data
- [ ] **4.3** - Validar se a fama e a posição do clã atualizam em tempo real na barra de resumo superior ao clicar em cada dia

## Arquivos Envolvidos

| Arquivo | Função |
|---------|--------|
| `src/collect_river_race_full.py` | Coleta dados de guerra das contas |
| `src/collect_war_top_decks.py` | Coleta TOP Global |
| `src/html_generator.py` | Gera HTML com dados processados |
| `index.html` | Frontend com JavaScript |

## Prioridade

**ALTA** - Sem isso, o calendário interativo não funciona corretamente para ver decks históricos.

---

*Atualizado em: 20/05/2026*