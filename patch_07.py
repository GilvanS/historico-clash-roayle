import csv
import os

data_dir = 'a:/Workspace/historico-clash-roayle/data/csv'
csv_07 = os.path.join(data_dir, 'inteligencia_guerra_2026-06-07.csv')
csv_06 = os.path.join(data_dir, 'inteligencia_guerra_2026-06-06.csv')
csv_hist = os.path.join(data_dir, 'guerra_historico.csv')

# Load 06 data
with open(csv_06, 'r', encoding='utf-8-sig') as f:
    reader_06 = list(csv.DictReader(f, delimiter=';'))

# Load 07 data
with open(csv_07, 'r', encoding='utf-8-sig') as f:
    reader_07 = list(csv.DictReader(f, delimiter=';'))

# Which global clans are in 07?
existing_global_tags_07 = set(r['clan_tag'] for r in reader_07 if r.get('conta_tipo') == 'TOP_GLOBAL')

# Find missing global clans from 06
missing_global_06 = [r for r in reader_06 if r.get('conta_tipo') == 'TOP_GLOBAL' and r['clan_tag'] not in existing_global_tags_07]

if missing_global_06:
    print(f"Found {len(missing_global_06)} missing records. Patching...")
    fieldnames = list(reader_07[0].keys()) if reader_07 else list(reader_06[0].keys())
    
    # Patch 07
    patched_07 = reader_07.copy()
    for row in missing_global_06:
        new_row = row.copy()
        new_row['data_coleta'] = '2026-06-07'
        new_row['dia_batalha'] = 'Dia 3'
        patched_07.append(new_row)
        
    with open(csv_07, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(patched_07)
        
    # Patch historico
    with open(csv_hist, 'r', encoding='utf-8-sig') as f:
        reader_hist = list(csv.DictReader(f, delimiter=';'))
        
    patched_hist = reader_hist.copy()
    for row in missing_global_06:
        new_row = row.copy()
        new_row['data_coleta'] = '2026-06-07'
        new_row['dia_batalha'] = 'Dia 3'
        patched_hist.append(new_row)
        
    with open(csv_hist, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(patched_hist)
    print("Patch applied successfully.")
else:
    print("No missing records to patch.")
