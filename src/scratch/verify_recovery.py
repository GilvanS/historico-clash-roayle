
import csv
import os

dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
file_path = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\recuperacao_hp_global.csv"

print(f"\nAnalisando: {file_path}")
if not os.path.exists(file_path):
    print("Arquivo nao encontrado.")
else:
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        count_missing = 0
        total_in_dates = 0
        for row in reader:
            if any(date in row.get('data', '') for date in dates):
                total_in_dates += 1
                king_player = row.get('vida_torre_rei_jogador', '0')
                if king_player == "0" or king_player == "" or king_player is None:
                    # Mas se for derrota 0-3, king=0 eh valido. 
                    # Vamos ver se coroas_oponente eh 3.
                    coroas_op = row.get('coroas_oponente', '0')
                    if coroas_op != '3':
                        count_missing += 1
        
        print(f"Total de batalhas nas datas: {total_in_dates}")
        print(f"Batalhas com vida_torre_rei_jogador zerada/faltando (e nao foi 3-crown loss): {count_missing}")
