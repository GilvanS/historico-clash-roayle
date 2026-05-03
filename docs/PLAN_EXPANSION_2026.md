# 📋 Plano de Expansão de Inteligência - Clash Royale Analytics 2026

## 🎯 Objetivo
Transformar o histórico de batalhas em uma central completa de inteligência competitiva e gestão estratégica de recursos.

## 🚀 Sprint Especial: 5 Dias (Prioridade Máxima)
Vamos focar nos itens que trazem retorno imediato e resolvem os problemas de sincronização.

| Dia | Foco | Entregável |
| :--- | :--- | :--- |
| **Dia 1** | **Ciclo de Baús** | Coleta de `/upcomingchests` e card visual no Dashboard. |
| **Dia 2** | **Meta Brasil** | Ranking Top 100 Local e estatística de cartas mais usadas. |
| **Dia 3** | **Otimização de Sync** | Fim dos conflitos de Git e garantia de atualização Web/Local. |
| **Dia 4** | **Guerra de Clãs** | Inteligência sobre o clã oponente e previsão de dificuldade. |
| **Dia 5** | **Copiador de Decks** | Botão para copiar decks Pro e polimento final do design. |

---

## 📅 Detalhamento das Fases

### 🛡️ Fase 1: Ciclo de Recompensas (Dia 1)
- **Endpoint**: `/upcomingchests`
- **Ação**: Implementar script de coleta para mapear os próximos 10 baús e baús especiais.
- **Visualização**: Novo card no Dashboard: "Previsão de Tesouros".
- **Impacto**: Saber quando gastar chaves ou esperar para abrir baús raros.

### 📊 Fase 2: Auditoria e Inteligência de Guerra (Dia 4)
- **Endpoints**: `/riverracelog`, `/currentriverrace`
- **Ação**: Consolidar pontuação semanal e cruzar com o ranking global/local.
- **Diferencial**: Previsão de dificuldade do confronto de guerra.

### ⚔️ Fase 3: Análise de Matchmaking (Longo Prazo)
- **Ação**: Cruzar o nível das cartas do oponente com a média do seu deck.

### 📈 Fase 4: Inteligência de Mercado (Meta Local - Dia 2)
- **Endpoint**: `/locations/57000038/rankings/pathoflegend/players` (Brasil)
- **Ação**: Extrair o Top 100 do Brasil semanalmente.
- **Visualização**: Aba "Tendências Brasil" (cartas mais usadas pelos pro-players locais).

### 🏆 Fase 5: Copiador de Decks (Dia 5)
- **Ação**: Link direto `clashroyale://copyDeck?deck=...` para os decks vencedores.

---

## 🛠️ Requisitos Técnicos & Fluxo de Dados
- **Python**: Expansão do coletor para suportar novos endpoints.
- **Git Sync**: Ajustar GitHub Actions para evitar conflitos com a extração local.
- **VBA**: Integrar novos CSVs de Baús e Meta no Excel.

---
**Status atual**: 🟡 Executando Sprint 5 Dias | ⚪ Concluído
