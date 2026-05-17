import os, requests, json
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('CR_API_TOKEN')
headers = {'Authorization': f'Bearer {token}'}
base_url = 'https://proxy.royaleapi.dev/v1'
clan_tag = '%23QCLPL9VQ'

# Testar riverracelog
r = requests.get(f'{base_url}/clans/{clan_tag}/riverracelog', headers=headers)
if r.status_code == 200:
    data = r.json()
    if data.get('items'):
        for i, item in enumerate(data['items'][:3]):
            with open(f'riverrace_item_{i}.json', 'w', encoding='utf-8') as f:
                json.dump(item, f, indent=2, ensure_ascii=False)
            print(f'Salvo riverrace_item_{i}.json')

# Mostrar players do currentriverrace com decks
r2 = requests.get(f'{base_url}/clans/{clan_tag}/currentriverrace', headers=headers)
if r2.status_code == 200:
    data2 = r2.json()
    my_clan = data2.get('clan', {})
    participants = my_clan.get('participants', [])
    
    # Mostrar players com decksUsed > 0
    players_with_decks = [p for p in participants if p.get('decksUsed', 0) > 0]
    print(f'\nPlayers com decks na guerra: {len(players_with_decks)}')
    
    with open('currentriverrace_players.json', 'w', encoding='utf-8') as f:
        json.dump(players_with_decks[:10], f, indent=2, ensure_ascii=False)
    print('Salvo currentriverrace_players.json')

print('Done!')