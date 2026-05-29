import os
import csv
import sys

# Força o encoding para UTF-8 no stdout/stderr para evitar o erro de charmap no Windows
if sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

def sync_identity():
    # Nickname oficial capturado da API (ツ Arcade Delta Я λ Σ ☯︎)
    official_nick = "\u30c4 \ufe7b\u30c7\u2550\u4e00\u27ff\u0394\u042f\u20a1\u03bb\u2181\u03a3\u262f\ufe0e"
    player_tag = "#2QR292P"
    
    # 1. Atualizar .env
    env_path = "a:/Workspace/historico-clash-roayle/.env"
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        new_lines = []
        found_nick = False
        for line in lines:
            if line.startswith("PLAYER_NICKNAME="):
                new_lines.append(f"PLAYER_NICKNAME={official_nick}\n")
                found_nick = True
            else:
                new_lines.append(line)
        
        if not found_nick:
            new_lines.append(f"PLAYER_NICKNAME={official_nick}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception:
        pass

    # 2. Atualizar players.csv
    csv_path = "a:/Workspace/historico-clash-roayle/src/data_csv_oficial/players.csv"
    try:
        players = []
        # Cabeçalho: player_tag;name;trophies;best_trophies;level;clan_tag;clan_name;last_updated
        header = "player_tag;name;trophies;best_trophies;level;clan_tag;clan_name;last_updated".split(";")
        
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                players = list(reader)
        
        found = False
        for p in players:
            if p['player_tag'] == player_tag:
                p['name'] = official_nick
                found = True
                break
        
        if not found:
            # Se não encontrar, adicionamos uma entrada básica (os outros dados serão preenchidos na próxima coleta)
            players.append({
                'player_tag': player_tag,
                'name': official_nick,
                'trophies': '0',
                'best_trophies': '0',
                'level': '0',
                'clan_tag': '',
                'clan_name': '',
                'last_updated': '2026-05-03'
            })
            
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header, delimiter=";")
            writer.writeheader()
            writer.writerows(players)
    except Exception:
        pass

if __name__ == "__main__":
    sync_identity()
