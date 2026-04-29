import csv, os
from datetime import datetime
import glob

DATA_DIR = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial"
FIELDNAMES = [
    'data','nome_oponente','tag_oponente','nivel_oponente','trofes_oponente',
    'clan_oponente','resultado','coroas_jogador','coroas_oponente','mudanca_trofes',
    'modo_jogo','tipo_batalha','arena','deck_jogador','deck_oponente','vezes_enfrentado'
]

def parse_date(date_str):
    formats = ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def get_row_score(row):
    """Calcula um score de 'qualidade' da linha para decidir qual manter em duplicatas."""
    score = 0
    # Nivel oponente 0 é sinal de dado incompleto do coletor antigo
    if row.get('nivel_oponente') != '0' and row.get('nivel_oponente'):
        score += 10
    # Troféus != 0
    if row.get('trofes_oponente') != '0' and row.get('trofes_oponente'):
        score += 5
    # Decks preenchidos
    if len(row.get('deck_jogador', '')) > 20:
        score += 2
    if len(row.get('deck_oponente', '')) > 20:
        score += 2
    return score

def deduplicate_file(file_path):
    if not os.path.exists(file_path):
        return
    
    print(f"Deduplicando {os.path.basename(file_path)}...")
    
    try:
        with open(file_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"  - Erro ao ler: {e}")
        return

    if not rows:
        return

    # Chave de deduplicação: (Data normalizada, Tag Oponente)
    # Ignoramos o resultado na chave para evitar que a mesma batalha com strings diferentes (victory vs vitoria) entre 2x
    unique_rows = {}
    removed_count = 0
    
    for row in rows:
        dt = parse_date(row.get('data', ''))
        if not dt:
            continue
        
        # Normaliza a data para minutos (ignora segundos para bater manual com auto)
        dt_norm = dt.strftime('%Y-%m-%d %H:%M')
        tag = row.get('tag_oponente', '').strip().upper()
        
        key = (dt_norm, tag)
        
        current_score = get_row_score(row)
        
        if key in unique_rows:
            existing_row, existing_score = unique_rows[key]
            if current_score > existing_score:
                unique_rows[key] = (row, current_score)
                removed_count += 1
            else:
                removed_count += 1
        else:
            unique_rows[key] = (row, current_score)

    final_rows = [v[0] for v in unique_rows.values()]
    # Ordena decrescente
    final_rows.sort(key=lambda r: parse_date(r['data']) or datetime.min, reverse=True)
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(final_rows)
    
    print(f"  - Sucesso: {removed_count} duplicatas removidas. Total final: {len(final_rows)}")

if __name__ == "__main__":
    pattern = os.path.join(DATA_DIR, 'oponentes_*.csv')
    files = glob.glob(pattern)
    files.extend([
        os.path.join(DATA_DIR, 'ano_2026.csv'),
        os.path.join(DATA_DIR, 'mes_202604.csv')
    ])
    
    for f in files:
        deduplicate_file(f)
