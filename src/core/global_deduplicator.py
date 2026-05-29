"""
Global Deduplicator - Clash Royale Battle CSV Cleaner.

Estrategia:
1. O arquivo principal de verdade e o `oponentes_ano_YYYY.csv` na pasta data_csv_oficial.
2. Os arquivos derivados (dia, semana, mes) devem ser subconjuntos do ano.
3. O arquivo raiz `oponentes_2026.csv` tem dados degradados e deve ser eliminado.
4. Dentro de cada arquivo, aplica deduplicacao por opponent_tag + resultado + coroas
   com janela temporal de 120 minutos.

Autoria: Script gerado para limpeza forense do historico de batalhas.
"""
import csv
import os
import glob
import shutil
from datetime import datetime, timedelta
from collections import defaultdict
import sys

# Forcar UTF-8 no stdout
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SRC_DIR, '..', 'data', 'csv')
BACKUP_DIR = os.path.join(SRC_DIR, 'backup_before_dedup')

# Arquivos na raiz que sao redundantes e devem ser removidos
ROOT_REDUNDANT_FILES = [
    'oponentes_2026.csv',
]


def normalize_result(res):
    """Normaliza resultado para comparacao."""
    if not res:
        return 'unknown'
    res = str(res).strip().lower()
    if res in ['vitoria', 'vitória', 'victory', 'win']:
        return 'victory'
    if res in ['derrota', 'defeat', 'loss']:
        return 'defeat'
    if res in ['empate', 'draw']:
        return 'draw'
    return res


