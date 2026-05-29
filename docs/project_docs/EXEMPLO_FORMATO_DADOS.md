# Exemplo de Formato de Dados Solicitado

## Formato Solicitado pelo Usuário

Para cada oponente nas abas "Oponentes que me Derrotaram" e "Oponentes Repetidos", deve aparecer:

```
🏆 X batalhas
✅ X vitórias
❌ X derrotas
📈 +X troféus
👑 X.X coroas médias
```

## Exemplo de Dados que Devem Ser Retornados

### Estrutura do Dicionário `deck` (para "Oponentes que me Derrotaram"):

```python
{
    'deck_cards': 'Archer | Goblin Barrel | Hog Rider | ...',
    'total_battles': 1,  # Vezes que este deck derrotou o usuário
    'opponent_tag': '#VVLYJR89L',
    'opponent_name': 'XxlilfrankXX',
    'opponent_game_stats': {  # ESTES SÃO OS DADOS QUE DEVEM APARECER
        'total_battles': 46,
        'wins': 29,
        'losses': 17,
        'draws': 0,
        'win_rate': 63.04,
        'total_trophy_change': 172,
        'avg_crowns': 1.2
    }
}
```

### Estrutura do Dicionário `opponent` (para "Oponentes Repetidos"):

```python
{
    'opponent_tag': '#8VPRRPJV2',
    'opponent_name': 'SalMaN',
    'total_battles': 2,  # Vezes que enfrentou o usuário
    'opponent_game_stats': {  # ESTES SÃO OS DADOS QUE DEVEM APARECER
        'total_battles': 46,
        'wins': 29,
        'losses': 17,
        'draws': 0,
        'win_rate': 63.04,
        'total_trophy_change': 172,
        'avg_crowns': 1.2
    }
}
```

## Exemplo de HTML Gerado

### Para "Oponentes que me Derrotaram":

```html
<div class="deck-card">
    <div class="deck-header">
        <h3>#1 - 1 Derrotas - XxlilfrankXX (#VVLYJR89L) [OPONENTE]</h3>
    </div>
    <div class="deck-stats">
        <span class="stat">🏆 46 batalhas</span>
        <span class="stat">✅ 29 vitórias</span>
        <span class="stat">❌ 17 derrotas</span>
        <span class="stat" style="color: green">📈 +172 trofeus</span>
        <span class="stat">👑 1.2 coroas médias</span>
    </div>
    <div class="deck-cards">
        <!-- Imagens dos cards do deck -->
    </div>
</div>
```

### Para "Oponentes Repetidos":

```html
<div class="opponent-card">
    <h3>SalMaN (#8VPRRPJV2)</h3>
    <p>🏆 2 vezes enfrentado</p>
    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e2e8f0;">
        <h4>📊 Dados do Oponente no Jogo</h4>
        <div class="deck-stats">
            <span class="stat">🏆 46 batalhas</span>
            <span class="stat">✅ 29 vitórias</span>
            <span class="stat">❌ 17 derrotas</span>
            <span class="stat" style="color: green">📈 +172 trofeus</span>
            <span class="stat">👑 1.2 coroas médias</span>
        </div>
    </div>
    <!-- Estatísticas por período (Hoje, Semana, Mês, Ano) -->
    <!-- Melhor deck -->
</div>
```

## Como Funciona a Busca de Dados

1. **Primeiro**: Tenta buscar os dados do oponente no banco de dados (`battles` table onde `player_tag = opponent_tag`)

2. **Se não encontrar**: 
   - Busca os dados do oponente via API (`fetch_opponent_data_from_api`)
   - Busca as batalhas do oponente via API (`fetch_opponent_battles_from_api`)
   - Salva no banco de dados
   - Tenta buscar novamente

3. **Se ainda não encontrar**: Exibe mensagem "Dados do oponente não disponíveis"

## Requisitos

- **Token da API**: Deve estar configurado na variável de ambiente `CR_API_TOKEN`
- **Rate Limiting**: Há delays entre chamadas à API para evitar rate limiting
- **Persistência**: Dados buscados são salvos no banco para uso futuro
