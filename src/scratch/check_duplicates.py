import csv
import collections

file_path = r'a:\Workspace\historico-clash-roayle\data\oponentes_ano_2026.csv'
keys = collections.Counter()
dupes = []

try:
    with open(file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            time = row.get('data') or row.get('battle_time')
            tag = row.get('tag_oponente') or row.get('opponent_tag')
            if time and tag:
                key = (time, tag)
                keys[key] += 1
                if keys[key] > 1:
                    dupes.append(key)

    print(f"Total de duplicatas encontradas: {len(dupes)}")
    for d in dupes[:10]:
        print(f"Duplicata: {d}")
except Exception as e:
    print(f"Erro: {e}")
