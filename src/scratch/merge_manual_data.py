#!/usr/bin/env python3
"""
Processa dados manuais do usuario, converte UTC->BRT e faz merge nos CSVs corretos.
"""
import csv, io, os
from datetime import datetime, timedelta

# Dados manuais do usuario (UTC)
RAW_DATA = """data,nome_oponente,tag_oponente,nivel_oponente,trofes_oponente,clan_oponente,resultado,coroas_jogador,coroas_oponente,mudanca_trofes,modo_jogo,tipo_batalha,arena,deck_jogador,deck_oponente,vezes_enfrentado
2026-04-24 21:17:41,Duduzin;),#89U2YVLY,15,12059,BRZ Esports,victory,1,0,+0.12,Ramp Up Battle,specialEvent,Legendary Arena,Evolved Goblin Giant | Archer Queen | Evolved Skeletons | Royal Hogs | Electro Giant | Barbarian Barrel | Poison | Graveyard,Evolved Firecracker | The Log | Evolved P.E.K.K.A | Tesla | Hog Rider | Fireball | Ice Spirit | Ice Golem,1"""

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_csv_oficial")

FIELDNAMES = [
    'data','nome_oponente','tag_oponente','nivel_oponente','trofes_oponente',
    'clan_oponente','resultado','coroas_jogador','coroas_oponente','mudanca_trofes',
    'modo_jogo','tipo_batalha','arena','deck_jogador','deck_oponente','vezes_enfrentado'
]

def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    rows_sorted = sorted(rows, key=lambda r: r.get('data',''), reverse=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows_sorted)

def existing_keys(rows):
    return {(r.get('data','').strip(), r.get('tag_oponente','').strip()) for r in rows}

# Parse dados manuais e converte UTC -> BRT
reader = csv.DictReader(io.StringIO(RAW_DATA))
rows_input = list(reader)

# Agrupa por arquivo de destino
por_arquivo = {}  # filename -> lista de rows novas

adicionados = []
ignorados = []

for row in rows_input:
    dt_utc_str = row['data'].strip()
    try:
        dt_utc = datetime.strptime(dt_utc_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        dt_utc = datetime.strptime(dt_utc_str[:19], '%Y-%m-%d %H:%M:%S')

    dt_brt = dt_utc - timedelta(hours=3)
    data_fmt = dt_brt.strftime('%d/%m/%Y %H:%M')
    data_key = dt_brt.strftime('%Y%m%d')

    # Determina arquivos de destino
    dia_csv  = os.path.join(DATA_DIR, f"oponentes_dia_{data_key}.csv")
    ano_csv  = os.path.join(DATA_DIR, f"oponentes_ano_{dt_brt.year}.csv")
    mes_csv  = os.path.join(DATA_DIR, f"oponentes_mes_{dt_brt.year}{dt_brt.strftime('%m')}.csv")

    nova_row = dict(row)
    nova_row['data'] = data_fmt

    tag = nova_row.get('tag_oponente','').strip()
    chave = (data_fmt, tag)

    # Verifica e adiciona em cada arquivo
    for csv_path in [dia_csv, ano_csv, mes_csv]:
        fname = os.path.basename(csv_path)
        existentes = read_csv(csv_path)
        keys = existing_keys(existentes)
        if chave not in keys:
            existentes.append(nova_row)
            write_csv(csv_path, existentes)
            if csv_path == dia_csv:
                adicionados.append((data_fmt, nova_row['nome_oponente'], fname))
        else:
            if csv_path == dia_csv:
                ignorados.append((data_fmt, nova_row['nome_oponente'], 'JA EXISTE'))

print("=" * 60)
print("MERGE CONCLUIDO")
print("=" * 60)

print(f"\nNOVAS batalhas adicionadas ({len(adicionados)}):")
for data, nome, arq in adicionados:
    print(f"  + {data} | {nome} -> {arq}")

print(f"\nBatalhas ja existentes ignoradas ({len(ignorados)}):")
for data, nome, status in ignorados:
    print(f"  = {data} | {nome}")

# Conta totais finais
for dia in ['20260426','20260427','20260428']:
    p = os.path.join(DATA_DIR, f"oponentes_dia_{dia}.csv")
    rows = read_csv(p)
    print(f"\n  {os.path.basename(p)}: {len(rows)} batalhas")

ano = os.path.join(DATA_DIR, "oponentes_ano_2026.csv")
print(f"  oponentes_ano_2026.csv: {len(read_csv(ano))} batalhas")
