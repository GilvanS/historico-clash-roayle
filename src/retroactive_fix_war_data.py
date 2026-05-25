#!/usr/bin/env python3
"""
Correcao Retroativa de Dados de Guerra (River Race)
Reanalisa o battlelog da API para cada jogador no historico da semana atual (21/05 a 24/05)
e reconstrói as estatísticas com o filtro temporal logico correto de fuso UTC-3.
"""

import os
import sys
import requests
import csv
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Forcar UTF-8 no terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data_clan')
os.makedirs(DATA_DIR, exist_ok=True)

WAR_BATTLE_TYPES = ['clanWarWarDay', 'boatBattle', 'riverRacePvP', 'riverRaceDuel']
BATTLE_TYPE_LABELS = {
    'clanWarWarDay': 'Guerra',
    'boatBattle': 'Barco',
    'riverRacePvP': 'RangeBattle',
    'riverRaceDuel': 'Duelo'
}

FAME_POR_VITORIA = 200
FAME_POR_DERROTA_COROA = 100
FAME_POR_DERROTA = 100

def format_deck(cards):
    if not cards: return ""
    return ", ".join(c.get('name', '') for c in cards)

def is_battle_on_logical_date(battle_time_str, target_date):
    if not battle_time_str:
        return False
    try:
        match = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", battle_time_str)
        if not match:
            return False
            
        year, month, day, hour, minute, second = map(int, match.groups())
        dt_utc = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        dt_local = dt_utc - timedelta(hours=3) # Fuso Brasil (UTC-3)
        
        if dt_local.hour < 7:
            logical_date = dt_local - timedelta(days=1)
        else:
            logical_date = dt_local
            
        return logical_date.strftime('%Y-%m-%d') == target_date
    except:
        return False

def collect_war_battles_stats(battles, target_date):
    stats = {
        'war_vitorias': 0,
        'war_derrotas': 0,
        'war_medals': 0,
        'war_torre': 'Tower Princess',
        'war_tipo_principal': '',
        'war_battles_count': 0
    }
    
    if not battles:
        return stats
    
    war_battles = []
    for b in battles:
        if b.get('type', '') not in WAR_BATTLE_TYPES:
            continue
        battle_time = b.get('battleTime', '')
        if not is_battle_on_logical_date(battle_time, target_date):
            continue
        war_battles.append(b)
        
    stats['war_battles_count'] = len(war_battles)
    
    if not war_battles:
        return stats
    
    tipo_counts = {}
    for b in war_battles:
        is_victory = False
        team = b.get('team', [])
        opponent = b.get('opponent', [])
        
        if team and opponent:
            team_crowns = team[0].get('crowns', 0)
            opp_crowns = opponent[0].get('crowns', 0) if opponent else 0
            is_victory = team_crowns > opp_crowns
        
        if is_victory:
            stats['war_vitorias'] += 1
        else:
            stats['war_derrotas'] += 1
        
        coroas = team[0].get('crowns', 0) if team else 0
        if is_victory:
            stats['war_medals'] += FAME_POR_VITORIA
        elif coroas > 0:
            stats['war_medals'] += FAME_POR_DERROTA_COROA
        else:
            stats['war_medals'] += FAME_POR_DERROTA
        
        if stats['war_torre'] == 'Tower Princess':
            tower = b.get('team', [{}])[0].get('kingTower', {}).get('name', 'Tower Princess')
            if tower and tower != 'King Tower':
                stats['war_torre'] = tower
        
        battle_type = b.get('type', '')
        tipo_label = BATTLE_TYPE_LABELS.get(battle_type, battle_type)
        tipo_counts[tipo_label] = tipo_counts.get(tipo_label, 0) + 1
    
    if tipo_counts:
        stats['war_tipo_principal'] = max(tipo_counts, key=tipo_counts.get)
    
    return stats

def collect_decks_from_battlelog(battles, target_date):
    decks_collected = []
    deck_types = []

    filtered_battles = []
    for b in battles:
        if b.get('type', '') not in WAR_BATTLE_TYPES:
            continue
        battle_time = b.get('battleTime', '')
        if not is_battle_on_logical_date(battle_time, target_date):
            continue
        filtered_battles.append(b)

    for b in filtered_battles:
        battle_type = b.get('type', '')
        tipo_label = BATTLE_TYPE_LABELS.get(battle_type, battle_type)
        team = b.get('team', [{}])[0]
        cards = team.get('cards', [])

        if len(cards) > 8:
            for idx in range(0, len(cards), 8):
                sub_cards = cards[idx:idx+8]
                deck_str = format_deck(sub_cards)
                if deck_str and deck_str not in decks_collected:
                    decks_collected.append(deck_str)
                    deck_types.append(tipo_label)
        else:
            deck_str = format_deck(cards)
            if deck_str and deck_str not in decks_collected:
                decks_collected.append(deck_str)
                deck_types.append(tipo_label)

        if len(decks_collected) >= 4:
            break

    for b in filtered_battles:
        if len(decks_collected) >= 4:
            break
        battle_type = b.get('type', '')
        if battle_type != 'riverRaceDuel':
            continue
        tipo_label = BATTLE_TYPE_LABELS.get(battle_type, battle_type)
        for rnd in b.get('rounds', []):
            if len(decks_collected) >= 4:
                break
            team_round = rnd.get('team', [{}])[0] if isinstance(rnd.get('team'), list) else {}
            cards_round = team_round.get('cards', [])
            deck_str = format_deck(cards_round)
            if deck_str and deck_str not in decks_collected:
                decks_collected.append(deck_str)
                deck_types.append(tipo_label)

    player_decks = {
        'deck_1': '', 'deck_2': '', 'deck_3': '', 'deck_4': '',
        'deck_1_tipo': '', 'deck_2_tipo': '', 'deck_3_tipo': '', 'deck_4_tipo': ''
    }
    for i, deck in enumerate(decks_collected[:4], 1):
        player_decks[f'deck_{i}'] = deck
        player_decks[f'deck_{i}_tipo'] = deck_types[i-1] if i <= len(deck_types) else ''

    return player_decks

