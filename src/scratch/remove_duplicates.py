import csv
import os

# Caminho correto descoberto: src/data_csv_oficial
file_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'
temp_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026_clean.csv'

if not os.path.exists(file_path):
    print(f"Arquivo {file_path} não encontrado.")
    exit(1)

seen_keys = set()
unique_rows = []
duplicates_count = 0

try:
    with open(file_path, mode='r', encoding='utf-8-sig') as f:
        # Detecta delimitador
        first_line = f.readline()
        f.seek(0)
        delimiter = ';' if ';' in first_line else ','
        
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = reader.fieldnames
        
        for row in reader:
            # Chave: (data, oponente_tag)
            time = (row.get('data') or row.get('battle_time') or '').strip()
            tag = (row.get('tag_oponente') or row.get('opponent_tag') or '').strip().upper()
            
            if not time or not tag:
                unique_rows.append(row)
                continue
                
            key = (time, tag)
            if key in seen_keys:
                duplicates_count += 1
            else:
                seen_keys.add(key)
                unique_rows.append(row)

    if duplicates_count > 0:
        with open(temp_path, mode='w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(unique_rows)
        
        # Substitui o original
        os.replace(temp_path, file_path)
        print(f"Sucesso: {duplicates_count} duplicatas removidas do {file_path}.")
    else:
        print(f"Nenhuma duplicata encontrada em {file_path}.")

except Exception as e:
    print(f"Erro ao processar CSV: {e}")
