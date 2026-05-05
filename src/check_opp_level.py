import csv
from datetime import datetime

file_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'
try:
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        count_target_days = 0
        count_missing_level = 0
        missing_examples = []
        for row in reader:
            data_str = row.get('data', '')
            if not data_str: continue
            try:
                dt = datetime.strptime(data_str, '%d/%m/%Y %H:%M')
            except ValueError:
                continue
            
            if datetime(2026, 4, 30) <= dt <= datetime(2026, 5, 5, 23, 59, 59):
                count_target_days += 1
                nivel = row.get('nivel_oponente', '')
                if not nivel or str(nivel) == '0' or str(nivel) == '':
                    count_missing_level += 1
                    if len(missing_examples) < 10:
                        missing_examples.append(f"{data_str} | {row.get('nome_oponente', '')} | {row.get('tag_oponente', '')}")

        print(f'Total battles 30/04 - 05/05: {count_target_days}')
        print(f'Battles missing opponent level: {count_missing_level}')
        for ex in missing_examples:
            print(ex)
except Exception as e:
    print('Error:', e)
