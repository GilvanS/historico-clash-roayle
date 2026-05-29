import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

api_token = os.getenv("CR_API_TOKEN")
player_tag = os.getenv("CR_PLAYER_TAG", "#2QR292P")

def get_battle_log():
    clean_tag = player_tag.replace('#', '')
    url = f"https://proxy.royaleapi.dev/v1/players/%23{clean_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"Error fetching log: {resp.status_code} - {resp.text}")
        return []

def parse_time(ts):
    # 20260429T230000.000Z
    return datetime.strptime(ts[:15], '%Y%m%dT%H%M%S')

def format_hp(hp_list):
    if hp_list is None: return "0"
    if isinstance(hp_list, int): return str(hp_list)
    return " | ".join(map(str, hp_list))

log = get_battle_log()
target_dates = ["20260430", "20260501", "20260502", "20260503"]

found = []
for b in log:
    bt = b.get('battleTime', '')
    if not bt: continue
    
    dt = parse_time(bt)
    dt_str = dt.strftime('%Y%m%d')
    
    if dt_str in target_dates:
        # Extrair dados do jogador
        team = b.get('team', [{}])[0]
        opponent = b.get('opponent', [{}])[0]
        
        # O oponente as vezes tem torres com 0 se ele ganhou de 3 coroas?
        # Na verdade queremos o HP final
        
        row = {
            'data': dt.strftime('%d/%m/%Y %H:%M'),
            'tag_oponente': opponent.get('tag'),
            'nome_oponente': opponent.get('name'),
            'nivel_torre_jogador': team.get('startingTowerHp', 0), # No battlelog da API as vezes so tem starting
            'vida_torre_rei_jogador': team.get('kingTowerHitPoints', 0),
            'vida_torre_rei_oponente': opponent.get('kingTowerHitPoints', 0),
            'vida_torres_princesa_jogador': format_hp(team.get('princessTowersHitPoints')),
            'vida_torres_princesa_oponente': format_hp(opponent.get('princessTowersHitPoints')),
        }
        found.append(row)

print(json.dumps(found, indent=2))
