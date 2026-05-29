
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def verify():
    token = os.getenv('CR_API_TOKEN')
    player_tag = os.getenv('CR_PLAYER_TAG', '#2QR292P').replace('#', '%23')
    headers = {'Authorization': f'Bearer {token}'}
    
    url = f"https://proxy.royaleapi.dev/v1/players/{player_tag}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        print(f"NICKNAME_API: {data.get('name')}")
    else:
        print(f"ERRO_API: {r.status_code} - {r.text}")

if __name__ == "__main__":
    verify()
