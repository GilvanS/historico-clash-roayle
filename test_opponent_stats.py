#!/usr/bin/env python3
"""
Test script to demonstrate how opponent stats should be displayed
"""

# Example of how the data should look when returned from get_deck_performance_defeated_by
example_deck_data = {
    'deck_cards': 'Archer | Goblin Barrel | Hog Rider | Royal Giant | Mega Knight | Musketeer | Skeleton Army | The Log',
    'total_battles': 1,  # Times this deck defeated the user
    'wins': 1,
    'losses': 0,
    'win_rate': 100.0,
    'total_trophy_change': -30,
    'avg_trophy_change': -30.0,
    'avg_crowns': 1.0,
    'opponent_tag': '#VVLYJR89L',
    'opponent_name': 'XxlilfrankXX',
    'opponent_game_stats': {  # THIS IS THE KEY DATA THAT MUST BE PRESENT
        'total_battles': 46,
        'wins': 29,
        'losses': 17,
        'draws': 0,
        'win_rate': 63.04,
        'total_trophy_change': 172,
        'avg_crowns': 1.2
    }
}

# Example HTML output that should be generated
example_html_output = """
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
        <!-- Card images here -->
    </div>
</div>
"""

print("=" * 80)
print("EXEMPLO DE DADOS QUE DEVEM SER RETORNADOS:")
print("=" * 80)
print(f"""
Deck: {example_deck_data['deck_cards']}
Oponente: {example_deck_data['opponent_name']} ({example_deck_data['opponent_tag']})

DADOS DO OPONENTE (opponent_game_stats):
  - Total de Batalhas: {example_deck_data['opponent_game_stats']['total_battles']}
  - Vitórias: {example_deck_data['opponent_game_stats']['wins']}
  - Derrotas: {example_deck_data['opponent_game_stats']['losses']}
  - Troféus: {example_deck_data['opponent_game_stats']['total_trophy_change']:+d}
  - Coroas Médias: {example_deck_data['opponent_game_stats']['avg_crowns']:.1f}
""")

print("=" * 80)
print("EXEMPLO DE HTML QUE DEVE SER GERADO:")
print("=" * 80)
print(example_html_output)

print("=" * 80)
print("FORMATO SOLICITADO PELO USUÁRIO:")
print("=" * 80)
print("""
🏆 X batalhas
✅ X vitórias
❌ X derrotas
📈 +X troféus
👑 X.X coroas médias
""")
