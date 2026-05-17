#!/usr/bin/env python3
"""
Coleta Inteligência Completa da Guerra de Rio (River Race)
- Top 5 clãs da corrida
- Top 5 jogadores de cada clã
- 4 decks com tipo de batalha (Guerra, Barco, RangeBattle, Duelo)
"""

import os
import sys
import requests
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Forçar UTF-8 no terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = 'src/data_clan'
os.makedirs(DATA_DIR, exist_ok=True)

# Tipos de batalha da Guerra de Rio
WAR_BATTLE_TYPES = ['clanWarWarDay', 'boatBattle', 'riverRacePvP', 'riverRaceDuel']
BATTLE_TYPE_LABELS = {
    'clanWarWarDay': 'Guerra',
    'boatBattle': 'Barco',
    'riverRacePvP': 'RangeBattle',
    'riverRaceDuel': 'Duelo'
}

def format_deck(cards):
    if not cards: return ""
    return ", ".join(c.get('name', '') for c in cards)

def get_clan_tag(token):
    player_tag = os.getenv('CR_PLAYER_TAG', '#2QR292P').replace('#', '%23')
    r = requests.get(f"https://proxy.royaleapi.dev/v1/players/{player_tag}", headers={'Authorization': f'Bearer {token}'})
    if r.status_code == 200:
        return r.json().get('clan', {}).get('tag')
    return None

def collect_river_race_intelligence():
    # Carregar dotenv do projeto raiz
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    load_dotenv(dotenv_path)
    
    token = os.getenv('CR_API_TOKEN')
    if not token:
        print("ERRO: CR_API_TOKEN não encontrado")
        return

    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"

    # Pegar tag do clan principal
    my_clan_tag = get_clan_tag(token)
    if not my_clan_tag:
        print("ERRO: Não foi possível obter a tag do clan")
        return

    print("=" * 60)
    print("COLETANDO INTELIGENCIA DE GUERRA - RIVER RACE")
    print("=" * 60)
    print(f"Clan Tag: {my_clan_tag}")

    # Buscar dados da corrida atual
    clan_url = my_clan_tag.replace('#', '%23')
    r = requests.get(f"{base_url}/clans/{clan_url}/currentriverrace", headers=headers)
    if r.status_code != 200:
        print(f"ERRO ao buscar corrida: {r.status_code}")
        return

    data = r.json()
    clans = data.get('clans', [])

    if not clans:
        print("Nenhum clan encontrado na corrida")
        return

    # Ordenar clans por fame (maior primero)
    sorted_clans = sorted(clans, key=lambda x: x.get('fame', 0), reverse=True)
    print(f"\nClans na corrida: {len(sorted_clans)}")

    # Data da coleta
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%d')
    results = []

    # Para cada clan (top 5 clãs)
    for clan_idx, clan in enumerate(sorted_clans[:5], 1):
        clan_name = clan.get('name', 'Unknown')
        clan_tag = clan.get('tag', '')
        clan_fame = clan.get('fame', 0)
        print(f"\n[Clan {clan_idx}] {clan_name} - Fama: {clan_fame}")

        participants = clan.get('participants', [])
        sorted_players = sorted(participants, key=lambda x: x.get('fame', 0), reverse=True)
        top_players = sorted_players[:5]
        print(f"  Top 5 jogadores encontrados")

        for player_idx, player in enumerate(top_players, 1):
            player_tag = player.get('tag', '')
            player_name = player.get('name', 'Unknown')
            player_fame = player.get('fame', 0)
            decks_used = player.get('decksUsed', 0)
            boat_attacks = player.get('boatAttacks', 0)

            print(f"    [{player_idx}] {player_name} - Fama: {player_fame}, Decks: {decks_used}")

            player_decks = {'deck_1': '', 'deck_2': '', 'deck_3': '', 'deck_4': '',
                           'deck_1_tipo': '', 'deck_2_tipo': '', 'deck_3_tipo': '', 'deck_4_tipo': ''}

            if player_tag:
                try:
                    p_tag_url = player_tag.replace('#', '%23')
                    br = requests.get(f"{base_url}/players/{p_tag_url}/battlelog", headers=headers, timeout=10)

                    if br.status_code == 200:
                        battles = br.json()
                        decks_collected = []
                        deck_types = []

                        for b in battles:
                            battle_type = b.get('type', '')
                            if battle_type in WAR_BATTLE_TYPES:
                                team = b.get('team', [{}])[0]
                                cards = team.get('cards', [])
                                deck_str = format_deck(cards)

                                if deck_str and deck_str not in decks_collected:
                                    decks_collected.append(deck_str)
                                    deck_types.append(BATTLE_TYPE_LABELS.get(battle_type, battle_type))

                                if len(decks_collected) >= 4:
                                    break

                        for i, deck in enumerate(decks_collected, 1):
                            player_decks[f'deck_{i}'] = deck
                            player_decks[f'deck_{i}_tipo'] = deck_types[i-1] if i <= len(deck_types) else ''

                except Exception as e:
                    print(f"      Erro: {e}")

            results.append({
                'data_coleta': data_hoje,
                'clan_posicao': clan_idx,
                'clan_nome': clan_name,
                'clan_tag': clan_tag,
                'clan_fame': clan_fame,
                'player_posicao': player_idx,
                'player_nome': player_name,
                'player_tag': player_tag,
                'player_fame': player_fame,
                'decks_usados': decks_used,
                'boat_attacks': boat_attacks,
                **player_decks
            })

    # Salvar CSV
    filename = f"{DATA_DIR}/inteligencia_guerra_full_{data_hoje}.csv"
    fieldnames = [
        'data_coleta', 'clan_posicao', 'clan_nome', 'clan_tag', 'clan_fame',
        'player_posicao', 'player_nome', 'player_tag', 'player_fame', 'decks_usados', 'boat_attacks',
        'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo'
    ]

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(results)

    print(f"\n\nSUCESSO! CSV gerado: {filename}")
    print(f"Total de registros: {len(results)}")

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO - TOP 5 CLANS DA CORRIDA")
    print("=" * 60)

    clans_in_results = {}
    for r in results:
        cn = r['clan_nome']
        if cn not in clans_in_results:
            clans_in_results[cn] = {'posicao': r['clan_posicao'], 'fame': r['clan_fame'], 'players': 0}
        clans_in_results[cn]['players'] += 1

    for cn, info in sorted(clans_in_results.items(), key=lambda x: x[1]['posicao']):
        print(f"#{info['posicao']} {cn} - {info['fame']} fame - {info['players']} players no top")

if __name__ == "__main__":
    collect_river_race_intelligence()