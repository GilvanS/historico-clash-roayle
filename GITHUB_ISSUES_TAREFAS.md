# Registro de Tarefas Executadas - Issues do GitHub

Este arquivo contém o detalhamento técnico de todas as tarefas de reengenharia e correções efetuadas no projeto Clash Royale. Estes templates estão formatados no padrão de **Issues do GitHub**, prontos para serem copiados ou usados como referência técnica.

---

## 🛠️ Issue 1: Reengenharia de Dados & Migração Histórica dos CSVs de Guerra
* **Título**: `[Dados] Reengenharia de Dados: Unificação do Histórico de Guerra e Status de Barcos`
* **Tipo**: `Refactoring / Data Engineering`
* **Status**: `Concluída`
* **Tags**: `data-engineering`, `refactoring`, `idempotency`

### 📝 Descrição da Issue
Atualmente, o pipeline gerava dezenas de pequenos arquivos diários individuais no formato `inteligencia_guerra_*.csv` e `status_barcos_*.csv`. Isso causava fragmentação, desperdício de espaço no repositório e alto custo computacional de `glob.glob` para listagem no backend. Esta issue resolve o problema consolidando todo o histórico acumulado em dois arquivos CSV unificados mestres.

### 📋 Checklist de Tarefas Efetuadas
- [x] **Análise de Leiautes Antigos**: Mapeamento dos formatos de dados antigos (incluindo dados anteriores a 17 de maio que não continham tags de jogadores/clãs).
- [x] **Criação do Script de Migração (`src/migrate_war_data.py`)**:
  * Normalização de colunas antigas e preenchimento inteligente de Tags de clã/jogador ausentes baseando-se em mapeamentos conhecidos.
  * Cálculo da coluna lógica `rodada_guerra` (`Dia 1` a `Dia 4`) aplicando estritamente a regra de reset lógico das 07:00:00 da manhã.
  * Agrupamento e processamento de 358 registros históricos de guerra e 90 registros de barcos.
- [x] **Geração dos CSVs Mestres na pasta `src/data_clan/`**:
  * `guerra_historico.csv` (101 KB, 358 registros consolidados)
  * `status_barcos_historico.csv` (6 KB, 90 registros consolidados)
- [x] **Limpeza Física**: Remoção das dezenas de CSVs diários legados para manter o repositório organizado e enxuto.

---

## 🔄 Issue 2: Ajuste e Robustez nos Scripts de Coleta (Idempotência e Caminhos Físicos)
* **Título**: `[Coletores] Correção de Diretórios Fantasmas e Implementação de Deduplicação Ativa nos Coletores`
* **Tipo**: `Bug / Optimization`
* **Status**: `Concluída`
* **Tags**: `collectors`, `idempotency`, `file-system`

### 📝 Descrição da Issue
Identificamos a geração de um diretório fantasma e redundante em `src/src/data_clan/` por conta de caminhos relativos frágeis (`'src/data_clan'`) durante a execução orquestrada a partir de subpastas. Além disso, execuções sucessivas do pipeline no mesmo dia podiam duplicar dados no histórico. Esta issue corrige os caminhos físicos absolutos e garante idempotência total das coletas diárias.

### 📋 Checklist de Tarefas Efetuadas
- [x] **Correção de Paths em `collect_river_race_full.py`**: Alteração do `DATA_DIR` relativo para um path físico absoluto baseado em `os.path.dirname(os.path.abspath(__file__))`.
- [x] **Implementação de Deduplicação Idempotente**:
  * O script agora calcula a data lógica lógico-operacional das 07:00:00.
  * Antes de salvar, ele carrega o histórico existente e remove registros da mesma data lógica lógica para aquele jogador/conta, mantendo apenas a coleta mais recente.
- [x] **Adequação do Coletor de Barcos (`collect_war_weekend.py`)**: Atualização para gravar de forma idempotente e direta no arquivo acumulado consolidado `status_barcos_historico.csv`.
- [x] **Limpeza do Diretório Fantasma**: Remoção física da pasta duplicada `src/src/` e todos os seus arquivos residuais.

---

## 📅 Issue 3: Restauração do Calendário de Guerra e Otimização do Dashboard
* **Título**: `[Dashboard] Restauração do Calendário da Conta Secundária e Leitura em Memória Otimizada`
* **Tipo**: `Frontend / Performance`
* **Status**: `Concluída`
* **Tags**: `dashboard`, `frontend`, `calendar`, `performance`

### 📝 Descrição da Issue
A aba da Conta Secundária no dashboard apresentava falhas de renderização no calendário horizontal de 4 dias. A causa era a ausência da tag do jogador durante a resolução de dados históricos de barcos. Adicionalmente, ler dezenas de arquivos físicos com `glob.glob` em tempo de execução de renderização gerava gargalo no gerador de HTML.

### 📋 Checklist de Tarefas Efetuadas
- [x] **Otimização do Gerador (`src/html_generator.py`)**: Modificação do método `get_war_calendar_data` para ler as datas e barcos diretamente em memória a partir de `status_barcos_historico.csv`.
- [x] **Correção da Tag de Rastreamento**: Passagem do argumento explícito `player_tag` para o calendário de guerra em `generate_war_radar_html`.
- [x] **Resolução do Clã Secundário**: Implementação de lógica para detectar a tag secundária `#2220UQQ0UU` e apontá-la corretamente para as estatísticas do clã `BLACK「DR4GON` (`_sec`), restabelecendo o calendário horizontal e a listagem de barcos.

---

## 🐛 Issue 4: Resolução da Corrupção do Dashboard (Bug da Fama Zerada no Barco)
* **Título**: `[Bug] Correção de Travamento de Abas HTML e Tratamento de Fama Zero no Início da Guerra`
* **Tipo**: `Bug / UI-UX`
* **Status**: `Concluída`
* **Tags**: `bug-fix`, `dashboard`, `clash-api`, `robustness`

### 📝 Descrição da Issue
O dashboard `index.html` travava a interatividade das abas no navegador (exceção JS silenciosa) e sumia com o calendário devido a uma falha catastrófica de fallback. No início da guerra (quinta-feira útil), quando a fama na API oficial é zero, o script de barcos descartava as informações da API e tentava buscar um fallback histórico. Como a secundária é nova, o fallback retornava vazio (`[]`), quebrando os dados estruturais do HTML.

### 📋 Checklist de Tarefas Efetuadas
- [x] **Correção de Condição de Fama em `collect_war_weekend.py`**: Ajuste do fluxo de fallback. Se a fama for zero e o histórico estiver vazio, o script agora preserva e grava os clãs reais válidos da API Clash Royale com fama zero.
- [x] **Execução e Consolidação das Contas**: Execução do pipeline mestre `python src/main_sync.py` de ponta a ponta com sucesso. Os dados de barcos de fama zero para a conta secundária foram gravados no CSV de forma limpa.
- [x] **Criação do Script de Validação de Integridade (`scratch/check_html_corruption.py`)**:
  * Análise sintática do `index.html` de 18.353 linhas.
  * Validação de fechamento correto de tags estruturais e presença de abas ativas para ambas as contas: conta principal (`account-tab-2QR292P`) na Linha 2204 e secundária (`account-tab-2220UQQ0UU`) na Linha 9693.
  * Atestado no relatório de diagnóstico (`scratch/corruption_report.txt`) que o HTML está 100% íntegro e reativo no navegador.
