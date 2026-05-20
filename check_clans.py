import requests, json, sys, os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('CR_API_TOKEN')
headers = {'Authorization': f'Bearer {token}'}

tags = ['#2QR292P', '#2220UQQ0UU']
for tag in tags:
    try:
        clean = tag.replace('#', '%23')
        url = f'https://proxy.royaleapi.dev/v1/players/{clean}'
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            clan = data.get('clan', {})
            clan_tag = clan.get('tag')
            clan_name = clan.get('name', 'Unknown')
            # Encode to ASCII-safe
            print(f'{tag}: clan={clan_tag}', flush=True)
            sys.stdout.flush()
        else:
            print(f'{tag}: erro {r.status_code}', flush=True)
    except Exception as e:
        print(f'{tag}: exception {e}', flush=True)