import os
import requests
import csv
import sys
from datetime import datetime
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

def get_war_decks(player_tag):
    headers, base_url, _ = get_config()
    player_tag_url = player_tag.replace('#', '%23')
    # Aumentamos o limite para garantir que achamos os 4 decks mesmo se houver outras lutas no meio
    r = requests.get(f"{base_url}/players/{player_tag_url}/battlelog", headers=headers)
    
    decks = []
    if r.status_code == 200:
        battles = r.json()
        for b in battles:
            if b.get('type') in ['clanWarAttack', 'clanWarDuel', 'riverRacePvP']:
                # Coleta as cartas do time do jogador
                team = b.get('team', [{}])[0]
                cards = sorted([c.get('name') for c in team.get('cards', [])])
                deck_str = ", ".join(cards)
                if deck_str not in decks:
                    decks.append(deck_str)
            if len(decks) >= 4:
                break
    return decks

def collect_intelligence():
    headers, base_url, my_clan_tag = get_config()
    today = datetime.now().strftime('%Y_%m_%d')
    os.makedirs('src/data_clan', exist_ok=True)
    filename = f'src/data_clan/inteligencia_guerra_{today}.csv'

    print(f"🚀 Refinando Inteligência de Guerra (4 Decks + Status do Dia)...")

    r = requests.get(f"{base_url}/clans/{my_clan_tag}/currentriverrace", headers=headers)
    if r.status_code != 200:
        print("Erro ao acessar dados da corrida.")
        return

    all_clans = r.json().get('clans', [])
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        # Novas colunas para facilitar sua visão
        writer.writerow(['Ranking', 'Cla', 'Jogador', 'Lutou_Hoje', 'Ataques_Feitos', 'Fama_Hoje', 'Deck_1', 'Deck_2', 'Deck_3', 'Deck_4'])

        for clan_info in all_clans:
            clan_name = clan_info.get('name')
            clan_tag = clan_info.get('tag')
            clan_tag_url = clan_tag.replace('#', '%23')
            
            print(f"📡 Analisando Clã: {clan_name}...")
            
            r_clan = requests.get(f"{base_url}/clans/{clan_tag_url}/currentriverrace", headers=headers)
            if r_clan.status_code == 200:
                participants = r_clan.json().get('clan', {}).get('participants', [])
                top_5 = sorted(participants, key=lambda x: x.get('fame', 0), reverse=True)[:5]
                
                for i, p in enumerate(top_5):
                    decks_usados_hoje = p.get('decksUsedToday', 0)
                    lutou = "Sim" if decks_usados_hoje > 0 else "Nao"
                    
                    print(f"   👤 {i+1}º: {p.get('name')} (Lutou: {lutou} | Decks: {decks_usados_hoje}/4)")
                    
                    # Busca os 4 decks históricos/recentes dele
                    found_decks = get_war_decks(p.get('tag'))
                    
                    # Preenche com "Nao encontrado" se o jogador nao tiver lutado guerra recentemente
                    while len(found_decks) < 4:
                        found_decks.append("Deck nao encontrado no log recente")

                    writer.writerow([
                        i + 1,
                        clan_name,
                        p.get('name'),
                        lutou,
                        f"{decks_usados_hoje}/4",
                        p.get('fame'),
                        found_decks[0],
                        found_decks[1],
                        found_decks[2],
                        found_decks[3]
                    ])
            else:
                print(f"   Erro ao acessar participantes do clã {clan_name}")

    print(f"\n✅ SUCESSO: Arquivo de inteligência FINAL gerado: {filename}")

if __name__ == "__main__":
    collect_intelligence()
