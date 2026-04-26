import csv
import os
from collections import Counter

def clean_csv():
    f_path = 'a:/Workspace/historico-clash-roayle/src/data_csv_oficial/oponentes_ano_2026.csv'
    if not os.path.exists(f_path):
        print(f"Arquivo nao encontrado: {f_path}")
        return

    with open(f_path, encoding='utf-8-sig') as f:
        r = csv.DictReader(f)
        rows = list(r)
        fieldnames = r.fieldnames

    # Decks mais frequentes (DNA do GilvanS)
    top_decks = [d.split(' | ') for d, c in Counter(row['deck_jogador'] for row in rows).most_common(10)]

    def is_gilvan(deck_str):
        if not deck_str: return False
        d = deck_str.split(' | ')
        # Se o deck tem pelo menos 5 cartas em comum com um dos top 10 decks dele, assumimos que eh dele
        return any(len(set(d) & set(td)) >= 5 for td in top_decks)

    clean_rows = [row for row in rows if is_gilvan(row['deck_jogador'])]

    with open(f_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(clean_rows)

    print(f'Original: {len(rows)} | Limpo: {len(clean_rows)} | Removidos: {len(rows)-len(clean_rows)}')

if __name__ == "__main__":
    clean_csv()
