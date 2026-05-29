# 🛠️ Resumo do Estado Atual: Clash Royale Analytics (Λ Яᄃ λ Ð Є)

Este documento descreve o que o projeto já realiza, os dados que ele gera e como você os visualiza, atualizado com a nova estrutura de 2026.

## 1. 📂 Onde os Dados são Gerados (Arquivos)
Atualmente, o pipeline unificado (`src/main_sync.py`) mantém os seguintes arquivos principais na pasta `src/data_csv_oficial/`:

*   **`oponentes_ano_2026.csv`**: O banco de dados principal de 2026. Contém cada batalha detalhada.
*   **`historico_completo_2023_2025.csv`**: Legado com mais de 2.000 batalhas preservadas.
*   **`clan_members.csv`**: Dados atualizados do seu clã (nível, troféus, atividade).
*   **`upcoming_chests.json`**: [NOVO] Ciclo dos próximos 50 baús coletados da API.
*   **`players.csv`**: Cache de dados detalhados dos jogadores enfrentados.

## 2. 🌐 O que você vê no Dashboard Web (`index.html` na RAIZ)
O gerador de HTML foi migrado para a raiz do projeto para garantir sincronia total com o GitHub Pages:

### A. Cabeçalho de Status & Baús
*   **Seu Perfil**: Nome (Λ Яᄃ λ Ð Є), Clã e Nível atual.
*   **Previsão de Tesouros**: [NOVO] Card visual que mostra os próximos baús que você vai ganhar no jogo.
*   **Cards de Resumo**: Total de Batalhas, % de Vitória Geral e Saldo de Troféus.

### B. Abas de Performance (Navegação)
*   **Histórico de Batalhas**: Lista cronológica com o "VS" visual (Seu Deck vs Oponente).
*   **Meus Decks**: Ranking dos seus 10 melhores decks (últimos 7 dias).
*   **Oponentes Repetidos**: Tabela de quem você mais enfrenta (Fregueses e Carrascos).

### C. Páginas Secundárias (Novidade)
*   **`clan.html`**: Página dedicada com análise profunda de todos os membros do clã.
*   **`member_*.html`**: Perfis individuais detalhados para cada companheiro de clã.

## 3. 📉 Integração Excel / VBA
O arquivo `vba_sync_auto.py` (ou a leitura direta dos CSVs) continua sendo a ponte:
*   **O que você vê no Excel**: Tabelas dinâmicas alimentadas pelos CSVs oficiais em `src/data_csv_oficial/`.

---

## 4. 🚀 O que está sendo construído (Plano de Expansão)
Estamos atualmente no **Dia 2** do plano de 5 dias:
1.  ✅ **Ciclo de Baús** (Entregue no Dia 1).
2.  🔵 **Meta Brasil** (Extração do Top 100 - Em desenvolvimento).
3.  ✅ **Otimização de Sync** (Entregue: Dashboard agora está na Raiz).
4.  ⏳ **Análise de Guerra** (Próxima fase).
5.  ⏳ **Copiador de Decks Pro** (Fase final).

---
**Status do Sistema**: 🟢 Operacional | **Total de Registros**: > 2.350 batalhas
**Última Sincronização**: Automática a cada 30 min via GitHub Actions.
