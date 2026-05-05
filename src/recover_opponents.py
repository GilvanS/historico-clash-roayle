import os
import csv
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('a:/Workspace/historico-clash-roayle/.env')
api_token = os.getenv('CR_API_TOKEN')

def get_player_level(tag):
    clean_tag = tag.replace('#', '')
    url = f"https://proxy.royaleapi.dev/v1/players/%23{clean_tag}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    
    # Try proxy first
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get('expLevel')
    
    # Fallback to battlelog to check if we can get it from there if proxy players/ fails
    # Wait, battlelog doesn't have the player's own expLevel easily, but let's try official API
    url_official = f"https://api.clashroyale.com/v1/players/%23{clean_tag}"
    r2 = requests.get(url_official, headers=headers)
    if r2.status_code == 200:
        return r2.json().get('expLevel')
    
    return None

file_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'

def recover_data():
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        fieldnames = reader.fieldnames
        rows = list(reader)
        
    updated_count = 0
    for row in rows:
        data_str = row.get('data', '')
        if not data_str: continue
        try:
            dt = datetime.strptime(data_str, '%d/%m/%Y %H:%M')
        except ValueError:
            continue
        
        if datetime(2026, 4, 30) <= dt <= datetime(2026, 5, 5, 23, 59, 59):
            nivel = row.get('nivel_oponente', '')
            if not nivel or str(nivel) == '0' or str(nivel) == '':
                tag = row.get('tag_oponente', '')
                if tag:
                    level = get_player_level(tag)
                    if level:
                        row['nivel_oponente'] = level
                        row['nivel_torre_oponente'] = level
                        updated_count += 1
                        print(f"Updated {tag} to level {level}")
                    else:
                        print(f"Failed to get level for {tag}")
                    time.sleep(0.5)
    
    if updated_count > 0:
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSuccessfully updated {updated_count} battles!")
    else:
        print("\nNo battles were updated.")

if __name__ == '__main__':
    recover_data()
