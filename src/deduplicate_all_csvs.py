import os
import csv
import glob
from datetime import datetime

# Diretório dos dados
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')

def parse_date(date_str):
    """Tenta converter a string de data para objeto datetime com múltiplos formatos."""
    if not date_str:
        return None
    for fmt in ('%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None

def deduplicate_file(file_path):
    if not os.path.exists(file_path):
        return
    
    print(f"INFO: Processando arquivo: {file_path}")
    
    rows = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
    except Exception as e:
        print(f"ERRO ao ler {file_path}: {e}")
        return

    if not rows:
        return

    # Ordena por data (mais recente primeiro)
    rows.sort(key=lambda x: parse_date(x.get('data', '')) or datetime.min, reverse=True)

    unique_rows = []
    removed_count = 0

    for row in rows:
        current_time = parse_date(row.get('data', ''))
        current_tag = str(row.get('tag_oponente', '')).strip().upper()
        current_res = str(row.get('resultado', '')).strip().lower()
        
        if not current_time or not current_tag:
            unique_rows.append(row)
            continue
            
        is_duplicate = False
        # Compara com o que já mantivemos (fuzzy matching de 4 horas)
        for existing in unique_rows:
            existing_time = parse_date(existing.get('data', ''))
            existing_tag = str(existing.get('tag_oponente', '')).strip().upper()
            existing_res = str(existing.get('resultado', '')).strip().lower()
            
            if current_tag == existing_tag:
                time_diff = abs((current_time - existing_time).total_seconds()) / 60.0
                # Se a diferença for menor que 4 horas e o resultado for o mesmo
                if time_diff <= 240 and current_res == existing_res:
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            unique_rows.append(row)
        else:
            removed_count += 1

    # Salva o arquivo limpo
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(unique_rows)
        
    print(f"INFO: Concluido: {os.path.basename(file_path)}. Removidas {removed_count} duplicatas.")

def run_mass_deduplication():
    # Busca todos os arquivos oponentes_*.csv
    pattern = os.path.join(DATA_DIR, "oponentes_*.csv")
    files = glob.glob(pattern)
    
    print(f"Iniciando deduplicacao em massa em {len(files)} arquivos...")
    for f in files:
        deduplicate_file(f)

if __name__ == "__main__":
    run_mass_deduplication()
