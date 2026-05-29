import csv
import os
from collections import Counter

file_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'

def check_duplicates():
    if not os.path.exists(file_path):
        print("Arquivo não encontrado.")
        return

    keys = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            key = (row.get('data'), row.get('tag_oponente'))
            keys.append(key)
    
    counts = Counter(keys)
    duplicates = {k: v for k, v in counts.items() if v > 1}
    
    if duplicates:
        print(f"Encontradas {len(duplicates)} chaves duplicadas.")
        for k, v in list(duplicates.items())[:10]:
            print(f"Chave {k} aparece {v} vezes.")
    else:
        print("Nenhuma duplicata real encontrada.")

if __name__ == "__main__":
    check_duplicates()
