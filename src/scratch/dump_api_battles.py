
import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
api_token = os.getenv("CR_API_TOKEN")
player_tag = os.getenv("CR_PLAYER_TAG", "#2QR292P").replace('#', '')

def format_date_brt(battle_time_str):
    try:
        dt_utc = datetime.strptime(battle_time_str[:15], '%Y%m%dT%H%M%S')
        return (dt_utc - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    except:
        return ""

url = f"https://proxy.royaleapi.dev/v1/players/%23{player_tag}/battlelog"
headers = {"Authorization": f"Bearer {api_token}"}

print(f"Buscando log completo para #{player_tag}...")
try:
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    battles = resp.json()
    
    target_dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
    found_battles = []
    
    for b in battles:
        b_date = format_date_brt(b.get('battleTime', ''))
        if any(d in b_date for d in target_dates):
            found_battles.append(b)
            print(f"Encontrada: {b_date} vs {b.get('opponent', [{}])[0].get('name')}")
    
    if found_battles:
        with open(r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\recuperacao_raw_api.json", "w", encoding="utf-8") as f:
            json.dump(found_battles, f, indent=4, ensure_ascii=False)
        print(f"\nSucesso! {len(found_battles)} batalhas salvas em recuperacao_raw_api.json")
    else:
        print("\nNenhuma batalha dessas datas encontrada no log atual da API (limite de 25 registros).")

except Exception as e:
    print(f"Erro: {e}")
