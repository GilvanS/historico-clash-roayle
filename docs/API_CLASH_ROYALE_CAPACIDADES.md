# API Clash Royale - Capacidades e Endpoints

## 📋 Informações Básicas da API
- **Base URL**: `https://api.clashroyale.com/v1`
- **Autenticação**: Token Bearer (API Key)
- **Rate Limit**: Geralmente 1000 requests/hora

## 🎯 Endpoints Principais Disponíveis

### 1. **Player Information** ✅
```http
GET /players/{playerTag}
```
**Dados extraíveis:**
- Nome, nível, troféus, melhor ranque
- Clan information (nome, tag, função)
- Estatísticas de batalha (vitórias, derrotas, trio)
- Cartas e nível das cartas
- Achievements e progresso
- Deck atual favorito

### 2. **Player Battle Log** ✅
```http
GET /players/{playerTag}/battlelog
```
**Dados extraíveis (25-30 batalhas mais recentes):**
- Tipo de batalha (1v1, 2v2, desafio, etc.)
- Resultado (vitória/derrota)
- Tropas destruídas (próprias e oponente)
- Deck usado (ambos jogadores)
- Nome e tag do oponente
- Data/hora da batalha
- Duração da batalha
- Modo de jogo (ladder, tournament, etc.)

### 3. **Clan Information** ✅
```http
GET /clans/{clanTag}
```
**Dados extraíveis:**
- Informações do clan (nome, descrição, localização)
- Membros (lista completa com estatísticas)
- Nível do clan, troféus necessários
- Tipo de clan (aberto/fechado)
- Guerra atual e histórico

### 4. **Clan Members** ✅
```http
GET /clans/{clanTag}/members
```
**Dados extraíveis por membro:**
- Nome, tag, função no clan
- Troféus, doações, nível
- Última atividade

### 5. **Clan War Log** ✅
```http
GET /clans/{clanTag}/warlog
```
**Dados extraíveis:**
- Histórico de guerras do clan
- Participantes e desempenho
- Troféus ganhos/perdidos
- Colocação na guerra

### 6. **Current Clan War** ✅
```http
GET /clans/{clanTag}/currentwar
```
**Dados extraíveis:**
- Status atual da guerra
- Participantes e decks usados
- Batalhas realizadas
- Próximas etapas

### 7. **Tournaments** ⚠️
```http
GET /tournaments
GET /tournaments/{tournamentTag}
```
**Limitações:** Só tournaments públicos/searcháveis

### 8. **Cards Information** ✅
```http
GET /cards
```
**Dados extraíveis:**
- Todas as cartas do jogo
- Informações de cada carta (raridade, tipo, elixir)
- Estatísticas por nível
- URLs de imagens

### 9. **Locations** ✅
```http
GET /locations
GET /locations/{locationId}/rankings/players
GET /locations/{locationId}/rankings/clans
```
**Dados extraíveis:**
- Ranking global/local de jogadores
- Ranking global/local de clans
- Informações geográficas

## 🔍 Dados Específicos das Batalhas (Battle Log)

Cada batalha retorna:
```json
{
  "type": "PvP",
  "battleTime": "20240501T123456.000Z",
  "gameMode": {
    "id": 72000000,
    "name": "Ladder"
  },
  "deckSelection": "collection",
  "team": [{
    "tag": "PLAYER_TAG",
    "name": "PlayerName",
    "startingTrophies": 6500,
    "crowns": 2,
    "cards": [...],
    "elixirLeaked": 0.5
  }],
  "opponent": [{
    "tag": "OPPONENT_TAG", 
    "name": "OpponentName",
    "startingTrophies": 6450,
    "crowns": 1,
    "cards": [...],
    "elixirLeaked": 1.2
  }]
}
```

## ⚠️ Limitações Importantes

1. **Battle Log**: Só retorna 25-30 batalhas mais recentes
2. **Rate Limiting**: Máximo ~1000 requests/hora
3. **Player Tag**: Requer tag correta (com # convertido para %23)
4. **Dados Históricos**: Não tem acesso a batalhas antigas além das 25-30 recentes
5. **Informações em Tempo Real**: Alguns dados têm delay de atualização

## 🚀 O que Seu Projeto Atual Extrai

✅ **Do Battle Log**:
- Todas as batalhas dos últimos ~2 dias (coleta a cada 30min)
- Estatísticas de vitórias/derrotas  
- Decks usados (próprio e oponente)
- Informações do oponente (nome, tag)
- Modo de jogo e tipo de batalha

✅ **Do Player Profile**:
- Nível e troféus atuais
- Informações do clan
- Progresso geral

✅ **Do Clan**:
- Lista de membros
- Estatísticas do clan

## 💡 Possíveis Melhorias

1. **Coleta mais frequente**: Para não perder batalhas (já feito - 30min)
2. **Análise de meta**: Quais decks estão populares
3. **Estatísticas avançadas**: Win rates por deck, contra decks específicos
4. **Monitoramento de clan**: Desempenho em guerras
5. **Trend analysis**: Evolução de troféus ao longo do tempo

A API é bastante completa para extrair dados de jogabilidade, mas tem limites intencionais para prevenir abuse.