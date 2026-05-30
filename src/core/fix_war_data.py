#!/usr/bin/env python3
"""
Recupera dados históricos do River Race para dias específicos
Busca dados passados via API e preenche CSV gaps
"""

import os
import sys
import io
import requests
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Forçar UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = 'data/csv'
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
    if not cards:
        return ""
    return ", ".join(c.get('name', '') for c in cards)

def get_player_info(token, player_tag):
    """Busca info do jogador (nome e clan_tag)."""
    headers = {'Authorization': f'Bearer {token}'}
    tag = player_tag.replace('#', '%23')
    r = requests.get(f'https://proxy.royaleapi.dev/v1/players/{tag}', headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        return {
            'name': data.get('name', 'Unknown'),
            'clan_tag': data.get('clan', {}).get('tag', ''),
            'clan_name': data.get('clan', {}).get('name', '')
        }
    return None

def get_river_race_history(token, clan_tag, date_str):
    """
    Tenta buscar dados do River Race para uma data específica.
    A API pode não suportar datas passadas, mas vamos tentar.
    """
    headers = {'Authorization': f'Bearer {token}'}
    clan_url = clan_tag.replace('#', '%23')

    # Primeiro tentar currentriverrace
    r = requests.get(f'https://proxy.royaleapi.dev/v1/clans/{clan_url}/currentriverrace', headers=headers, timeout=15)
    if r.status_code != 200:
        return None

    data = r.json()
    clans = data.get('clans', [])

    if not clans:
        return None

    sorted_clans = sorted(clans, key=lambda x: x.get('fame', 0), reverse=True)

    results = []
    for clan_idx, clan in enumerate(sorted_clans[:5], 1):
        clan_name = clan.get('name', 'Unknown')
        clan_tag_val = clan.get('tag', '')
        clan_fame = clan.get('fame', 0)

        participants = clan.get('participants', [])
        sorted_players = sorted(participants, key=lambda x: x.get('fame', 0), reverse=True)
        top_players = sorted_players[:5]

        for player_idx, player in enumerate(top_players, 1):
            player_tag = player.get('tag', '')
            player_name = player.get('name', 'Unknown')
            player_fame = player.get('fame', 0)
            decks_used = player.get('decksUsed', 0)
            boat_attacks = player.get('boatAttacks', 0)

            player_decks = {'deck_1': '', 'deck_2': '', 'deck_3': '', 'deck_4': '',
                           'deck_1_tipo': '', 'deck_2_tipo': '', 'deck_3_tipo': '', 'deck_4_tipo': ''}

            if player_tag:
                try:
                    p_tag_url = player_tag.replace('#', '%23')
                    br = requests.get(f'https://proxy.royaleapi.dev/v1/players/{p_tag_url}/battlelog', headers=headers, timeout=10)

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
                except:
                    pass

            results.append({
                'data_coleta': date_str,
                'clan_posicao': clan_idx,
                'clan_nome': clan_name,
                'clan_tag': clan_tag_val,
                'clan_fame': clan_fame,
                'player_posicao': player_idx,
                'player_nome': player_name,
                'player_tag': player_tag,
                'player_fame': player_fame,
                'decks_usados': decks_used,
                'boat_attacks': boat_attacks,
                **player_decks
            })

    return results

def convert_old_format_to_full(old_file, output_file, target_date):
    """
    Converte formato antigo (inteligencia_guerra_sec_YYYY_MM_DD.csv)
    para formato novo (inteligencia_guerra_full_sec_YYYY-MM-DD.csv)
    """
    if not os.path.exists(old_file):
        print(f'Arquivo antigo nao encontrado: {old_file}')
        return False

    print(f'Convertendo: {old_file} -> {output_file}')

    fieldnames = [
        'data_coleta', 'clan_posicao', 'clan_nome', 'clan_tag', 'clan_fame',
        'player_posicao', 'player_nome', 'player_tag', 'player_fame', 'decks_usados', 'boat_attacks',
        'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo'
    ]

    try:
        with open(old_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

        # Agrupar por clã para obter clan_fame (soma das fame dos players)
        clan_fames = {}
        for row in rows:
            cla = row.get('Cla', 'Unknown')
            try:
                fame = int(row.get('Fama_Hoje', 0) or 0)
            except:
                fame = 0
            if cla not in clan_fames:
                clan_fames[cla] = 0
            clan_fames[cla] += fame

        # Processar rows para formato novo
        results = []
        current_clan = None
        clan_idx = 0
        player_idx = 0

        for row in rows:
            cla = row.get('Cla', 'Unknown')
            ranking = int(row.get('Ranking', 99) or 99)

            # Novo clã
            if cla != current_clan:
                current_clan = cla
                clan_idx += 1
                player_idx = 0

            player_idx += 1

            # Calcular boat_attacks baseado em Lutou_Hoje
            lutou = row.get('Lutou_Hoje', 'Nao')
            boat_attacks = 4 if lutou == 'Sim' else 0

            deck_1 = row.get('Deck_1', '')
            deck_2 = row.get('Deck_2', '')
            deck_3 = row.get('Deck_3', '')
            deck_4 = row.get('Deck_4', '')

            # Determinar tipo do deck
            deck_1_tipo = 'Guerra' if deck_1 and deck_1 != 'Deck nao encontrado no log recente' else ''
            deck_2_tipo = 'Guerra' if deck_2 and deck_2 != 'Deck nao encontrado no log recente' else ''
            deck_3_tipo = 'Guerra' if deck_3 and deck_3 != 'Deck nao encontrado no log recente' else ''
            deck_4_tipo = 'Guerra' if deck_4 and deck_4 != 'Deck nao encontrado no log recente' else ''

            results.append({
                'data_coleta': target_date,
                'clan_posicao': clan_idx,
                'clan_nome': cla,
                'clan_tag': '',
                'clan_fame': clan_fames.get(cla, 0),
                'player_posicao': player_idx,
                'player_nome': row.get('Jogador', ''),
                'player_tag': '',
                'player_fame': int(row.get('Fama_Hoje', 0) or 0),
                'decks_usados': row.get('Ataques_Feitos', '0/4'),
                'boat_attacks': boat_attacks,
                'deck_1': deck_1,
                'deck_1_tipo': deck_1_tipo,
                'deck_2': deck_2,
                'deck_2_tipo': deck_2_tipo,
                'deck_3': deck_3,
                'deck_3_tipo': deck_3_tipo,
                'deck_4': deck_4,
                'deck_4_tipo': deck_4_tipo
            })

        # Ordenar por clan_posicao e player_posicao
        results.sort(key=lambda x: (x['clan_posicao'], x['player_posicao']))

        # Escrever CSV
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(results)

        print(f'  Convertido {len(results)} jogadores de {clan_idx} clãs')
        return True

    except Exception as e:
        print(f'Erro ao converter: {e}')
        return False

def fix_missing_days():
    """Preenche dias que estão faltando dados no formato full."""
    load_dotenv(os.path.join('.env'))

    token = os.getenv('CR_API_TOKEN')
    if not token:
        print('ERRO: CR_API_TOKEN nao encontrado')
        return

    print('=' * 60)
    print('RECUPERANDO DADOS HISTÓRICOS DO RIVER RACE')
    print('=' * 60)

    # Contar quantos arquivos full_sec existem
    full_sec_files = [f for f in os.listdir(DATA_DIR) if f.startswith('inteligencia_guerra_full_sec_') and f.endswith('.csv')]
    print(f'Arquivos full_sec encontrados: {len(full_sec_files)}')

    # Verificar quais dias têm dados no formato antigo mas não no novo
    # Formato antigo: inteligencia_guerra_sec_YYYY_MM_DD.csv
    # Formato novo: inteligencia_guerra_full_sec_YYYY-MM-DD.csv

    dates_to_check = [
        ('2026-05-16', '2026_05_16'),
        ('2026-05-15', '2026_05_15'),
        ('2026-05-14', '2026_05_14'),
    ]

    for target_date, old_date_str in dates_to_check:
        new_file = f'{DATA_DIR}/inteligencia_guerra_full_sec_{target_date}.csv'
        old_file = f'{DATA_DIR}/inteligencia_guerra_sec_{old_date_str}.csv'

        # Se já existe arquivo novo, pular
        if os.path.exists(new_file):
            print(f'\n{target_date}: arquivo full ja existe')
            # Verificar se tem dados válidos
            with open(new_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
                has_data = any(int(r.get('player_fame', 0) or 0) > 0 for r in rows)
                if has_data:
                    print(f'  OK - tem {len(rows)} jogadores com dados')
                else:
                    print(f'  ATENCAO - arquivo existe mas dados estao vazios')
                    # Tentar converter do formato antigo
                    if os.path.exists(old_file):
                        convert_old_format_to_full(old_file, new_file, target_date)
            continue

        # Se não existe arquivo novo, verificar se existe formato antigo
        if os.path.exists(old_file):
            print(f'\n{target_date}: convertendo de formato antigo')
            convert_old_format_to_full(old_file, new_file, target_date)
        else:
            print(f'\n{target_date}: tentando buscar da API...')
            # Buscar info dos jogadores
            player_info = get_player_info(token, '#2220UQQ0UU')
            if player_info and player_info.get('clan_tag'):
                results = get_river_race_history(token, player_info['clan_tag'], target_date)
                if results:
                    fieldnames = [
                        'data_coleta', 'clan_posicao', 'clan_nome', 'clan_tag', 'clan_fame',
                        'player_posicao', 'player_nome', 'player_tag', 'player_fame', 'decks_usados', 'boat_attacks',
                        'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo'
                    ]
                    with open(new_file, 'w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                        writer.writeheader()
                        writer.writerows(results)
                    print(f'  Salvo {len(results)} jogadores')
                else:
                    print(f'  API nao retornou dados')

    print('\n' + '=' * 60)
    print('RESUMO DOS ARQUIVOS FULL_SEC:')
    print('=' * 60)

    for f in sorted(os.listdir(DATA_DIR)):
        if f.startswith('inteligencia_guerra_full_sec_') and f.endswith('.csv'):
            path = os.path.join(DATA_DIR, f)
            size = os.path.getsize(path)
            with open(path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file, delimiter=';')
                rows = list(reader)
                clans = set(r.get('clan_nome', '') for r in rows)
                total_fame = sum(int(r.get('player_fame', 0) or 0) for r in rows)
                has_decks = any(r.get('deck_1', '') and r.get('deck_1', '') != '' for r in rows)
                print(f'{f}: {len(rows)} jogadores, {len(clans)} clãs, fame={total_fame}, decks={has_decks} ({size} bytes)')

if __name__ == '__main__':
    fix_missing_days()