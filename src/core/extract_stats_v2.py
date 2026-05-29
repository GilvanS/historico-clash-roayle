import csv
import os

csv_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'
player_tag = '#2QR292P'

latest_stats = None

if os.path.exists(csv_path):
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            if row.get('player_tag') == player_tag:
                # Assuming the file is ordered with newest last (or we just want the last one in the file)
                # Let's check if it has trophies
                if row.get('trofes_finais_jogador'):
                    latest_stats = row

if latest_stats:
    print(f"Found stats for {player_tag}:")
    print(f"Level: {latest_stats.get('nivel_torre_jogador')}")
    print(f"Trophies: {latest_stats.get('trofes_finais_jogador')}")
    print(f"Initial Trophies: {latest_stats.get('trofes_iniciais_jogador')}")
else:
    print(f"No stats found for {player_tag} with trophies in {csv_path}")
