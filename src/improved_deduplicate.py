import csv, os
from datetime import datetime, timedelta
import glob

FIELDNAMES = [
    'data','nome_oponente','tag_oponente','nivel_oponente','trofes_oponente',
    'clan_oponente','resultado','coroas_jogador','coroas_oponente','mudanca_trofes',
    'modo_jogo','tipo_batalha','arena','deck_jogador','deck_oponente','vezes_enfrentado'
]

def parse_date(date_str):
    formats = ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def get_row_score(row):
    """Calcula um score de 'qualidade' da linha para decidir qual manter em duplicatas."""
    score = 0
    nivel = str(row.get('nivel_oponente', '0'))
    if nivel != '0' and nivel != '':
        score += 10
    trofes = str(row.get('trofes_oponente', '0'))
    if trofes != '0' and trofes != '':
        score += 5
    if len(row.get('deck_jogador', '')) > 20:
        score += 2
    if len(row.get('deck_oponente', '')) > 20:
        score += 2
    # Prefere nomes com caracteres especiais se existirem
    if any(ord(c) > 127 for c in row.get('nome_oponente', '')):
        score += 1
    return score

def deduplicate_file(file_path):
    if not os.path.exists(file_path):
        return
    
    print(f"Deduplicando {os.path.basename(file_path)} (Modo Avançado)...")
    
    try:
        with open(file_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"  - Erro ao ler: {e}")
        return

    if not rows:
        return

    # 1. Filtra linhas sem data válida
    valid_rows = []
    for row in rows:
        dt = parse_date(row.get('data', ''))
        if dt:
            row['_dt'] = dt
            valid_rows.append(row)
    
    # 2. Agrupa por Tag Oponente
    by_tag = {}
    for row in valid_rows:
        tag = row.get('tag_oponente', '').strip().upper()
        if tag not in by_tag:
            by_tag[tag] = []
        by_tag[tag].append(row)
    
    final_rows = []
    removed_count = 0
    
    for tag, tag_rows in by_tag.items():
        # Ordena por data
        tag_rows.sort(key=lambda r: r['_dt'])
        
        i = 0
        while i < len(tag_rows):
            best_row = tag_rows[i]
            best_score = get_row_score(best_row)
            
            # Procura duplicatas "fuzzy" nas próximas linhas (janela de 6 horas)
            j = i + 1
            while j < len(tag_rows):
                next_row = tag_rows[j]
                time_diff = next_row['_dt'] - best_row['_dt']
                
                if time_diff > timedelta(hours=6):
                    break
                
                # Critérios de duplicata (mesmo resultado, coroas e troféus)
                # Adicionado: Janela fuzzy de 15 minutos para considerar a MESMA partida
                # mesmo que o horário tenha um pequeno delay na API.
                
                res_best = str(best_row.get('resultado') or '').strip().lower()
                res_next = str(next_row.get('resultado') or '').strip().lower()
                
                # Normalização simples para comparação
                def norm(r):
                    if any(x in r for x in ['vitoria', 'victory', 'vitória']): return 'v'
                    if any(x in r for x in ['derrota', 'defeat']): return 'd'
                    if any(x in r for x in ['empate', 'draw']): return 'e'
                    return r
                
                is_duplicate = (
                    norm(res_best) == norm(res_next) and
                    str(next_row.get('coroas_jogador')) == str(best_row.get('coroas_jogador')) and
                    str(next_row.get('coroas_oponente')) == str(best_row.get('coroas_oponente')) and
                    time_diff <= timedelta(minutes=20) # Janela de 20 min para cobrir delays de 10-15 min relatados
                )
                
                if is_duplicate:
                    # Se for duplicata, decide qual manter (a que tem mais dados/score)
                    next_score = get_row_score(next_row)
                    if next_score > best_score:
                        best_row = next_row
                        best_score = next_score
                    removed_count += 1
                    j += 1
                else:
                    # Se não for idêntico nos campos chave ou passar de 15 min,
                    # avançamos para o próximo 'best_row'
                    break
            
            final_rows.append(best_row)
            i = j

    # Remove o campo temporário _dt
    for row in final_rows:
        if '_dt' in row:
            del row['_dt']
            
    # Ordena decrescente para salvar
    final_rows.sort(key=lambda r: parse_date(r['data']) or datetime.min, reverse=True)
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(final_rows)
    
    print(f"  - Sucesso: {removed_count} duplicatas removidas. Total final: {len(final_rows)}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data_csv_oficial')
    
    # Processa todos os arquivos
    files = glob.glob(os.path.join(data_dir, 'oponentes_*.csv'))
    
    for f in files:
        deduplicate_file(f)
