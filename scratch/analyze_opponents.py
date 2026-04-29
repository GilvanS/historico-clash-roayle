
import csv
import glob
import os

path = 'a:/Workspace/historico-clash-roayle/src/data_csv_oficial/oponentes_*.csv'
files = glob.glob(path)
ignored = ['oponentes_todos.csv', 'oponentes_batalhas.csv', 'battles.csv']

opponents = {}
for f in files:
    if os.path.basename(f) in ignored: continue
    with open(f, 'r', encoding='utf-8-sig', errors='ignore') as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            # try with ;
            file.seek(0)
            reader = csv.DictReader(file, delimiter=';')
            
        for row in reader:
            tag = row.get('tag_oponente') or row.get('opponent_tag')
            if not tag: continue
            res = row.get('resultado') or row.get('result') or ''
            if tag not in opponents:
                opponents[tag] = {'name': row.get('nome_oponente') or row.get('oponente'), 'count': 0, 'results': []}
            opponents[tag]['count'] += 1
            opponents[tag]['results'].append(res)

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sorted_opps = sorted(opponents.items(), key=lambda x: x[1]['count'], reverse=True)
for tag, data in sorted_opps[:30]:
    draws = sum(1 for r in data['results'] if r and ('empate' in r.lower() or 'draw' in r.lower()))
    print(f"Tag: {tag}, Name: {data['name']}, Battles: {data['count']}, Draws: {draws}")
