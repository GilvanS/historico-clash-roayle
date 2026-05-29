import sys
import os
import logging

# Adiciona o diretório src ao path para importar as classes
sys.path.append(os.path.join(os.getcwd(), 'src'))

from html_generator import GitHubPagesHTMLGenerator

# Configura logging para ver o que está acontecendo
logging.basicConfig(level=logging.INFO)

def debug_repeated():
    generator = GitHubPagesHTMLGenerator()
    repeated = generator.get_repeated_opponents_from_csv()
    
    print(f"Total de batalhas carregadas: {len(generator.battles_cache)}")
    print(f"Total de oponentes repetidos encontrados: {len(repeated)}")
    
    if len(repeated) > 0:
        for i, opp in enumerate(repeated[:5]):
            print(f"{i+1}. {opp['opponent_name']} ({opp['opponent_tag']}) - {opp['total_battles']} batalhas")
    else:
        print("Nenhum oponente repetido encontrado.")

if __name__ == "__main__":
    debug_repeated()
