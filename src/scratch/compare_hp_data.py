
import csv
import os

dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
files = [
    r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv",
    r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\backups\oponentes_ano_2026_restaurado.csv"
]

for file_path in files:
    print(f"\nAnalisando: {file_path}")
    if not os.path.exists(file_path):
        print("Arquivo nao encontrado.")
        continue
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        count_missing = 0
        total_in_dates = 0
        for row in reader:
            if any(date in row.get('data', '') for date in dates):
                total_in_dates += 1
                # Check if HP columns are "0" or empty
                king_player = row.get('vida_torre_rei_jogador', '0')
                king_opp = row.get('vida_torre_rei_oponente', '0')
                if king_player == "0" or king_player == "":
                    count_missing += 1
        
        print(f"Total de batalhas nas datas: {total_in_dates}")
        print(f"Batalhas com vida_torre_rei_jogador zerada/faltando: {count_missing}")
