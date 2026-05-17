import os, requests, json
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('CR_API_TOKEN')
headers = {'Authorization': f'Bearer {token}'}
base_url = 'https://proxy.royaleapi.dev/v1'
clan_tag = '%23QCLPL9VQ'

# Testar currentriverrace
print('=== /clans/{tag}/currentriverrace ===')
r = requests.get(f'{base_url}/clans/{clan_tag}/currentriverrace', headers=headers)
if r.status_code == 200:
    data = r.json()
    print(f'Campos principais: {list(data.keys())}')
    print(f'State: {data.get("state")}')
    print(f'Clans count: {len(data.get("clans", []))}')
    
    # Verificar estrutura de um clã
    if data.get('clans'):
        c = data['clans'][0]
        print(f'\nEstrutura do clan: {list(c.keys())}')
        print(f'  name: {c.get("name")}')
        print(f'  fame: {c.get("fame")}')
        print(f'  periodPoints: {c.get("periodPoints")}')
        
    # Verificar participants do meu clan
    if 'clan' in data:
        p = data['clan'].get('participants', [])
        print(f'\nParticipantes do meu clan: {len(p)}')
        if p:
            player = p[0]
            print(f'Campos do player: {list(player.keys())}')
            print(f'  name: {player.get("name")}')
            print(f'  fame: {player.get("fame")}')
            print(f'  decksUsed: {player.get("decksUsed")}')
            print(f'  cardsEarned: {player.get("cardsEarned")}')
            print(f'  decks: {player.get("decks")}')

# Testar riverracelog
print('\n\n=== /clans/{tag}/riverracelog ===')
r2 = requests.get(f'{base_url}/clans/{clan_tag}/riverracelog', headers=headers)
if r2.status_code == 200:
    data2 = r2.json()
    print(f'Campos: {list(data2.keys())}')
    if data2.get('items'):
        item = data2['items'][0]
        print(f'Estrutura do log: {list(item.keys())}')
        print(f'  seasonId: {item.get("seasonId")}')
        if item.get('standings'):
            s = item['standings'][0]
            print(f'  standing: {list(s.keys())}')

# Listar TODOS os campos retornados em currentriverrace
print('\n\n=== ESTRUTURA COMPLETA currentriverrace ===')
print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])