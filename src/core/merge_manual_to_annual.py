"""
Merge dados manuais preservados no CSV anual.
- Le de dados_manuais_preservados.csv (UTC)
- Converte UTC -> BRT (-3h)
- Insere no oponentes_ano_YYYY.csv APENAS o que nao existe
- Nunca modifica o arquivo de dados manuais
"""
import csv
import os
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'data', 'csv')
MANUAL_FILE = os.path.join(DATA_DIR, 'dados_manuais_preservados.csv')

FIELDNAMES = [
    'player_tag',
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente', 'trofes_oponente',
    'clan_oponente', 'resultado', 'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador',
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente', 'vida_torres_princesa_jogador',
    'vida_torres_princesa_oponente', 'trofes_iniciais_jogador', 'trofes_finais_jogador',
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente',
    'torre_jogador', 'torre_oponente',
    'elixir_medio_jogador', 'elixir_medio_oponente',
    'evolucoes_jogador', 'evolucoes_oponente',
    'nivel_medio_deck_jogador', 'nivel_medio_deck_oponente',
    'tag_clan_oponente'
]


def detect_delim(fp):
    with open(fp, 'r', encoding='utf-8-sig') as f:
        sample = f.read(2000)
    return ';' if sample.count(';') > sample.count(',') else ','


def parse_date(s):
    s = str(s).strip().strip('"')
    for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S']:
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
    return r


def load_csv(fp):
    if not os.path.exists(fp):
        return [], ','
    delim = detect_delim(fp)
    with open(fp, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f, delimiter=delim)), delim


def build_keys(rows):
    """Chaves com tolerancia de 120min para detectar duplicatas."""
    keys = []
    for r in rows:
        tag = r.get('tag_oponente', r.get('opponent_tag', '')).strip()
        dt = parse_date(r.get('data', r.get('battleTime', '')))
        res = norm_res(r.get('resultado', r.get('result', '')))
        if tag and dt:
            keys.append((tag, dt, res))
    return keys


def is_duplicate(tag, dt, res, existing_keys):
    for e_tag, e_dt, e_res in existing_keys:
        if e_tag == tag and e_res == res:
            diff = abs((dt - e_dt).total_seconds()) / 60
            if diff <= 120:
                return True
    return False


# 1. Ler dados manuais
manual_rows, _ = load_csv(MANUAL_FILE)
print(f"Dados manuais: {len(manual_rows)} registros")

# 2. Agrupar por ano
by_year = {}
for row in manual_rows:
    dt_utc = parse_date(row['data'])
    if not dt_utc:
        print(f"  ERRO: nao conseguiu parsear data: {row['data']}")
        continue
    dt_brt = dt_utc - timedelta(hours=3)
    year = dt_brt.year
    if year not in by_year:
        by_year[year] = []
    # Criar row convertida para BRT
    new_row = dict(row)
    new_row['data'] = dt_brt.strftime('%d/%m/%Y %H:%M')
    by_year[year].append(new_row)

# 3. Merge em cada arquivo anual
total_added = 0
total_skipped = 0

for year, rows_to_add in sorted(by_year.items()):
    ano_file = os.path.join(DATA_DIR, f'oponentes_ano_{year}.csv')
    existing_rows, delim = load_csv(ano_file)
    existing_keys = build_keys(existing_rows)

    added = 0
    skipped = 0

    for row in rows_to_add:
        tag = row.get('tag_oponente', '').strip()
        dt = parse_date(row['data'])
        res = norm_res(row.get('resultado', ''))

        if is_duplicate(tag, dt, res, existing_keys):
            skipped += 1
        else:
            existing_rows.append(row)
            existing_keys.append((tag, dt, res))
            added += 1
            print(f"  + {row['data']} | {row['nome_oponente']} | {row['resultado']}")

    if added > 0:
        # Ordenar por data decrescente
        def sort_key(r):
            d = parse_date(r.get('data', ''))
            return d if d else datetime.min
        existing_rows.sort(key=sort_key, reverse=True)

        with open(ano_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=delim,
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(existing_rows)

    print(f"\n  {os.path.basename(ano_file)}: +{added} novos, {skipped} ja existiam "
          f"(total: {len(existing_rows)})")
    total_added += added
    total_skipped += skipped

print(f"\nRESUMO: {total_added} batalhas adicionadas, {total_skipped} ja existiam")
