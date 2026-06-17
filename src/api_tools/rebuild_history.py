
import csv
import os
import glob
from datetime import datetime

def detect_encoding(path):
    with open(path, 'rb') as f:
        raw = f.read(4)
        if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
            return 'utf-16'
        return 'utf-8-sig'

def detect_delimiter(path, encoding):
    with open(path, 'r', encoding=encoding, errors='ignore') as f:
        first_line = f.readline()
        if ';' in first_line:
            return ';'
        return ','

def rebuild():
    data_dir = 'a:/Workspace/historico-clash-roayle/src/data_csv_oficial'
    files = glob.glob(os.path.join(data_dir, 'oponentes_*.csv'))
    # Include the recovered file
    files.append(os.path.join(data_dir, f'oponentes_ano_{datetime.now().year}_recovered.csv'))
    
    all_battles = {} # Key: (time, opponent_tag)
    
    # Standard header from collect_battles_csv.py
    header = [
        "data", "nome_oponente", "tag_oponente", "nivel_oponente", "trofes_oponente", 
        "clan_oponente", "resultado", "coroas_jogador", "coroas_oponente", 
        "mudanca_trofes", "modo_jogo", "tipo_batalha", "arena", 
        "deck_jogador", "deck_oponente", "vezes_enfrentado", 
        "elixir_vazado_jogador", "elixir_vazado_oponente", "nivel_torre_jogador", 
        "vida_torre_rei_jogador", "vida_torre_rei_oponente", "vida_torres_princesa_jogador", 
        "vida_torres_princesa_oponente", "trofes_iniciais_jogador", "trofes_finais_jogador", 
        "posicao_global_jogador", "posicao_global_oponente", "nivel_torre_oponente", "player_tag"
    ]

    # Mapping from possible input names to our standard header
    mapping = {
        "data": ["data", "date"],
        "nome_oponente": ["nome_oponente", "oponente", "opponent_name", "opponent"],
        "tag_oponente": ["tag_oponente", "tag do oponente", "opponent_tag"],
        "nivel_oponente": ["nivel_oponente", "opponent_level"],
        "trofes_oponente": ["trofes_oponente", "trofeus do oponente", "opponent_trophies"],
        "clan_oponente": ["clan_oponente", "clã do oponente", "clã do oponente", "opponent_clan"],
        "resultado": ["resultado", "result"],
        "coroas_jogador": ["coroas_jogador", "coroas do jogador", "crowns", "player_crowns"],
        "coroas_oponente": ["coroas_oponente", "coroas do oponente", "opponent_crowns"],
        "mudanca_trofes": ["mudanca_trofes", "trofeus ganhos/perdidos", "trophy_change"],
        "modo_jogo": ["modo_jogo", "modo de jogo", "game_mode"],
        "tipo_batalha": ["tipo_batalha", "tipo de batalha", "battle_type"],
        "arena": ["arena"],
        "deck_jogador": ["deck_jogador", "deck do jogador", "player_deck"],
        "deck_oponente": ["deck_oponente", "deck do oponente", "opponent_deck"],
        "player_tag": ["player_tag", "tag do jogador"]
    }

    count_total = 0

    for file in files:
        if not os.path.exists(file): continue
        if os.path.getsize(file) == 0: continue
        if 'consolidated' in file: continue # Skip our own output if it exists
        
        encoding = detect_encoding(file)
        delim = detect_delimiter(file, encoding)
        print(f"Processing {file} with encoding '{encoding}' and delimiter '{delim}'...")
        
        with open(file, 'r', encoding=encoding, errors='ignore') as f:
            reader = csv.reader(f, delimiter=delim)
            try:
                rows = list(reader)
            except:
                print(f"Error reading {file}")
                continue
                
            if not rows or len(rows) < 2: continue
            
            file_header = [h.strip().lower() for h in rows[0]]
            
            def get_val(row, target_field):
                possible_names = mapping.get(target_field, [target_field])
                for name in possible_names:
                    if name in file_header:
                        idx = file_header.index(name)
                        if idx < len(row):
                            return row[idx].strip()
                return ""

            # Check if this file has Data and Tag
            idx_data = -1
            for n in mapping["data"]:
                if n in file_header:
                    idx_data = file_header.index(n)
                    break
            
            idx_tag = -1
            for n in mapping["tag_oponente"]:
                if n in file_header:
                    idx_tag = file_header.index(n)
                    break

            if idx_data == -1 or idx_tag == -1:
                print(f"Skipping {file}: Required columns (Data/Tag) not found")
                continue

            for row in rows[1:]:
                count_total += 1
                if len(row) <= max(idx_data, idx_tag): continue
                
                b_time_str = row[idx_data].strip()
                opp_tag = row[idx_tag].strip()
                
                if not b_time_str or not opp_tag or opp_tag == 'None' or len(opp_tag) < 3:
                    continue
                
                if not b_time_str[0].isdigit():
                    continue

                key = (b_time_str, opp_tag)
                
                # Normalize row
                new_row = [""] * len(header)
                for i, h_name in enumerate(header):
                    new_row[i] = get_val(row, h_name)
                
                # Fill player_tag if missing
                if not new_row[header.index("player_tag")]:
                    new_row[header.index("player_tag")] = "#2QR292P"
                
                # Update/Insert logic: keep the row with more data
                if key not in all_battles or len("".join(new_row)) > len("".join(all_battles[key])):
                    all_battles[key] = new_row

    print(f"Total rows processed: {count_total}")
    print(f"Unique valid battles found: {len(all_battles)}")

    # Sort
    sorted_battles = sorted(all_battles.values(), key=lambda x: x[0], reverse=True)

    output_path = os.path.join(data_dir, f'oponentes_ano_{datetime.now().year}_consolidated.csv')
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f: # Use utf-8-sig for Excel compatibility
        writer = csv.writer(f, delimiter=';')
        writer.writerow(header)
        writer.writerows(sorted_battles)

    print(f"Saved {len(sorted_battles)} battles to {output_path}")

if __name__ == "__main__":
    rebuild()
