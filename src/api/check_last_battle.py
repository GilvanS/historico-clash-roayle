import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def check_last_battle():
    token = os.getenv('CR_API_TOKEN')
    tag = os.getenv('CR_PLAYER_TAG').replace('#', '')
    url = f'https://proxy.royaleapi.dev/v1/players/%23{tag}/battlelog'
    headers = {'Authorization': f'Bearer {token}'}
    
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"Erro na API: {r.status_code}")
        return

    battles = r.json()
    if not battles:
        print("Nenhuma batalha encontrada.")
        return

    last_battle = battles[0]
    opponent = last_battle['opponent'][0]
    
    print("=== DADOS DA ULTIMA BATALHA (BRUTO) ===")
    print(f"Oponente: {opponent.get('name')}")
    print(f"Tag Oponente: {opponent.get('tag')}")
    print(f"Clã Oponente: {opponent.get('clan', {}).get('name', 'SEM CLÃ')}")
    print(f"Hora (UTC): {last_battle.get('battleTime')}")
    print(f"Tipo: {last_battle.get('type')}")
    print(f"Modo: {last_battle.get('gameMode', {}).get('name')}")

if __name__ == "__main__":
    check_last_battle()
