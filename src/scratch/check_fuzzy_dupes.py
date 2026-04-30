import csv, os
from datetime import datetime, timedelta
import glob

def parse_date(date_str):
    formats = ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def normalize_res(res):
    if not res: return 'unknown'
    res = res.lower()
    if any(x in res for x in ['vitoria', 'victory', 'vitória']): return 'victory'
    if any(x in res for x in ['derrota', 'defeat']): return 'defeat'
    if any(x in res for x in ['empate', 'draw']): return 'draw'
    return 'unknown'

data_dir = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial"
files = glob.glob(os.path.join(data_dir, 'oponentes_*.csv'))

all_battles = []
for f in files:
    try:
        with open(f, encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                dt = parse_date(row.get('data', ''))
                if dt:
                    row['_dt'] = dt
                    row['_source'] = os.path.basename(f)
                    all_battles.append(row)
    except:
        pass

# Sort by tag and date
all_battles.sort(key=lambda x: (x.get('tag_oponente', ''), x['_dt']))

duplicates_found = []
for i in range(len(all_battles) - 1):
    b1 = all_battles[i]
    b2 = all_battles[i+1]
    
    if b1.get('tag_oponente') == b2.get('tag_oponente') and b1.get('tag_oponente') != '':
        time_diff = abs((b1['_dt'] - b2['_dt']).total_seconds()) / 60.0
        if time_diff <= 20: # 20 mins fuzzy
            res1 = normalize_res(b1.get('resultado', b1.get('result')))
            res2 = normalize_res(b2.get('resultado', b2.get('result')))
            
            if res1 == res2:
                duplicates_found.append((b1, b2))

print(f"Total potential duplicates found: {len(duplicates_found)}")
for b1, b2 in duplicates_found[:20]:
    print(f"Match: {b1.get('nome_oponente')} vs {b2.get('nome_oponente')}")
    print(f"  Time 1: {b1['_dt']} ({b1['_source']})")
    print(f"  Time 2: {b2['_dt']} ({b2['_source']})")
    print(f"  Res: {b1.get('resultado')} / {b2.get('resultado')}")
    print("-" * 20)
