"""Limpeza final: remove de dia/semana/mes tudo que ja existe no anual (com tolerancia temporal)."""
import csv
import glob
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')


def parse_date(s):
    if not s:
        return None
    s = str(s).strip().strip('"')
    for fmt in ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S']:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def norm_res(r):
    r = str(r).strip().lower()
    if r in ['vitoria', 'victory', 'win']:
        return 'v'
    if r in ['derrota', 'defeat', 'loss']:
        return 'd'
    if r in ['empate', 'draw']:
        return 'e'
    return r


def detect_delim(fp):
    with open(fp, 'r', encoding='utf-8-sig') as f:
        sample = f.read(2000)
    return ';' if sample.count(';') > sample.count(',') else ','


# 1. Carregar TODAS as entradas anuais
ano_entries = []
for fp in sorted(glob.glob(os.path.join(DATA, 'oponentes_ano_*.csv'))):
    delim = detect_delim(fp)
    with open(fp, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            tag = row.get('tag_oponente', row.get('opponent_tag', '')).strip()
            dt = parse_date(row.get('data', row.get('battleTime', '')))
            res = norm_res(row.get('resultado', row.get('result', '')))
            if tag and dt:
                ano_entries.append((tag, dt, res))

print(f"Entradas no anual: {len(ano_entries)}")


def is_in_annual(tag, dt, res):
    """Verifica se uma entrada ja existe no anual com tolerancia de 120min."""
    for a_tag, a_dt, a_res in ano_entries:
        if a_tag == tag and a_res == res:
            diff = abs((dt - a_dt).total_seconds()) / 60
            if diff <= 120:
                return True
    return False


# 2. Limpar TODOS os arquivos nao-anuais
targets = sorted(
    glob.glob(os.path.join(DATA, 'oponentes_dia_*.csv')) +
    glob.glob(os.path.join(DATA, 'oponentes_semana_*.csv')) +
    glob.glob(os.path.join(DATA, 'oponentes_mes_*.csv'))
)

for fp in targets:
    fn = os.path.basename(fp)
    delim = detect_delim(fp)
    with open(fp, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delim)
        fieldnames = reader.fieldnames
        rows = list(reader)

    orig = len(rows)
    kept = []
    for row in rows:
        tag = row.get('tag_oponente', row.get('opponent_tag', '')).strip()
        dt = parse_date(row.get('data', row.get('battleTime', '')))
        res = norm_res(row.get('resultado', row.get('result', '')))
        if tag and dt and is_in_annual(tag, dt, res):
            continue
        kept.append(row)

    removed = orig - len(kept)
    with open(fp, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delim)
        writer.writeheader()
        writer.writerows(kept)

    if removed > 0:
        print(f"  {fn}: {orig} -> {len(kept)} (removidos {removed})")
    else:
        print(f"  {fn}: {orig} registros (limpo)")

# 3. Verificacao final
print("\nVERIFICACAO FINAL:")
check_names = ['daniel_wrld08', 'Boruto Uzumaki', 'VINI', 'Luiz03br', 'MIGUEL CR']
for fp in sorted(glob.glob(os.path.join(DATA, 'oponentes_*.csv'))):
    fn = os.path.basename(fp)
    delim = detect_delim(fp)
    with open(fp, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            nome = row.get('nome_oponente', row.get('opponent_name', ''))
            for t in check_names:
                if t.lower() in str(nome).lower():
                    data = row.get('data', row.get('battleTime', ''))
                    print(f"  {fn} | {nome} | {data}")
