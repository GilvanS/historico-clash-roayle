import sqlite3
import os

def sync_battles():
    print("Iniciando sincronizacao de dados entre oponentes.db e clash_royale.db...")
    
    # Connect to both databases
    clash_db_path = "src/clash_royale.db"
    oponentes_db_path = "src/oponentes.db"
    
    if not os.path.exists(clash_db_path) or not os.path.exists(oponentes_db_path):
        print(f"Erro: Bancos de dados nao encontrados. Certifique-se de executar na pasta src.")
        return

    clash_conn = sqlite3.connect(clash_db_path)
    oponentes_conn = sqlite3.connect(oponentes_db_path)
    
    clash_cur = clash_conn.cursor()
    oponentes_cur = oponentes_conn.cursor()
    
    # Get all battles from oponentes.db
    oponentes_cur.execute("""
        SELECT 
            player_tag, battle_time, arena, modo_jogo, resultado, tipo_batalha, 
            coroas_jogador, coroas_oponente, tag_oponente, nome_oponente, mudanca_trofes
        FROM oponentes_batalhas
    """)
    source_battles = oponentes_cur.fetchall()
    
    print(f"Lidas {len(source_battles)} batalhas do oponentes.db.")
    
    # Get existing battles in clash_royale.db to avoid duplicates
    # Since battle_time is unique per player_tag
    clash_cur.execute("SELECT battle_time FROM battles WHERE player_tag = '#2QR292P'")
    existing_times = {row[0] for row in clash_cur.fetchall()}
    
    inserted_count = 0
    for battle in source_battles:
        player_tag = battle[0]
        battle_time = battle[1]
        
        # Oponentes CSV and DB might not have the correct ISO for # character
        if not player_tag.startswith('#'):
            player_tag = '#' + player_tag

        if battle_time in existing_times:
            continue
            
        arena_name = battle[2]
        game_mode = battle[3]
        
        # Translate resultado
        resultado_str = battle[4].lower() if battle[4] else ""
        if 'vitoria' in resultado_str or 'victory' in resultado_str:
            result = 'victory'
        elif 'derrota' in resultado_str or 'defeat' in resultado_str:
            result = 'defeat'
        else:
            result = 'draw'
            
        battle_type = battle[5]
        team_crowns = battle[6]
        opponent_crowns = battle[7]
        opponent_tag = battle[8]
        if opponent_tag and not opponent_tag.startswith('#'):
            opponent_tag = '#' + opponent_tag
        opponent_name = battle[9]
        trophy_change = battle[10]
        
        is_ladder = 1 if battle_type in ['pathOfLegend', 'Ranked1v1', 'PvP'] else 0
        arena_id = 0 # Default since we don't have mapping here, html_generator doesn't use it much
        
        try:
            clash_cur.execute("""
                INSERT INTO battles (
                    player_tag, battle_time, arena_id, arena_name, game_mode, battle_type, result,
                    crowns, opponent_tag, opponent_name, is_ladder_tournament, trophy_change
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_tag, battle_time, arena_id, arena_name, game_mode, battle_type, result,
                team_crowns, opponent_tag, opponent_name, is_ladder, trophy_change
            ))
            inserted_count += 1
            existing_times.add(battle_time)
        except sqlite3.IntegrityError:
            pass # Already exists
            
    clash_conn.commit()
    print(f"Sincronizacao concluida! {inserted_count} batalhas novas inseridas no clash_royale.db.")
    
    clash_conn.close()
    oponentes_conn.close()

if __name__ == "__main__":
    sync_battles()
