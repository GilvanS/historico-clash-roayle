"""
Script de Analise Forense de Duplicatas.
Analisa cada caso reportado pelo usuario para determinar se sao:
  - Duplicatas reais (mesma batalha registrada 2x pela API)
  - Lutas legitimas repetidas (clan wars, amigos, favoritos)

Criterios de identificacao de DUPLICATA REAL:
  1. Mesmo opponent_tag
  2. Mesmo resultado (normalizado)
  3. Mesmas coroas (jogador e oponente)
  4. Mesma mudanca de trofeus
  5. Diferenca de tempo < 120 minutos
  6. Um registro tem dados "ricos" (Evolved cards, nivel > 0) e outro "pobre"
"""
import csv
import os
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'data', 'csv')
ROOT_DIR = os.path.dirname(__file__)

# Oponentes reportados como duplicatas pelo usuario
TARGETS = [
    'daniel_wrld08',
    'Boruto Uzumaki',
    'VINI',  # Pode aparecer como VINI ou VINI✨鬼滅
    'Luiz03br mp',
    'MIGUEL CR'
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
    
    # Nivel do oponente > 0 = dado mais rico
    try:
        nivel = int(row.get('nivel_oponente', row.get('opponent_level', 0)))
        if nivel > 0:
            score += 10
    except (ValueError, TypeError):
        pass
    
    # Cartas evoluidas no deck
    deck = row.get('deck_jogador', row.get('deck_cards', ''))
    if 'Evolved' in str(deck):
        score += 5
    
    opp_deck = row.get('deck_oponente', row.get('opponent_deck_cards', ''))
    if 'Evolved' in str(opp_deck):
        score += 5
    
    # Modo de jogo em ingles padrao (mais completo)
    game_mode = row.get('tipo_batalha', row.get('battle_type', ''))
    if game_mode and game_mode not in ['PvP']:
        score += 2
    
    # Vezes enfrentado > 1 = dado com historico
    try:
        vezes = int(row.get('vezes_enfrentado', 1))
        if vezes > 1:
            score += 1
    except (ValueError, TypeError):
        pass
    
    return score

def load_all_records():
    """Carrega todos os registros de todos os CSVs de oponentes."""
    all_records = []
    
    # Caminhos para buscar
    import glob
    patterns = [
        os.path.join(ROOT_DIR, 'oponentes_*.csv'),
        os.path.join(DATA_DIR, 'oponentes_*.csv'),
    ]
    
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            filename = os.path.basename(filepath)
            try:
                # Detectar delimitador
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    sample = f.read(2000)
                    delimiter = ';' if sample.count(';') > sample.count(',') else ','
                
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    for row in reader:
                        row['_source_file'] = filename
                        row['_source_path'] = filepath
                        all_records.append(row)
            except Exception as e:
                print(f"  [ERRO] Falha ao ler {filename}: {e}")
    
    return all_records

def analyze_target(records, target_name):
    """Analisa registros de um oponente especifico."""
    # Filtra registros que contem o nome alvo
    matching = []
    for r in records:
        nome = r.get('nome_oponente', r.get('opponent_name', ''))
        if target_name.lower() in str(nome).lower():
            matching.append(r)
    
    if not matching:
        print(f"\n{'='*60}")
        print(f"  {target_name}: NENHUM REGISTRO ENCONTRADO")
        return []
    
    print(f"\n{'='*60}")
    print(f"  ANALISE: {target_name} ({len(matching)} registros encontrados)")
    print(f"{'='*60}")
    
    # Agrupar por tag do oponente
    by_tag = defaultdict(list)
    for r in matching:
        tag = r.get('tag_oponente', r.get('opponent_tag', 'UNKNOWN'))
        by_tag[tag].append(r)
    
    duplicates_found = []
    
    for tag, tag_records in by_tag.items():
        print(f"\n  Tag: {tag} ({len(tag_records)} registros)")
        
        # Ordenar por data
        for r in tag_records:
            data_str = r.get('data', r.get('battleTime', r.get('battle_time', '')))
            r['_parsed_date'] = parse_date(data_str)
        
        tag_records.sort(key=lambda x: x['_parsed_date'] or datetime.min)
        
        # Mostrar cada registro
        for i, r in enumerate(tag_records):
            data_str = r.get('data', r.get('battleTime', r.get('battle_time', '')))
            resultado = r.get('resultado', r.get('result', ''))
            coroas = r.get('coroas_jogador', r.get('crowns', ''))
            coroas_opp = r.get('coroas_oponente', r.get('opponent_crowns', ''))
            trofeus = r.get('mudanca_trofeus', r.get('trophy_change', ''))
            nivel = r.get('nivel_oponente', r.get('opponent_level', ''))
            tipo = r.get('tipo_batalha', r.get('battle_type', ''))
            game_mode = r.get('modo_jogo', r.get('game_mode', ''))
            deck = r.get('deck_jogador', r.get('deck_cards', ''))[:60]
            source = r.get('_source_file', '')
            score = score_record(r)
            
            has_evolved = 'Evolved' in str(r.get('deck_jogador', r.get('deck_cards', '')))
            
            print(f"\n  [{i+1}] Data: {data_str}")
            print(f"      Resultado: {resultado} | Coroas: {coroas}-{coroas_opp} | Trofeus: {trofeus}")
            print(f"      Nivel Opp: {nivel} | Tipo: {tipo} | Modo: {game_mode}")
            print(f"      Evolved?: {'SIM' if has_evolved else 'NAO'} | Score: {score}")
            print(f"      Fonte: {source}")
        
        # Comparar pares para detectar duplicatas
        print(f"\n  --- DIAGNOSTICO ---")
        for i in range(len(tag_records)):
            for j in range(i + 1, len(tag_records)):
                r1, r2 = tag_records[i], tag_records[j]
                
                dt1 = r1['_parsed_date']
                dt2 = r2['_parsed_date']
                
                if not dt1 or not dt2:
                    continue
                
                diff_minutes = abs((dt2 - dt1).total_seconds()) / 60
                
                res1 = normalize_result(r1.get('resultado', r1.get('result', '')))
                res2 = normalize_result(r2.get('resultado', r2.get('result', '')))
                
                crowns1 = r1.get('coroas_jogador', r1.get('crowns', ''))
                crowns2 = r2.get('coroas_jogador', r2.get('crowns', ''))
                
                opp_crowns1 = r1.get('coroas_oponente', r1.get('opponent_crowns', ''))
                opp_crowns2 = r2.get('coroas_oponente', r2.get('opponent_crowns', ''))
                
                trophy1 = r1.get('mudanca_trofeus', r1.get('trophy_change', ''))
                trophy2 = r2.get('mudanca_trofeus', r2.get('trophy_change', ''))
                
                same_result = (res1 == res2)
                same_crowns = (str(crowns1) == str(crowns2) and str(opp_crowns1) == str(opp_crowns2))
                same_trophies = (str(trophy1) == str(trophy2))
                
                # Verificar se e luta friendly/showdown (pode ser re-match legitimo)
                tipo1 = str(r1.get('tipo_batalha', r1.get('battle_type', ''))).lower()
                tipo2 = str(r2.get('tipo_batalha', r2.get('battle_type', ''))).lower()
                is_friendly = any(x in tipo1 for x in ['friendly', 'showdown', 'trail']) or \
                              any(x in tipo2 for x in ['friendly', 'showdown', 'trail'])
                
                # Verificar se os fontes sao diferentes (root vs oficial)
                src1 = r1.get('_source_file', '')
                src2 = r2.get('_source_file', '')
                different_sources = (src1 != src2)
                
                # Score de cada registro
                s1 = score_record(r1)
                s2 = score_record(r2)
                
                print(f"\n  Par [{i+1}] vs [{j+1}]:")
                print(f"    Diferenca temporal: {diff_minutes:.0f} minutos")
                print(f"    Mesmo resultado? {same_result} ({res1} vs {res2})")
                print(f"    Mesmas coroas? {same_crowns} ({crowns1}-{opp_crowns1} vs {crowns2}-{opp_crowns2})")
                print(f"    Mesmos trofeus? {same_trophies} ({trophy1} vs {trophy2})")
                print(f"    Luta amigavel? {is_friendly}")
                print(f"    Fontes diferentes? {different_sources} ({src1} vs {src2})")
                print(f"    Scores: [{i+1}]={s1} vs [{j+1}]={s2}")
                
                # VEREDICTO
                is_duplicate = False
                reason = ""
                
                if same_result and same_crowns and same_trophies and diff_minutes <= 120:
                    is_duplicate = True
                    reason = f"DUPLICATA REAL - Mesma batalha com {diff_minutes:.0f}min de atraso na API"
                elif same_result and same_crowns and diff_minutes <= 120 and different_sources:
                    is_duplicate = True
                    reason = f"DUPLICATA PROVAVEL - Fontes diferentes, dados compativeis, {diff_minutes:.0f}min"
                elif is_friendly and same_result and same_crowns and diff_minutes <= 120:
                    is_duplicate = True
                    reason = f"DUPLICATA (friendly) - Mesma luta amigavel registrada 2x, {diff_minutes:.0f}min"
                elif not same_result or not same_crowns:
                    reason = f"LUTA LEGITIMA - Resultado ou coroas diferentes (rematch real)"
                elif diff_minutes > 120:
                    reason = f"LUTA LEGITIMA - Intervalo grande demais ({diff_minutes:.0f}min), provavel rematch"
                
                if is_duplicate:
                    print(f"    >>> VEREDICTO: {reason}")
                    # Qual manter?
                    keep = i+1 if s1 >= s2 else j+1
                    remove = j+1 if s1 >= s2 else i+1
                    print(f"    >>> ACAO: MANTER [{keep}] (score={max(s1,s2)}), REMOVER [{remove}] (score={min(s1,s2)})")
                    duplicates_found.append({
                        'keep': tag_records[keep-1],
                        'remove': tag_records[remove-1],
                        'reason': reason
                    })
                else:
                    print(f"    >>> VEREDICTO: {reason}")
    
    return duplicates_found

def main():
    print("=" * 60)
    print("  ANALISE FORENSE DE DUPLICATAS - Clash Royale")
    print("  Data: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 60)
    
    print("\nCarregando todos os registros...")
    records = load_all_records()
    print(f"Total de registros carregados: {len(records)}")
    
    all_duplicates = []
    
    for target in TARGETS:
        dupes = analyze_target(records, target)
        all_duplicates.extend(dupes)
    
    # Resumo final
    print(f"\n{'='*60}")
    print(f"  RESUMO FINAL")
    print(f"{'='*60}")
    print(f"  Duplicatas reais encontradas: {len(all_duplicates)}")
    
    for i, d in enumerate(all_duplicates):
        nome = d['remove'].get('nome_oponente', d['remove'].get('opponent_name', ''))
        data_rem = d['remove'].get('data', d['remove'].get('battleTime', ''))
        data_keep = d['keep'].get('data', d['keep'].get('battleTime', ''))
        src_rem = d['remove'].get('_source_file', '')
        print(f"\n  [{i+1}] {nome}")
        print(f"      Remover: {data_rem} (de {src_rem})")
        print(f"      Manter:  {data_keep}")
        print(f"      Motivo:  {d['reason']}")

if __name__ == '__main__':
    main()
