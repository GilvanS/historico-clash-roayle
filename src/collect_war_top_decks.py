import os
import requests
import csv
import json
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Forcar UTF-8 no terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()


# Campos para o CSV de decks de guerra
WAR_FIELDNAMES = [
    'data_coleta', 'tag_jogador', 'nome_jogador', 'tag_cla', 'nome_cla', 
    'fama_atual', 'posicao_no_top', 'categoria_top', 'deck_1', 'deck_2', 'deck_3', 'deck_4',
    'resultado_dia', 'lutou_hoje'
]

DATA_DIR = 'src/data_csv_oficial'

def get_clan_tag():
    token = os.getenv('CR_API_TOKEN')
    player_tag = os.getenv('CR_PLAYER_TAG').replace('#', '%23')
    r = requests.get(f"https://proxy.royaleapi.dev/v1/players/{player_tag}", headers={'Authorization': f'Bearer {token}'})
    if r.status_code == 200:
        return r.json().get('clan', {}).get('tag')
    return None

def format_deck(cards):
    if not cards: return ""
    return " | ".join(sorted(c.get('name', '') for c in cards))

def collect_top_decks():
    token = os.getenv('CR_API_TOKEN')
    my_clan_tag = get_clan_tag()
    if not token or not my_clan_tag:
        print("Erro: Credenciais ou Clan Tag nao encontrados.")
        return

    print(f"Buscando dados da guerra para o cla {my_clan_tag}...")
    clan_url = my_clan_tag.replace('#', '%23')
    r = requests.get(f"https://proxy.royaleapi.dev/v1/clans/{clan_url}/currentriverrace", headers={'Authorization': f'Bearer {token}'})
    
    if r.status_code != 200:
        print(f"Erro ao buscar guerra: {r.status_code}")
        return

    race_data = r.json()
    all_participants = []
    my_clan_participants = []
    
    # Coletar participantes
    for clan in race_data.get('clans', []):
        c_tag = clan.get('tag')
        c_name = clan.get('name')
        for p in clan.get('participants', []):
            p['clanTag'] = c_tag
            p['clanName'] = c_name
            all_participants.append(p)
            if c_tag == my_clan_tag:
                my_clan_participants.append(p)

    # Ordenar por fama (descendente)
    all_participants.sort(key=lambda x: x.get('fame', 0), reverse=True)
    my_clan_participants.sort(key=lambda x: x.get('fame', 0), reverse=True)
    
    top_global = all_participants[:5]
    top_clan = my_clan_participants[:5]

    # Unir e remover duplicatas (usando a tag)
    players_to_fetch = []
    seen_tags = set()

    for p in top_clan:
        if p['tag'] not in seen_tags:
            p['categoria'] = 'Top Cla'
            players_to_fetch.append(p)
            seen_tags.add(p['tag'])
            
    for p in top_global:
        if p['tag'] not in seen_tags:
            p['categoria'] = 'Top Global'
            players_to_fetch.append(p)
            seen_tags.add(p['tag'])
        else:
            # Se ja esta no top cla, marcamos como ambos
            for ptf in players_to_fetch:
                if ptf['tag'] == p['tag']:
                    ptf['categoria'] = 'Top Cla/Global'

    print(f"Identificados {len(players_to_fetch)} jogadores de elite. Coletando decks (Guerra + Barco)...")
    
    results = []
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%d/%m/%Y')

    for i, p in enumerate(players_to_fetch, 1):
        p_tag = p.get('tag')
        p_name = p.get('name')
        print(f"  [{i}] {p_name} ({p_tag}) - Fama: {p.get('fame')} [{p['categoria']}]")
        
        # Buscar battle log do jogador
        p_tag_url = p_tag.replace('#', '%23')
        br = requests.get(f"https://proxy.royaleapi.dev/v1/players/{p_tag_url}/battlelog", headers={'Authorization': f'Bearer {token}'})
        
        decks = []
        wins = 0
        losses = 0
        lutou = "Nao"
        
        if br.status_code == 200:
            battles = br.json()
            for b in battles:
                # Inclui clanWarWarDay e boatBattle explicitamente
                if b.get('type') in ['clanWarWarDay', 'boatBattle']:
                    lutou = "Sim"
                    team = b.get('team', [{}])[0]
                    deck_str = format_deck(team.get('cards', []))
                    if deck_str and deck_str not in decks:
                        decks.append(deck_str)
                    
                    p_crowns = team.get('crowns', 0)
                    opp_crowns = b.get('opponent', [{}])[0].get('crowns', 0)
                    if p_crowns > opp_crowns: wins += 1
                    else: losses += 1
                    
                    if len(decks) >= 4: break

        while len(decks) < 4:
            decks.append("N/A")

        results.append({
            'data_coleta': data_hoje,
            'tag_jogador': p_tag,
            'nome_jogador': p_name,
            'tag_cla': p.get('clanTag'),
            'nome_cla': p.get('clanName'),
            'fama_atual': p.get('fame'),
            'posicao_no_top': i,
            'categoria_top': p['categoria'],
            'deck_1': decks[0],
            'deck_2': decks[1],
            'deck_3': decks[2],
            'deck_4': decks[3],
            'resultado_dia': f"{wins}V {losses}D" if lutou == "Sim" else "N/A",
            'lutou_hoje': lutou
        })


    # Salvar no CSV
    file_path = os.path.join(DATA_DIR, 'war_decks_top_players.csv')
    file_exists = os.path.exists(file_path)
    
    with open(file_path, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=WAR_FIELDNAMES, delimiter=';')
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)

    print(f"\nSucesso! Decks salvos em {file_path}")

if __name__ == "__main__":
    collect_top_decks()
