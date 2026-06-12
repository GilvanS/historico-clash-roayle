import os
import csv

def clean_challenges():
    """
    Limpa os dados de decks aleatórios nos CSVs de desafios.
    Substitui decks por 'Aleatório' e zera estatísticas de elixir/nível
    para não poluir as análises.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    csv_path = os.path.join(project_root, 'data', 'csv', 'challenge_decks_semanal.csv')
    
    if not os.path.exists(csv_path):
        print(f"CSV de desafios não encontrado: {csv_path}")
        return

    # Lendo o CSV atual
    rows = []
    fieldnames = []
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        fieldnames = reader.fieldnames
        for row in reader:
            # Força as colunas de deck e stats para "Aleatório" e 0.0, pois o desafio atual é aleatório
            row['deck_jogador'] = 'Aleatório'
            row['deck_oponente'] = 'Aleatório'
            row['deck_key'] = 'Aleatório'  # caso exista do script TOP
            row['elixir_medio_jogador'] = '0.0'
            row['elixir_medio_oponente'] = '0.0'
            row['nivel_medio_deck_jogador'] = '0.0'
            row['nivel_medio_deck_oponente'] = '0.0'
            rows.append(row)

    # Reescrevendo o CSV limpo
    if fieldnames:
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        print(f"Limpeza de decks concluída em {csv_path} (Forçados para 'Aleatório')")

if __name__ == '__main__':
    clean_challenges()
