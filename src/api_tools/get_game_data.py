import os
import requests
import sys
from dotenv import load_dotenv

# Força UTF-8 no terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def get_config():
    token = os.getenv('CR_API_TOKEN')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    return headers, base_url

def fetch_cards():
    headers, base_url = get_config()
    r = requests.get(f"{base_url}/cards", headers=headers)
    if r.status_code == 200:
        items = r.json().get('items', [])
        print(f"\n=== CATALOGO DE CARTAS ===")
        print(f"Total de cartas no jogo: {len(items)}")
        print(f"{'ID':<10} | {'NOME CARTAS'}")
        print("-" * 30)
        # Mostra as primeiras 10 cartas como exemplo
        for card in items[:10]:
            print(f"{card.get('id'):<10} | {card.get('name')}")
    else:
        print(f"Erro ao buscar cartas: {r.status_code}")

def fetch_locations():
    headers, base_url = get_config()
    r = requests.get(f"{base_url}/locations", headers=headers)
    if r.status_code == 200:
        items = r.json().get('items', [])
        print(f"\n=== LOCALIZACOES (TOP 10) ===")
        print(f"{'ID':<10} | {'NOME':<20} | {'E PAIS?'}")
        print("-" * 45)
        for loc in items[:10]:
            print(f"{loc.get('id'):<10} | {loc.get('name'):<20} | {loc.get('isCountry')}")
    else:
        print(f"Erro ao buscar localizacoes: {r.status_code}")

def fetch_global_tournaments():
    headers, base_url = get_config()
    r = requests.get(f"{base_url}/globaltournaments", headers=headers)
    if r.status_code == 200:
        items = r.json().get('items', [])
        print(f"\n=== TORNEIOS GLOBAIS ATIVOS ===")
        if not items:
            print("Nenhum torneio global ativo no momento.")
        for tour in items:
            print(f"Torneio: {tour.get('name')}")
            print(f"Status: {tour.get('state')}")
            print("-" * 30)
    else:
        print(f"Erro ao buscar torneios: {r.status_code}")

if __name__ == "__main__":
    fetch_cards()
    fetch_locations()
    fetch_global_tournaments()
