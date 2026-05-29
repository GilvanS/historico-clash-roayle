
import csv
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
api_token = os.getenv("CR_API_TOKEN")
player_tag = os.getenv("CR_PLAYER_TAG", "#2QR292P").replace('#', '')

def get_battle_log():
    url = f"https://proxy.royaleapi.dev/v1/players/%23{player_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Erro API: {e}")
        return []

def format_date_brt(battle_time_str):
    try:
        dt_utc = datetime.strptime(battle_time_str[:15], '%Y%m%dT%H%M%S')
        return (dt_utc - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    except:
        return ""

print("--- Buscando na API ---")
battles = get_battle_log()
found_in_api = 0
for b in battles:
    b_date = format_date_brt(b.get('battleTime', ''))
    if any(d in b_date for d in dates):
        found_in_api += 1
        print(f"Encontrada na API: {b_date} vs {b.get('opponent', [{}])[0].get('name')}")

print(f"Total encontrado na API para essas datas: {found_in_api}")

print("\n--- Verificando Arquivo Restaurado (Encoding Fix) ---")
restored_path = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\backups\oponentes_ano_2026_restaurado.csv"
if os.path.exists(restored_path):
    # Tenta varios encodings
    for enc in ['utf-16', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            with open(restored_path, 'r', encoding=enc) as f:
                content = f.read(100)
                # Se leu algo razoavel, tenta o csv
                f.seek(0)
                reader = csv.DictReader(f, delimiter=';')
                total_restored = 0
                missing_hp_restored = 0
                for row in reader:
                    if any(d in row.get('data', '') for d in dates):
                        total_restored += 1
                        if row.get('vida_torre_rei_jogador', '0') in ["0", ""]:
                            missing_hp_restored += 1
                print(f"Encoding {enc}: Total {total_restored}, Faltando HP {missing_hp_restored}")
                if total_restored > 0:
                    break
        except Exception as e:
            continue
else:
    print("Arquivo restaurado nao encontrado.")
