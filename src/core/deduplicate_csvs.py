import csv, os
from datetime import datetime
import glob

FIELDNAMES = [
    'player_tag',
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente', 'trofes_oponente',
    'clan_oponente', 'resultado', 'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador',
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente',
    'vida_torres_princesa_jogador', 'vida_torres_princesa_oponente',
    'trofes_iniciais_jogador', 'trofes_finais_jogador',
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente',
    'torre_jogador', 'torre_oponente',
    'elixir_medio_jogador', 'elixir_medio_oponente',
    'evolucoes_jogador', 'evolucoes_oponente',
    'nivel_medio_deck_jogador', 'nivel_medio_deck_oponente',
    'tag_clan_oponente'
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
    # Nivel oponente 0 é sinal de dado incompleto do coletor antigo
    nivel = str(row.get('nivel_oponente', '0'))
    if nivel != '0' and nivel != '':
        score += 10
    # Troféus != 0
    trofes = str(row.get('trofes_oponente', '0'))
    if trofes != '0' and trofes != '':
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
        delimiter = ';' if ';' in open(file_path, encoding='utf-8-sig').readline() else ','
        with open(file_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)
    except Exception as e:
        print(f"  - Erro ao ler: {e}")
        return

    if not rows:
        return

    # Chave de deduplicação: (Data normalizada, Tag Oponente)
    unique_rows = {}
    removed_count = 0
    
    for row in rows:
        dt = parse_date(row.get('data', ''))
        if not dt:
            continue
        
        # Normaliza a data para minutos
        dt_norm = dt.strftime('%Y-%m-%d %H:%M')
        tag = row.get('tag_oponente', '').strip().upper()
        
        # Chave: player_tag + data normalizada + tag oponente (evita dedup entre contas)
        key = (str(row.get('player_tag', '')).strip().upper(), dt_norm, tag)
        
        current_score = get_row_score(row)
        
        if key in unique_rows:
            existing_row, existing_score = unique_rows[key]
            if current_score > existing_score:
                unique_rows[key] = (row, current_score)
            removed_count += 1
        else:
            unique_rows[key] = (row, current_score)

    final_rows = [v[0] for v in unique_rows.values()]
    # Ordena decrescente
    final_rows.sort(key=lambda r: parse_date(r['data']) or datetime.min, reverse=True)
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=delimiter)
        w.writeheader()
        w.writerows(final_rows)
    
    print(f"  - Sucesso: {removed_count} duplicatas removidas. Total final: {len(final_rows)}")

if __name__ == "__main__":
    # Usa o diretório do script como base (src/)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '..', 'data', 'csv')
    
    pattern = os.path.join(data_dir, 'oponentes_*.csv')
    files = glob.glob(pattern)
    files.extend([
        os.path.join(data_dir, 'oponentes_ano_2026.csv'),
        os.path.join(data_dir, 'oponentes_mes_202604.csv')
    ])
    
    for f in files:
        deduplicate_file(f)