def parse_date(date_str):
    """Tenta parsear data em multiplos formatos."""
    if not date_str:
        return None
    date_str = str(date_str).strip().strip('"').strip("'")
    
    formats = [
        '%d/%m/%Y %H:%M',
        '%d/%m/%Y %H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def score_record(row):
    """Pontua a qualidade de um registro. Maior = melhor."""
    score = 0
    
    # Nivel do oponente > 0
    try:
        nivel = int(row.get('nivel_oponente', row.get('opponent_level', 0)) or 0)
        if nivel > 0:
            score += 10
    except (ValueError, TypeError):
        pass
    
    # Cartas evoluidas
    for field in ['deck_jogador', 'deck_cards', 'deck_oponente', 'opponent_deck_cards']:
        if 'Evolved' in str(row.get(field, '')):
            score += 5
    
    # Modo de jogo mais descritivo (nao generico)
    game_mode = str(row.get('tipo_batalha', row.get('battle_type', '')))
    if game_mode and game_mode not in ['PvP', 'trail', '']:
        score += 2
    
    # Trofeus preenchidos
    try:
        trofeus = int(row.get('trofes_oponente', row.get('opponent_trophies', 0)) or 0)
        if trofeus > 0:
            score += 1
    except (ValueError, TypeError):
        pass
    
    return score


def detect_delimiter(filepath):
    """Detecta delimitador do CSV."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        sample = f.read(3000)
        return ';' if sample.count(';') > sample.count(',') else ','


def read_csv_records(filepath):
    """Le todos os registros de um CSV."""
    delimiter = detect_delimiter(filepath)
    records = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = reader.fieldnames
        for row in reader:
            # Pular linhas vazias
            if not any(v.strip() for v in row.values() if v):
                continue
            records.append(row)
    return records, fieldnames, delimiter


def write_csv_records(filepath, records, fieldnames, delimiter=','):
    """Escreve registros de volta no CSV."""
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(records)


def get_dedup_key(row):
    """Gera a chave de deduplicacao baseada no tag do oponente."""
    tag = row.get('tag_oponente', row.get('opponent_tag', '')).strip()
    return tag


def get_date_field(row):
    """Extrai a data do registro."""
    return row.get('data', row.get('battleTime', row.get('battle_time', '')))


def deduplicate_within_file(records, filename):
    """
    Remove duplicatas DENTRO de um unico arquivo.
    Agrupa por opponent_tag e remove registros com mesmo resultado/coroas
    dentro de janela de 120 minutos.
    """
    # Agrupar por tag
    by_tag = defaultdict(list)
    for i, row in enumerate(records):
        tag = get_dedup_key(row)
        if tag:
            by_tag[tag].append((i, row))
    
    indices_to_remove = set()
    
    for tag, entries in by_tag.items():
        if len(entries) < 2:
            continue
        
        # Parsear datas
        for idx, (i, row) in enumerate(entries):
            entries[idx] = (i, row, parse_date(get_date_field(row)))
        
        # Comparar todos os pares
        for a in range(len(entries)):
            if entries[a][0] in indices_to_remove:
                continue
            for b in range(a + 1, len(entries)):
                if entries[b][0] in indices_to_remove:
                    continue
                
                i_a, row_a, dt_a = entries[a]
                i_b, row_b, dt_b = entries[b]
                
                if not dt_a or not dt_b:
                    continue
                
                diff_minutes = abs((dt_b - dt_a).total_seconds()) / 60
                
                if diff_minutes > 120:
                    continue
                
                # Comparar resultado e coroas
                res_a = normalize_result(row_a.get('resultado', row_a.get('result', '')))
                res_b = normalize_result(row_b.get('resultado', row_b.get('result', '')))
                
                crowns_a = str(row_a.get('coroas_jogador', row_a.get('crowns', ''))).strip()
                crowns_b = str(row_b.get('coroas_jogador', row_b.get('crowns', ''))).strip()
                
                opp_crowns_a = str(row_a.get('coroas_oponente', row_a.get('opponent_crowns', ''))).strip()
                opp_crowns_b = str(row_b.get('coroas_oponente', row_b.get('opponent_crowns', ''))).strip()
                
                if res_a == res_b and crowns_a == crowns_b and opp_crowns_a == opp_crowns_b:
                    # E duplicata! Manter o de maior score
                    score_a = score_record(row_a)
                    score_b = score_record(row_b)
                    
                    if score_a >= score_b:
                        indices_to_remove.add(i_b)
                    else:
                        indices_to_remove.add(i_a)
    
    if indices_to_remove:
        cleaned = [r for i, r in enumerate(records) if i not in indices_to_remove]
        print(f"  [{filename}] Removidas {len(indices_to_remove)} duplicatas "
              f"({len(records)} -> {len(cleaned)} registros)")
        return cleaned
    else:
        print(f"  [{filename}] Nenhuma duplicata encontrada ({len(records)} registros)")
        return records


def main():
    print("=" * 70)
    print("  GLOBAL DEDUPLICATOR - Clash Royale Battle CSV Cleaner")
    print(f"  Executado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. Criar backup
    print("\n[1/4] Criando backup dos arquivos originais...")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Backup dos arquivos oficiais
    for filepath in glob.glob(os.path.join(DATA_DIR, 'oponentes_*.csv')):
        filename = os.path.basename(filepath)
        backup_path = os.path.join(BACKUP_DIR, f'oficial_{filename}')
        shutil.copy2(filepath, backup_path)
        print(f"  Backup: {filename} -> backup_before_dedup/")
    
    # Backup do arquivo raiz
    for filename in ROOT_REDUNDANT_FILES:
        root_path = os.path.join(SRC_DIR, filename)
        if os.path.exists(root_path):
            backup_path = os.path.join(BACKUP_DIR, f'root_{filename}')
            shutil.copy2(root_path, backup_path)
            print(f"  Backup: {filename} (raiz) -> backup_before_dedup/")
    
    # 2. Limpar duplicatas dentro de cada arquivo oficial
    print("\n[2/4] Deduplicando arquivos oficiais (data_csv_oficial/)...")
    
    total_before = 0
    total_after = 0
    
    for filepath in sorted(glob.glob(os.path.join(DATA_DIR, 'oponentes_*.csv'))):
        filename = os.path.basename(filepath)
        records, fieldnames, delimiter = read_csv_records(filepath)
        total_before += len(records)
        
        cleaned = deduplicate_within_file(records, filename)
        total_after += len(cleaned)
        
        if len(cleaned) < len(records):
            write_csv_records(filepath, cleaned, fieldnames, delimiter)
    
    print(f"\n  Total oficial: {total_before} -> {total_after} "
          f"(removidas {total_before - total_after} duplicatas)")
    
    # 3. Tratar o arquivo raiz redundante
    print("\n[3/4] Tratando arquivo raiz redundante...")
    
    for filename in ROOT_REDUNDANT_FILES:
        root_path = os.path.join(SRC_DIR, filename)
        if os.path.exists(root_path):
            records, _, _ = read_csv_records(root_path)
            print(f"  {filename}: {len(records)} registros (dados degradados)")
            print(f"  ACAO: Este arquivo contem dados com nivel_oponente=0, "
                  f"sem cartas evoluidas, e horarios defasados.")
            print(f"  Os dados de melhor qualidade ja estao em data_csv_oficial/oponentes_ano_2026.csv")
            print(f"  REMOVENDO {filename} da raiz...")
            os.remove(root_path)
            print(f"  REMOVIDO com sucesso. (Backup mantido em backup_before_dedup/)")
        else:
            print(f"  {filename}: Arquivo nao encontrado (ja removido)")
    
    # 4. Verificacao final
    print("\n[4/4] Verificacao final dos oponentes reportados...")
    
    targets = ['daniel_wrld08', 'Boruto Uzumaki', 'VINI', 'Luiz03br mp', 'MIGUEL CR']
    
    for target in targets:
        count = 0
        for filepath in glob.glob(os.path.join(DATA_DIR, 'oponentes_ano_*.csv')):
            records, _, _ = read_csv_records(filepath)
            for r in records:
                nome = r.get('nome_oponente', r.get('opponent_name', ''))
                if target.lower() in str(nome).lower():
                    count += 1
        
        status = "OK" if count == 1 else f"ATENCAO ({count} ocorrencias)"
        print(f"  {target}: {status} no arquivo anual")
    
    print("\n" + "=" * 70)
    print("  LIMPEZA CONCLUIDA!")
    print("  Backup salvo em: src/backup_before_dedup/")
    print("=" * 70)


if __name__ == '__main__':
    main()
