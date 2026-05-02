import os
import requests
import json
import sys
from dotenv import load_dotenv

# Força UTF-8 no terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Carrega as chaves do .env
load_dotenv()

def get_config():
    token = os.getenv('CR_API_TOKEN')
    tag = os.getenv('CR_PLAYER_TAG').replace('#', '')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    return token, tag, headers, base_url

def format_table(title, data_dict):
    print(f"\n=== {title} ===")
    print(f"{'CAMPO':<25} | {'VALOR'}")
    print("-" * 50)
    for k, v in data_dict.items():
        print(f"{k:<25} | {v}")

def fetch_player():
    _, tag, headers, base_url = get_config()
    r = requests.get(f"{base_url}/players/%23{tag}", headers=headers)
    if r.status_code == 200:
        data = r.json()
        info = {
            "Nome": data.get('name'),
            "Nivel": data.get('expLevel'),
            "Trofeus": data.get('trophies'),
            "Melhor Pontuacao": data.get('bestTrophies'),
            "Vitorias": data.get('wins'),
            "Derrotas": data.get('losses'),
            "Total de Batalhas": data.get('battleCount'),
            "Vitorias Tres Coroas": data.get('threeCrownWins'),
            "Cartas Descobertas": f"{data.get('cardsFound')}/{len(data.get('cards', [])) + (len(data.get('cardsFound')) if isinstance(data.get('cardsFound'), list) else 0)}", # Simples estimativa
            "Doacoes Totais": data.get('totalDonations'),
            "Vitorias em Guerra": data.get('warDayWins'),
            "Cla": data.get('clan', {}).get('name', 'Sem Cla'),
            "Arena": data.get('arena', {}).get('name')
        }
        format_table("PERFIL DO JOGADOR", info)
    else:
        print(f"Erro ao buscar jogador: {r.status_code}")

def fetch_chests():
    _, tag, headers, base_url = get_config()
    r = requests.get(f"{base_url}/players/%23{tag}/upcomingchests", headers=headers)
    if r.status_code == 200:
        items = r.json().get('items', [])
        print("\n=== PROXIMOS BAUS ===")
        print(f"{'POSICAO':<10} | {'BAU'}")
        print("-" * 30)
        for i, item in enumerate(items[:10]):
            print(f"{i+1:<10} | {item.get('name')}")
    else:
        print(f"Erro ao buscar baus: {r.status_code}")

if __name__ == "__main__":
    fetch_player()
    fetch_chests()