def retroactive_fix():
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    load_dotenv(dotenv_path)
    
    token = os.getenv('CR_API_TOKEN')
    if not token:
        print("ERRO: CR_API_TOKEN nao encontrado")
        return
        
    guerra_hist_path = f"{DATA_DIR}/guerra_historico.csv"
    if not os.path.exists(guerra_hist_path):
        print("ERRO: guerra_historico.csv nao encontrado!")
        return
        
    print("=" * 60)
    # Comentario em pt-BR sem acento
    print("INICIANDO RETROACTIVE FIX - SEMANA DE 21/05 A 24/05")
    print("=" * 60)
    
    # Carregar registros existentes
    existing_records = []
    with open(guerra_hist_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            existing_records.append(row)
            
    # Identificar tags de jogadores unicas que constam no historico do clã principal e secundario nesta semana
    target_dates = ['2026-05-21', '2026-05-22', '2026-05-23', '2026-05-24']
    
    # Coletar todas as tags do proprio cla e adversarios da conta principal e secundaria
    tags_to_process = set()
    for r in existing_records:
        if r['data_coleta'] in target_dates and r.get('player_tag'):
            tags_to_process.add(r['player_tag'])
            
    print(f"Total de {len(tags_to_process)} jogadores unicos identificados para processar")
    
    # Buscar battlelog de cada jogador na API e manter em cache
    headers = {'Authorization': f'Bearer {token}'}
    player_battlelogs = {}
    
    processed_count = 0
    for tag in tags_to_process:
        processed_count += 1
        clean_tag = tag.replace('#', '%23')
        print(f"[{processed_count}/{len(tags_to_process)}] Buscando battlelog de {tag}...")
        try:
            url = f"https://proxy.royaleapi.dev/v1/players/{clean_tag}/battlelog"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                player_battlelogs[tag] = r.json()
            else:
                print(f"  Aviso: API falhou para {tag} com codigo {r.status_code}")
                player_battlelogs[tag] = []
        except Exception as e:
            print(f"  Aviso: Erro de conexao para {tag}: {e}")
            player_battlelogs[tag] = []
            
    # Atualizar os registros de guerra retroativamente
    updated_records = []
    fixed_count = 0
    
    for r in existing_records:
        date = r['data_coleta']
        tag = r.get('player_tag', '')
        
        # Só processar se estiver nas datas alvo e tivermos o battlelog
        if date in target_dates and tag in player_battlelogs:
            battles = player_battlelogs[tag]
            
            # Recalcular stats e decks baseados no battlelog real para a data logica especifica!
            new_war_stats = collect_war_battles_stats(battles, date)
            new_player_decks = collect_decks_from_battlelog(battles, date)
            
            # Se mudou as estatisticas do jogador
            orig_battles = int(r.get('war_battles_count', '0') or 0)
            new_battles = new_war_stats['war_battles_count']
            
            # Atualizar os dados no registro
            r.update(new_war_stats)
            r.update(new_player_decks)
            
            # Se a API retornou fame=0 mas o jogador nao duelou na data logica, manter zerado.
            # Se o jogador nao jogou nada no dia, garantir que o decks_usados e boat_attacks batam com o real.
            if new_battles == 0:
                r['decks_usados'] = '0'
                r['boat_attacks'] = '0'
                
            if orig_battles != new_battles:
                fixed_count += 1
                
        updated_records.append(r)
        
    # Salvar o arquivo corrigido
    fieldnames = [
        'data_coleta', 'dia_batalha', 'conta_tipo', 'player_tag', 'player_nome', 
        'player_fame', 'player_posicao', 'clan_tag', 'clan_nome', 'clan_posicao', 
        'clan_fame', 'decks_usados', 'boat_attacks', 
        'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 
        'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo',
        'war_vitorias', 'war_derrotas', 'war_medals', 'war_torre', 'war_battles_count'
    ]
    
    try:
        with open(guerra_hist_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(updated_records)
        print(f"\nSUCESSO: guerra_historico.csv corrigido retroativamente!")
        print(f"Total de registros corrigidos/limpos de duplicacoes: {fixed_count}")
    except Exception as e:
        print(f"ERRO ao gravar guerra_historico.csv corrigido: {e}")

if __name__ == '__main__':
    retroactive_fix()
