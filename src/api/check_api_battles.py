import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

api_token = os.environ.get('CR_API_TOKEN')
player_tag = os.environ.get('CR_PLAYER_TAG').replace('#', '')

url = f"https://proxy.royaleapi.dev/v1/players/%23{player_tag}/battlelog"
headers = {"Authorization": f"Bearer {api_token}"}

response = requests.get(url, headers=headers)
battles = response.json()

print(f"Total de batalhas na API: {len(battles)}")
for b in battles[:10]:
    bt = b.get('battleTime')
    # 20260429T230000.000Z
    dt_utc = datetime.strptime(bt[:15], '%Y%m%dT%H%M%S')
    dt_brt = dt_utc - timedelta(hours=3)
    print(f"Time UTC: {bt} -> BRT: {dt_brt}")
