# 🛠️ Resumo do Estado Atual: Clash Royale Analytics (GilvanS)

Este documento descreve o que o projeto já realiza, os dados que ele gera e como você os visualiza.

## 1. 📂 Onde os Dados são Gerados (Arquivos)
Atualmente, o script Python (`collect_battles_csv.py` e `consolidar_dados_2026.py`) gera e mantém os seguintes arquivos principais na pasta `src/data_csv_oficial/`:

*   **`oponentes_ano_2026.csv`**: O banco de dados principal de 2026. Contém cada batalha detalhada (Data, Resultado, Coroas, Troféus, Decks e Tags).
*   **`historico_completo_2023_2025.csv`**: Arquivo de "Legado" que preserva suas mais de 2.000 batalhas de anos anteriores.
*   **`clan_members.csv`**: Dados atualizados do seu clã (Quem está no clã, nível e troféus).
*   **`players.csv`**: Cache de dados detalhados dos jogadores que você enfrenta (usado para não sobrecarregar a API).

## 2. 🌐 O que você vê no Dashboard Web (`index.html`)
O gerador de HTML (`html_generator.py`) transforma os CSVs acima em um painel visual com as seguintes seções:

### A. Cabeçalho de Status
*   **Seu Perfil**: Nome, Clã e Nível atual.
*   **Cards de Resumo**: Total de Batalhas, % de Vitória Geral, Saldo de Troféus e Data da Última Partida.

### B. Abas de Performance (Navegação)
*   **Histórico de Batalhas**: Uma lista cronológica das suas últimas partidas com o "VS" visual (Seu Deck vs Deck do Oponente).
*   **Meus Decks**: Ranking dos seus 10 melhores decks (baseado em taxa de vitória nos últimos 7 dias).
*   **Oponentes Repetidos**: Tabela que mostra quem são os jogadores que você mais enfrenta, quantas vezes ganhou/perdeu deles e a data do último encontro.

### C. Visualização de Partida (Card VS)
*   Mostra as 8 cartas do seu deck e as 8 do oponente.
*   Exibe o nível médio das cartas e o elixir vazado (se os dados premium estiverem ativos).

## 3. 📉 Integração Excel / VBA
O arquivo `vba_sync_auto.py` serve como a ponte:
*   Ele lê os mesmos CSVs que o Dashboard Web usa.
*   O VBA no Excel chama esse script para "puxar" os dados para dentro das planilhas automaticamente.
*   **O que você vê no Excel**: Tabelas dinâmicas e gráficos nativos do Excel alimentados pelos dados reais da API.

---

## 4. 🚀 O que está "Ganhando Vida" (Expansão 2026)
O que você começou a pedir agora e que **ainda não está** no Dashboard atual:
1.  **Previsão de Próximos Baús** (Saber o que vem depois).
2.  **Ranking Top 100 Brasil** (Para comparar seu deck com os profissionais).
3.  **Análise de Guerra** (Saber se o clã inimigo é muito mais forte que o seu).
4.  **Copiador de Decks Pro** (Botão para salvar decks de quem fez 20 vitórias em torneios).

---
**Status do Sistema**: 🟢 Operacional | **Total de Registros**: > 2.300 batalhas
