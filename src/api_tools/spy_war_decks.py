import os
import requests
import sys
from dotenv import load_dotenv

load_dotenv()

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_config():
    token = os.getenv('CR_API_TOKEN')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    my_clan_tag = "%23QCLPL9VQ"
    return headers, base_url, my_clan_tag

def get_top_player_from_clan(clan_tag):
    headers, base_url, _ = get_config()
    # Corrige a tag para URL
    clan_tag_url = clan_tag.replace('#', '%23')
    r = requests.get(f"{base_url}/clans/{clan_tag_url}/currentriverrace", headers=headers)
    
    if r.status_code == 200:
        clan_data = r.json().get('clan', {})
        participants = clan_data.get('participants', [])
        if not participants:
            return None
        # Encontra o jogador com maior fama
        top_player = max(participants, key=lambda x: x.get('fame', 0))
        return {
            "name": top_player.get('name'),
            "tag": top_player.get('tag'),
            "fame": top_player.get('fame'),
            "clan": clan_data.get('name')
        }
    return None

def get_war_decks(player_tag):
    headers, base_url, _ = get_config()
    player_tag_url = player_tag.replace('#', '%23')
    r = requests.get(f"{base_url}/players/{player_tag_url}/battlelog", headers=headers)
    
    decks = []
    if r.status_code == 200:
        battles = r.json()
        for b in battles:
            # Filtra apenas batalhas de guerra (Clan War)
            if b.get('type') in ['clanWarAttack', 'clanWarDuel', 'riverRacePvP']:
                cards = [c.get('name') for c in b.get('team', [{}])[0].get('cards', [])]
                if cards not in decks:
                    decks.append(cards)
            if len(decks) >= 4: # Para quando achar os 4 decks da guerra
                break
    return decks

def run_spy():
    headers, base_url, my_clan_tag = get_config()
    
    print("🔍 Iniciando Espionagem de Guerra...")
    
    # 1. Pega os rivais
    r = requests.get(f"{base_url}/clans/{my_clan_tag}/currentriverrace", headers=headers)
    if r.status_code != 200:
        print("Erro ao acessar dados da corrida.")
        return

    all_clans = r.json().get('clans', [])
    
    for clan_info in all_clans:
        clan_name = clan_info.get('name')
        clan_tag = clan_info.get('tag')
        
        print(f"\n📡 Analisando Clã: {clan_name} ({clan_tag})")
        top_p = get_top_player_from_clan(clan_tag)
        
        if top_p:
            print(f"🏆 Melhor Jogador: {top_p['name']} (Fama: {top_p['fame']})")
            print(f"🎴 Buscando Decks de Guerra...")
            decks = get_war_decks(top_p['tag'])
            
            if not decks:
                print("   Nenhum deck de guerra encontrado no log recente.")
            for i, deck in enumerate(decks):
                print(f"   Deck {i+1}: {', '.join(deck)}")
        else:
            print("   Não foi possível encontrar participantes ativos.")

if __name__ == "__main__":
    run_spy()
