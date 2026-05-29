
import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_token = os.getenv("CR_API_TOKEN")
player_tag = os.getenv("CR_PLAYER_TAG", "#2QR292P").replace('#', '')

url = f"https://api.clashroyale.com/v1/players/%23{player_tag}"
headers = {"Authorization": f"Bearer {api_token}"}

try:
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    player_data = resp.json()
    clan = player_data.get('clan', {})
    print(f"Jogador: {player_data.get('name')} ({player_data.get('tag')})")
    print(f"Clan: {clan.get('name')} ({clan.get('tag')})")
except Exception as e:
    print(f"Erro: {e}")
