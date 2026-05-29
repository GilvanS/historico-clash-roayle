# Documentação da API Clash Royale (Swagger Oficial)

Este documento contém a transcrição completa dos endpoints disponíveis na API oficial da Supercell, conforme extraído do Swagger UI em Maio de 2026.

## 🔗 Base URL
- **Oficial:** `https://api.clashroyale.com/v1`
- **Proxy (Utilizado no Projeto):** `https://proxy.royaleapi.dev/v1`

---

## 👥 Jogadores (Players)
Acesso a informações específicas do jogador.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/players/{playerTag}` | Retorna o perfil completo do jogador (troféus, nível, cartas). |
| `GET` | `/players/{playerTag}/upcomingchests` | Retorna a sequência dos próximos baús do jogador. |
| `GET` | `/players/{playerTag}/battlelog` | Retorna o histórico das últimas 25-30 batalhas realizadas. |

---

## 🏰 Clãs (Clans)
Acesso a informações específicas de clãs e guerras.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/clans` | Busca global de clãs por nome ou parâmetros. |
| `GET` | `/clans/{clanTag}` | Retorna os detalhes de um clã específico. |
| `GET` | `/clans/{clanTag}/members` | Lista todos os membros atuais do clã. |
| `GET` | `/clans/{clanTag}/warlog` | Retorna o histórico de guerras do clã. |
| `GET` | `/clans/{clanTag}/currentwar` | Informações sobre a guerra de clãs em andamento. |
| `GET` | `/clans/{clanTag}/currentriverrace` | Dados da Corrida Fluvial atual do clã. |
| `GET` | `/clans/{clanTag}/riverracelog` | Histórico de Corridas Fluviais passadas. |

---

## 🃏 Cartas (Cards)
Acesso à biblioteca de cartas do jogo.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/cards` | Retorna a lista de todas as cartas disponíveis no jogo. |

---

## 🏆 Localizações e Rankings (Locations)
Acesso aos rankings globais e locais.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/locations` | Lista todas as localizações (países/regiões) e seus IDs. |
| `GET` | `/locations/{locationId}/rankings/clans` | Ranking de clãs por localização. |
| `GET` | `/locations/{locationId}/rankings/players` | Ranking de jogadores por localização. |
| `GET` | `/locations/{locationId}/rankings/clanwars` | Ranking de guerra de clãs por localização. |
| `GET` | `/locations/global/pathoflegend/{seasonId}/rankings/players` | Top jogadores do Caminho das Lendas da temporada. |
| `GET` | `/locations/global/seasons` | Lista as temporadas passadas da liga. |

---

## 🏟️ Torneios (Tournaments)
Informações sobre torneios dentro do jogo.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/tournaments` | Busca por torneios ativos. |
| `GET` | `/tournaments/{tournamentTag}` | Detalhes de um torneio específico. |
| `GET` | `/globaltournaments` | Lista de torneios globais ativos. |

---

## 📅 Eventos e Placar (Events & Leaderboards)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/events` | Retorna os eventos atuais do jogo. |
| `GET` | `/leaderboards` | Lista os placares disponíveis. |
| `GET` | `/leaderboard/{leaderboardId}` | Jogadores em um placar específico. |

---
**Nota:** Para utilizar qualquer um destes endpoints, é necessário um Token de API válido com o IP do servidor autorizado na Whitelist da Supercell.
