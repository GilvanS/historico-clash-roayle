
import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
api_token = os.getenv("CR_API_TOKEN")
player_tag = os.getenv("CR_PLAYER_TAG", "#2QR292P").replace('#', '')

# URL OFICIAL DO SWAGGER (sem proxy)
url = f"https://api.clashroyale.com/v1/players/%23{player_tag}/battlelog"
headers = {"Authorization": f"Bearer {api_token}"}

def format_date_brt(battle_time_str):
    try:
        dt_utc = datetime.strptime(battle_time_str[:15], '%Y%m%dT%H%M%S')
        return (dt_utc - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    except:
        return ""

print(f"Consultando API OFICIAL SWAGGER para #{player_tag}...")
try:
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 403:
        print("Erro 403: Token invalido ou IP nao autorizado na Whitelist da Supercell.")
    else:
        resp.raise_for_status()
        battles = resp.json()
        print(f"Total de batalhas retornadas: {len(battles)}")
        
        target_dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
        found = 0
        for b in battles:
            b_date = format_date_brt(b.get('battleTime', ''))
            if any(d in b_date for d in target_dates):
                found += 1
                print(f"Encontrada: {b_date} vs {b.get('opponent', [{}])[0].get('name')}")
        
        if found == 0:
            print("\nAVISO: Nenhuma batalha das datas 30/04 a 03/05 encontrada no log oficial.")
            print("Isso ocorre porque a API so mantem as ultimas 25 batalhas.")
        else:
            print(f"\nSucesso! {found} batalhas encontradas.")
            
except Exception as e:
    print(f"Erro: {e}")
