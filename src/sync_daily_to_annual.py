import os
import csv
import glob
import sys
from datetime import datetime

# Garante que o stdout aceite UTF-8 para evitar erros de encoding no print
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')
FIELDNAMES = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado'
]

def make_dedup_key(row):
    return (str(row.get('data', '')).strip(), str(row.get('tag_oponente', '')).strip().upper())

def sync():
    daily_files = glob.glob(os.path.join(DATA_DIR, "oponentes_dia_*.csv"))
    print(f"Encontrados {len(daily_files)} arquivos diarios.")
    
    # Cache para arquivos anuais
    annual_data = {} # year -> list of rows
    annual_keys = {} # year -> set of (data, tag)
    
    total_added = 0
    
    for df in daily_files:
        with open(df, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Determina o ano
                date_str = row.get('data', '')
                try:
                    year = date_str.split(' ')[0].split('/')[-1]
                    if len(year) != 4: continue
                except:
                    continue
                
                if year not in annual_data:
                    annual_path = os.path.join(DATA_DIR, f"oponentes_ano_{year}.csv")
                    if os.path.exists(annual_path):
                        with open(annual_path, 'r', encoding='utf-8-sig') as af:
                            areader = csv.DictReader(af)
                            annual_data[year] = list(areader)
                            annual_keys[year] = {make_dedup_key(r) for r in annual_data[year]}
                    else:
                        annual_data[year] = []
                        annual_keys[year] = set()
                
                key = make_dedup_key(row)
                if key not in annual_keys[year]:
                    annual_data[year].append(row)
                    annual_keys[year].add(key)
                    total_added += 1

    # Salva de volta
    for year, rows in annual_data.items():
        # Ordena por data decrescente
        def parse_dt(d):
            for fmt in ('%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
                try: 
                    return datetime.strptime(d.get('data',''), fmt)
                except: 
                    continue
            return datetime.min
            
        rows.sort(key=parse_dt, reverse=True)
        
        annual_path = os.path.join(DATA_DIR, f"oponentes_ano_{year}.csv")
        with open(annual_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        print(f"Arquivo oponentes_ano_{year}.csv atualizado. Total registros: {len(rows)}")

    print(f"Sincronizacao concluida. {total_added} batalhas sincronizadas para os arquivos anuais.")

if __name__ == "__main__":
    sync()
