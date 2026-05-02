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
    tag = os.getenv('CR_PLAYER_TAG').replace('#', '')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    return token, tag, headers, base_url

def get_player_clan_tag():
    _, tag, headers, base_url = get_config()
    r = requests.get(f"{base_url}/players/%23{tag}", headers=headers)
    if r.status_code == 200:
        return r.json().get('clan', {}).get('tag')
    return None

def fetch_clan():
    clan_tag = get_player_clan_tag()
    if not clan_tag:
        print("Jogador sem cla no momento.")
        return

    _, _, headers, base_url = get_config()
    # Corrige a tag para URL
    clan_tag_url = clan_tag.replace('#', '%23')
    r = requests.get(f"{base_url}/clans/{clan_tag_url}", headers=headers)
    
    if r.status_code == 200:
        data = r.json()
        print(f"\n=== DETALHES DO CLA: {data.get('name')} ===")
        print(f"{'CAMPO':<25} | {'VALOR'}")
        print("-" * 50)
        info = {
            "Tag": data.get('tag'),
            "Tipo": data.get('type'),
            "Descricao": data.get('description', 'N/A')[:30] + "...",
            "Trofeus do Cla": data.get('clanScore'),
            "Trofeus de Guerra": data.get('clanWarTrophies'),
            "Membros": f"{data.get('members')}/50",
            "Doacoes Semanais": data.get('donationsPerWeek'),
            "Trofeus Requeridos": data.get('requiredTrophies'),
            "Localizacao": data.get('location', {}).get('name')
        }
        for k, v in info.items():
            print(f"{k:<25} | {v}")

        # Listagem de Membros (Top 10)
        members = data.get('memberList', [])
        print(f"\n=== TOP 10 MEMBROS (POR TROFEUS) ===")
        print(f"{'RANK':<5} | {'NOME':<20} | {'TROFEUS':<10} | {'CARGO'}")
        print("-" * 55)
        for i, m in enumerate(members[:10]):
            print(f"{i+1:<5} | {m.get('name'):<20} | {m.get('trophies'):<10} | {m.get('role')}")
    else:
        print(f"Erro ao buscar cla: {r.status_code}")

if __name__ == "__main__":
    fetch_clan()
