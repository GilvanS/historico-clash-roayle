
import sys
import os

# Adiciona src ao path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from html_generator import GitHubPagesHTMLGenerator

def main():
    generator = GitHubPagesHTMLGenerator()
    
    # Simula dados de oponentes repetidos
    opponents = generator.get_repeated_opponents_from_csv()
    
    # Simula dados de decks letais (pegando os primeiros do histórico que resultaram em derrota)
    lethal_decks = []
    seen_decks = set()
    for b in generator.battles_cache:
        if b['result'] == 'defeat' and b['opponent_deck_cards'] not in seen_decks:
            lethal_decks.append({
                'deck': b['opponent_deck_cards'],
                'losses_caused': 5, # Mock
                'last_encounter': b['battle_time'],
                'cards': [c.strip() for c in b['opponent_deck_cards'].split('|') if c.strip()]
            })
            seen_decks.add(b['opponent_deck_cards'])
            if len(lethal_decks) >= 3: break

    # Gera o HTML completo
    html = generator.generate_html_report()
    
    # Salva para teste
    with open('index_test.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("Relatório de teste gerado em index_test.html")

if __name__ == "__main__":
    main()
