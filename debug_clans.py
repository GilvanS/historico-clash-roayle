import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('CR_API_TOKEN')
headers = {'Authorization': f'Bearer {token}'}
base_url = "https://proxy.royaleapi.dev/v1"

clan_tag = "#P2P2Y880"
clan_url = clan_tag.replace('#', '%23')

# 1. Informações Básicas do Clã
print("--- TESTE CLAN INFO ---")
r_clan = requests.get(f"{base_url}/clans/{clan_url}", headers=headers)
print("Status Code Clan Info:", r_clan.status_code)
if r_clan.status_code == 200:
    clan_data = r_clan.json()
    print("Nome:", clan_data.get('name'))
    print("Membros:", clan_data.get('members'))
    print("Trophies:", clan_data.get('clanWarTrophies'))
else:
    print("Erro ao obter info do clã:", r_clan.text)

# 2. Corrida de Rio Atual
print("\n--- TESTE CURRENT RIVER RACE ---")
r_race = requests.get(f"{base_url}/clans/{clan_url}/currentriverrace", headers=headers)
print("Status Code River Race:", r_race.status_code)
if r_race.status_code == 200:
    race_data = r_race.json()
    clans_in_race = race_data.get('clans', [])
    print(f"Quantidade de clãs na corrida: {len(clans_in_race)}")
    for c in clans_in_race:
        c_tag = c.get('tag')
        c_name = c.get('name')
        c_fame = c.get('fame')
        is_target = " (ALVO)" if c_tag == clan_tag else ""
        print(f"- Clã: {c_name} ({c_tag}) | Fame: {c_fame}{is_target}")
        
        if c_tag == clan_tag:
            participants = c.get('participants', [])
            print(f"  Total de participantes no clã: {len(participants)}")
            # Mostrar os 5 participantes com mais fama
            sorted_p = sorted(participants, key=lambda x: x.get('fame', 0), reverse=True)
            for idx, p in enumerate(sorted_p[:10], 1):
                print(f"    {idx}. {p.get('name')} ({p.get('tag')}) | Fame: {p.get('fame')} | Decks Used: {p.get('decksUsed')}")
else:
    print("Erro ao obter River Race:", r_race.text)
