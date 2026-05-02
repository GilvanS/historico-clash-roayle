import os
import requests
import sys
from dotenv import load_dotenv

# Configuração de UTF-8 para o terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def get_config():
    token = os.getenv('CR_API_TOKEN')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    # Tag do clã do usuário (já sabemos que é #QCLPL9VQ)
    clan_tag = "%23QCLPL9VQ"
    return headers, base_url, clan_tag

def test_endpoint(name, path):
    headers, base_url, clan_tag = get_config()
    url = f"{base_url}{path.replace('{clanTag}', clan_tag)}"
    print(f"\n--- Testando: {name} ({path}) ---")
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            # Mostra as chaves de primeiro nível para saber o que ele traz
            if isinstance(data, dict):
                print(f"Campos retornados: {list(data.keys())}")
                if 'items' in data and len(data['items']) > 0:
                    print(f"Exemplo do primeiro item: {list(data['items'][0].keys())}")
            elif isinstance(data, list):
                print(f"Retorna uma lista. Exemplo do primeiro item: {list(data[0].keys()) if len(data)>0 else 'Vazia'}")
        else:
            print(f"Status: {r.status_code} - Talvez não haja dados no momento (ex: sem guerra ativa).")
    except Exception as e:
        print(f"Erro: {str(e)}")

endpoints = [
    ("War Log", "/clans/{clanTag}/warlog"),
    ("Search Clans", "/clans?name=Bruxo"),
    ("River Race Log", "/clans/{clanTag}/riverracelog"),
    ("Current War", "/clans/{clanTag}/currentwar"),
    ("Clan Info", "/clans/{clanTag}"),
    ("Members List", "/clans/{clanTag}/members"),
    ("Current River Race", "/clans/{clanTag}/currentriverrace")
]

for name, path in endpoints:
    test_endpoint(name, path)
