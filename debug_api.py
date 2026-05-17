import os, requests
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('CR_API_TOKEN')
player_tag = os.getenv('CR_PLAYER_TAG', '#2QR292P').replace('#', '%23')

print(f"Token: {token[:20]}...")
print(f"Player Tag URL: {player_tag}")

headers = {'Authorization': f'Bearer {token}'}
base_url = "https://proxy.royaleapi.dev/v1"

# Primeiro pega o clan tag do player
print("\n1. Buscando clan do player...")
r = requests.get(f"{base_url}/players/{player_tag}", headers=headers)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    clan_tag = data.get('clan', {}).get('tag', '')
    print(f"Clan Tag: {clan_tag}")

    if clan_tag:
        clan_url = clan_tag.replace('#', '%23')
        print(f"\n2. Buscando currentriverrace...")
        r2 = requests.get(f"{base_url}/clans/{clan_url}/currentriverrace", headers=headers)
        print(f"Status: {r2.status_code}")
        if r2.status_code == 200:
            d2 = r2.json()
            print(f"Clans na corrida: {len(d2.get('clans', []))}")
        else:
            print(f"Erro: {r2.text[:200]}")
else:
    print(f"Erro: {r.text[:200]}")