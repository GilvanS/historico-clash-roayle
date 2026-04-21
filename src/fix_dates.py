import sqlite3
from datetime import datetime, timedelta
import os
from collections import Counter

db_path = "oponentes.db"

def format_date_for_query(dt):
    return dt.strftime('%Y%m%dT%H%M%S')

def generate_csv_for_date(player_tag, target_date_brt):
    brt_offset = timedelta(hours=-3)
    
    dia_inicio_brt = target_date_brt.replace(hour=0, minute=0, second=0, microsecond=0)
    dia_fim_brt = target_date_brt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    dia_inicio = dia_inicio_brt - brt_offset
    dia_fim = dia_fim_brt - brt_offset
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    inicio_str = format_date_for_query(dia_inicio)
    fim_str = format_date_for_query(dia_fim)
    arquivo = f"oponentes_dia_{target_date_brt.strftime('%Y%m%d')}.csv"
    
    query = """
        SELECT * FROM oponentes_batalhas 
        WHERE player_tag = ? 
        AND substr(battle_time, 1, 15) >= ? 
        AND substr(battle_time, 1, 15) <= ?
        ORDER BY battle_time DESC
    """
    cursor.execute(query, (player_tag, inicio_str, fim_str))
    rows = cursor.fetchall()
    
    if not rows:
        print(f"Nenhuma batalha para {arquivo}.")
        conn.close()
        return
        
    opponents_data = []
    for row in rows:
        opponents_data.append({
            'data': row[3],
            'nome_oponente': row[4],
            'tag_oponente': row[5],
            'nivel_oponente': row[6],
            'trofes_oponente': row[7],
            'clan_oponente': row[8],
            'resultado': row[9],
            'coroas_jogador': row[10],
            'coroas_oponente': row[11],
            'mudanca_trofes': row[12],
            'modo_jogo': row[13],
            'tipo_batalha': row[14],
            'arena': row[15],
            'deck_jogador': row[16],
            'deck_oponente': row[17]
        })
    
    opponent_tags = [op['tag_oponente'] for op in opponents_data if op['tag_oponente']]
    opponent_counts = Counter(opponent_tags)
    
    for opponent_info in opponents_data:
        tag = opponent_info['tag_oponente']
        count = opponent_counts.get(tag, 0)
        opponent_info['vezes_enfrentado'] = count
    
    import csv
    with open(arquivo, 'w', newline='', encoding='utf-8') as f:
        keys = list(opponents_data[0].keys())
        writer = csv.DictWriter(f, fieldnames=keys, delimiter=';')
        writer.writeheader()
        writer.writerows(opponents_data)
        
    print(f"Gerado {arquivo} com {len(opponents_data)} batalhas.")
    conn.close()

if __name__ == '__main__':
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT player_tag FROM oponentes_batalhas LIMIT 1")
    res = cursor.fetchone()
    conn.close()
    
    if res:
        tag = res[0]
        # Target 2026-04-20 and 2026-04-21
        date_20 = datetime(2026, 4, 20)
        date_21 = datetime(2026, 4, 21)
        generate_csv_for_date(tag, date_20)
        generate_csv_for_date(tag, date_21)
        
        # also delete the wrong 21 if it's empty, or wait we just created it anyway.
    else:
        print("Player tag nao encontrada.")
