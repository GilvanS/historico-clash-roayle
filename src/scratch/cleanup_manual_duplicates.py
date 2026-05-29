import csv, os
from datetime import datetime

DATA_DIR = "data/csv"
FILES = [
    "oponentes_dia_20260424.csv",
    "oponentes_dia_20260426.csv",
    "oponentes_dia_20260427.csv",
    "oponentes_dia_20260428.csv",
    "oponentes_ano_2026.csv",
    "oponentes_mes_202604.csv"
]

FIELDNAMES = [
    'data','nome_oponente','tag_oponente','nivel_oponente','trofes_oponente',
    'clan_oponente','resultado','coroas_jogador','coroas_oponente','mudanca_trofes',
    'modo_jogo','tipo_batalha','arena','deck_jogador','deck_oponente','vezes_enfrentado'
]

def parse_date(date_str):
    formats = ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def is_manual(row):
    # Marcadores de que eu inseri via script de merge:
    # 1. nivel_oponente != '0' (o coletor bugado salva '0')
    # 2. modo_jogo em ['Ranked', 'Ladder', 'Special Event', 'Take To The Skies', '1v1 Showdown']
    # 3. mudanca_trofes com prefixo '+' ou '0.00'
    return row.get('nivel_oponente') != '0'

def cleanup_file(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return
    
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    if not rows:
        return

    # Ordena por data (crescente para facilitar o sweep)
    rows.sort(key=lambda r: parse_date(r['data']) or datetime.min)
    
    to_keep = []
    removed_count = 0
    
    # Agrupa por tag
    by_tag = {}
    for r in rows:
        tag = r['tag_oponente']
        if tag not in by_tag:
            by_tag[tag] = []
        by_tag[tag].append(r)
    
    final_rows = []
    for tag, tag_rows in by_tag.items():
        # Dentro de cada tag, remove manuais que estao proximos de originais
        kept_for_tag = []
        tag_rows.sort(key=lambda r: parse_date(r['data']) or datetime.min)
        
        for i, row in enumerate(tag_rows):
            dt = parse_date(row['data'])
            manual = is_manual(row)
            
            duplicate_found = False
            if manual:
                # Procura se existe algum original proximo
                for other in tag_rows:
                    if not is_manual(other):
                        dt_other = parse_date(other['data'])
                        diff = abs((dt - dt_other).total_seconds()) / 60.0
                        if diff < 20: # 20 minutos de janela
                            duplicate_found = True
                            break
            
            if not duplicate_found:
                kept_for_tag.append(row)
            else:
                removed_count += 1
                print(f"  [REMOVIDO DUPLICATA MANUAL] {row['data']} | {row['nome_oponente']} (Tag: {tag})")
        
        final_rows.extend(kept_for_tag)

    # Re-ordena decrescente para salvar (padrao do projeto)
    final_rows.sort(key=lambda r: parse_date(r['data']) or datetime.min, reverse=True)
    
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(final_rows)
    
    print(f"Arquivo {filename}: {removed_count} duplicatas manuais removidas. Total final: {len(final_rows)}")

if __name__ == "__main__":
    print("Iniciando limpeza de duplicatas manuais (preservando originais)...")
    for f in FILES:
        cleanup_file(f)
    print("\nLimpeza concluida!")
