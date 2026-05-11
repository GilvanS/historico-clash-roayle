import os
import glob
import csv
from datetime import datetime

# Configurações
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')
YEAR_FILE = os.path.join(DATA_DIR, 'oponentes_ano_2026.csv')

FIELDNAMES = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente', 'trofes_oponente',
    'clan_oponente', 'resultado', 'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador', 
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente', 'vida_torres_princesa_jogador', 
    'vida_torres_princesa_oponente', 'trofes_iniciais_jogador', 'trofes_finais_jogador', 
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente',
    'torre_jogador', 'torre_oponente'
]

def parse_date(date_str):
    formats = ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

def make_dedup_key(row):
    dt = parse_date(row.get('data', ''))
    dt_str = dt.strftime('%Y-%m-%d %H:%M') if dt else row.get('data', '')
    return (dt_str, row.get('tag_oponente', '').strip().upper())

def consolidate():
    print("=" * 60)
    print("Consolidação de Dados 2026")
    print("=" * 60)

    all_battles = {}

    # 1. Carregar arquivo anual atual (se existir)
    if os.path.exists(YEAR_FILE):
        print(f"Lendo arquivo anual existente: {os.path.basename(YEAR_FILE)}")
        with open(YEAR_FILE, 'r', encoding='utf-8-sig') as f:
            # Detectar delimitador
            first_line = f.readline()
            f.seek(0)
            delim = ';' if ';' in first_line else ','
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                key = make_dedup_key(row)
                all_battles[key] = row

    # 2. Localizar arquivos diários e mensais de 2026
    patterns = [
        os.path.join(DATA_DIR, "oponentes_dia_2026*.csv"),
        os.path.join(DATA_DIR, "oponentes_mes_2026*.csv")
    ]
    
    files_to_process = []
    for p in patterns:
        files_to_process.extend(glob.glob(p))
    
    # Filtra para não incluir o próprio arquivo anual se ele cair no glob por algum motivo
    files_to_process = [f for f in files_to_process if "ano" not in os.path.basename(f)]

    print(f"Arquivos encontrados para processamento: {len(files_to_process)}")

    added_count = 0
    for filepath in files_to_process:
        print(f"  Processando {os.path.basename(filepath)}...")
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                # Detectar delimitador
                first_line = f.readline()
                f.seek(0)
                delim = ';' if ';' in first_line else ','
                reader = csv.DictReader(f, delimiter=delim)
                for row in reader:
                    key = make_dedup_key(row)
                    if key not in all_battles:
                        all_battles[key] = row
                        added_count += 1
        except Exception as e:
            print(f"    [ERRO] Falha ao ler {filepath}: {e}")

    # 3. Salvar arquivo anual consolidado
    print(f"\nTotal de batalhas únicas: {len(all_battles)}")
    print(f"Novas batalhas incorporadas: {added_count}")

    sorted_rows = sorted(
        all_battles.values(),
        key=lambda r: parse_date(r['data']) or datetime.min,
        reverse=True
    )

    with open(YEAR_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(sorted_rows)

    print(f"Arquivo {os.path.basename(YEAR_FILE)} atualizado com sucesso.")

    # 4. Limpeza (Opcional - mas recomendada para reduzir volume no Git)
    print("\nLimpando arquivos redundantes...")
    for filepath in files_to_process:
        try:
            os.remove(filepath)
            print(f"  Removido: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"  [ERRO] Falha ao remover {filepath}: {e}")

    print("\nConsolidação concluída!")

if __name__ == "__main__":
    consolidate()
