
import os
import sys
import logging
from datetime import datetime

# Add src to path
sys.path.append('src')

from html_generator import GitHubPagesHTMLGenerator

def diagnostic():
    generator = GitHubPagesHTMLGenerator()
    
    print("--- Diagnostics ---")
    all_rows = generator.load_all_data_rows()
    print(f"Total rows in all_rows: {len(all_rows)}")
    
    if len(all_rows) > 0:
        print(f"First row keys: {list(all_rows[0].keys())}")
        print(f"First row _dt: {all_rows[0].get('_dt')}")
        print(f"First row battle_time: {all_rows[0].get('battle_time')}")
        print(f"First row opponent_tag: {all_rows[0].get('opponent_tag')}")
    
    repeated = generator.get_repeated_opponents_from_csv()
    print(f"Total repeated opponents found: {len(repeated)}")
    
    if len(repeated) == 0:
        print("\nChecking why repeated is empty...")
        opp_stats = {}
        processed_battle_ids = set()
        
        for i, b in enumerate(all_rows):
            t_tag = (b.get('tag_oponente') or b.get('opponent_tag') or '').strip().upper()
            if not t_tag.startswith('#'): t_tag = '#' + t_tag
            
            b_dt = b.get('dt') or b.get('battle_time')
            battle_id = b.get('id') or f"{b_dt}_{t_tag}_{b.get('deck_jogador')}"
            
            if battle_id in processed_battle_ids:
                if i < 20: print(f"Row {i} skipped: duplicate battle_id {battle_id}")
                continue
            processed_battle_ids.add(battle_id)
            
            tag = t_tag
            if not tag or tag == '#':
                if i < 20: print(f"Row {i} skipped: empty tag")
                continue

            game_mode = (b.get('modo_jogo') or b.get('game_mode') or '').lower()
            if 'boatbattle' in game_mode or 'barco' in game_mode:
                if i < 20: print(f"Row {i} skipped: boat battle")
                continue
                
            if tag not in opp_stats:
                opp_stats[tag] = {'total_battles': 0}
            opp_stats[tag]['total_battles'] += 1
            
        print(f"Total unique opponents processed: {len(opp_stats)}")
        for tag, stats in list(opp_stats.items())[:10]:
            print(f"Opponent {tag}: {stats['total_battles']} battles")
            
        count_multiple = sum(1 for s in opp_stats.values() if s['total_battles'] > 1)
        print(f"Opponents with multiple battles: {count_multiple}")

if __name__ == "__main__":
    diagnostic()
