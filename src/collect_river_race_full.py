#!/usr/bin/env python3
"""
Coleta Inteligência Completa da Guerra de Rio (River Race)
- Top 5 clãs da corrida
- Top 5 jogadores de cada clã
- 4 decks com tipo de batalha (Guerra, Barco, RangeBattle, Duelo)
- Estatísticas de batalhas de guerra (vitórias, derrotas, medals, torre)
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

def get_clan_tag(token, player_tag):
    """Obtém a tag do clã do jogador usando a API"""
    clean = player_tag.replace('#', '%23')
    r = requests.get(f"https://proxy.royaleapi.dev/v1/players/{clean}", headers={'Authorization': f'Bearer {token}'})
    if r.status_code == 200:
        return r.json().get('clan', {}).get('tag')
    return None

def collect_war_battles_stats(battles):
    """Coleta estatísticas de batalhas de guerra"""
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
    
    war_battles = [b for b in battles if b.get('type', '') in WAR_BATTLE_TYPES]
    stats['war_battles_count'] = len(war_battles)
    
    if not war_battles:
        return stats
    
    # Contar vitórias e derrotas
    tipo_counts = {}
    for b in war_battles:
        # Verificar se o jogador venceu (olhar team e opponent)
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
        
        # Contar medals (3 para vitória, 1 para derrota com coroas)
        coroas = team[0].get('crowns', 0) if team else 0
        if is_victory:
            stats['war_medals'] += 3  # Vitória = 3 medals
        elif coroas > 0:
            stats['war_medals'] += 1  # Derrota com coroa = 1 medal
        
        # Torre do jogador (primeira batalha)
        if stats['war_torre'] == 'Tower Princess':
            tower = b.get('team', [{}])[0].get('kingTower', {}).get('name', 'Tower Princess')
            if tower and tower != 'King Tower':
                stats['war_torre'] = tower
        
        # Tipo principal (mais frequente)
        battle_type = b.get('type', '')
        tipo_label = BATTLE_TYPE_LABELS.get(battle_type, battle_type)
        tipo_counts[tipo_label] = tipo_counts.get(tipo_label, 0) + 1
    
    # Tipo mais usado
    if tipo_counts:
        stats['war_tipo_principal'] = max(tipo_counts, key=tipo_counts.get)
    
    return stats

def collect_top_global_clans(token, limit=5):
    """Coleta os TOP N clãs do ranking global e seus top 5 jogadores com decks"""
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    
    results = []
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%d')
    
    try:
        r = requests.get(f"{base_url}/locations/global/rankings/clans", headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"ERRO ao buscar ranking global: {r.status_code}")
            return []
        
        data = r.json()
        clans = data.get('items', [])
        
        print(f"\n{'='*60}")
        print(f"COLLECTING TOP GLOBAL WAR - TOP {limit} CLANS")
        print(f"{'='*60}")
        
        for clan_idx, clan in enumerate(clans[:limit], 1):
            clan_name = clan.get('name', 'Unknown')
            clan_tag = clan.get('tag', '')
            clan_fame = clan.get('fame', 0)
            clan_members = clan.get('members', 0)
            
            print(f"\n#{clan_idx} {clan_name} ({clan_tag}) - Fame: {clan_fame}")
            
            try:
                clan_url = clan_tag.replace('#', '%23')
                cr = requests.get(f"{base_url}/clans/{clan_url}/currentriverrace", headers=headers, timeout=15)
                
                if cr.status_code == 200:
                    race_data = cr.json()
                    my_clan = race_data.get('clans', [])
                    clan_race = next((c for c in my_clan if c.get('tag') == clan_tag), None)
                    
                    if clan_race:
                        clan_fame = clan_race.get('fame', 0)
                    
                    participants = next((c.get('participants', []) for c in my_clan if c.get('tag') == clan_tag), [])
                    sorted_players = sorted(participants, key=lambda x: x.get('fame', 0), reverse=True)
                    top_players = sorted_players[:5]
                else:
                    top_players = []
            except:
                top_players = []
            
            for player_idx, player in enumerate(top_players, 1):
                player_tag_player = player.get('tag', '')
                player_name = player.get('name', 'Unknown')
                player_fame = player.get('fame', 0)
                decks_used = player.get('decksUsed', 0)
                boat_attacks = player.get('boatAttacks', 0)
                
                player_decks = {'deck_1': '', 'deck_2': '', 'deck_3': '', 'deck_4': '',
                               'deck_1_tipo': '', 'deck_2_tipo': '', 'deck_3_tipo': '', 'deck_4_tipo': ''}
                
                war_stats = {
                    'war_vitorias': 0, 'war_derrotas': 0, 'war_medals': 0,
                    'war_torre': 'Tower Princess', 'war_tipo_principal': '', 'war_battles_count': 0
                }
                
                if player_tag_player:
                    try:
                        p_tag_url = player_tag_player.replace('#', '%23')
                        br = requests.get(f"{base_url}/players/{p_tag_url}/battlelog", headers=headers, timeout=10)
                        
                        if br.status_code == 200:
                            battles = br.json()
                            war_stats = collect_war_battles_stats(battles)
                            
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
                    'data_coleta': data_hoje,
                    'player_tag_conta': 'TOP_GLOBAL',
                    'clan_posicao': clan_idx,
                    'clan_nome': clan_name,
                    'clan_tag': clan_tag,
                    'clan_fame': clan_fame,
                    'player_posicao': player_idx,
                    'player_nome': player_name,
                    'player_tag': player_tag_player,
                    'player_fame': player_fame,
                    'decks_usados': decks_used,
                    'boat_attacks': boat_attacks,
                    **player_decks,
                    **war_stats
                })
                
                print(f"  - Player #{player_idx}: {player_name} ({player_fame} fame)")
        
        return results
        
    except Exception as e:
        print(f"ERRO ao coletar TOP Global: {e}")
        return []

def collect_river_race_for_account(token, player_tag, suffix=""):
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    
    my_clan_tag = get_clan_tag(token, player_tag)
    if not my_clan_tag:
        print(f"ERRO: Nao foi possivel obter a tag do clan para {player_tag}")
        return []
    
    print(f"Coletando para {player_tag} - Clan: {my_clan_tag}")
    
    clan_url = my_clan_tag.replace('#', '%23')
    r = requests.get(f"{base_url}/clans/{clan_url}/currentriverrace", headers=headers)
    if r.status_code != 200:
        print(f"ERRO ao buscar corrida: {r.status_code}")
        return []
    
    data = r.json()
    clans = data.get('clans', [])
    
    if not clans:
        print("Nenhum clan encontrado na corrida")
        return []
    
    sorted_clans = sorted(clans, key=lambda x: x.get('fame', 0), reverse=True)
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%d')
    results = []
    
    for clan_idx, clan in enumerate(sorted_clans[:5], 1):
        clan_name = clan.get('name', 'Unknown')
        clan_tag = clan.get('tag', '')
        clan_fame = clan.get('fame', 0)
        
        participants = clan.get('participants', [])
        sorted_players = sorted(participants, key=lambda x: x.get('fame', 0), reverse=True)
        top_players = sorted_players[:5]
        
        for player_idx, player in enumerate(top_players, 1):
            player_tag_player = player.get('tag', '')
            player_name = player.get('name', 'Unknown')
            player_fame = player.get('fame', 0)
            decks_used = player.get('decksUsed', 0)
            boat_attacks = player.get('boatAttacks', 0)
            
            player_decks = {'deck_1': '', 'deck_2': '', 'deck_3': '', 'deck_4': '',
                           'deck_1_tipo': '', 'deck_2_tipo': '', 'deck_3_tipo': '', 'deck_4_tipo': ''}
            
            # Inicializar stats de guerra
            war_stats = {
                'war_vitorias': 0,
                'war_derrotas': 0,
                'war_medals': 0,
                'war_torre': 'Tower Princess',
                'war_tipo_principal': '',
                'war_battles_count': 0
            }
            
            if player_tag_player:
                try:
                    p_tag_url = player_tag_player.replace('#', '%23')
                    br = requests.get(f"{base_url}/players/{p_tag_url}/battlelog", headers=headers, timeout=10)
                    
                    if br.status_code == 200:
                        battles = br.json()
                        
                        # Coletar estatísticas de batalha de guerra
                        war_stats = collect_war_battles_stats(battles)
                        
                        # Coletar decks (lógica existente)
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
            
            # Incluir player_tag da conta (não do jogador) - usar tag real do .env
            results.append({
                'data_coleta': data_hoje,
                'player_tag_conta': player_tag,  # player_tag agora é a tag real (#2QR292P ou #2220UQQ0UU)
                'clan_posicao': clan_idx,
                'clan_nome': clan_name,
                'clan_tag': clan_tag,
                'clan_fame': clan_fame,
                'player_posicao': player_idx,
                'player_nome': player_name,
                'player_tag': player_tag_player,
                'player_fame': player_fame,
                'decks_usados': decks_used,
                'boat_attacks': boat_attacks,
                **player_decks,
                **war_stats
            })
    
    return results

def collect_river_race_intelligence():
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    load_dotenv(dotenv_path)
    
    token = os.getenv('CR_API_TOKEN')
    if not token:
        print("ERRO: CR_API_TOKEN nao encontrado")
        return
    
    # Tags reais das contas
    tag_pri_real = os.getenv('CR_PLAYER_TAG', '#2QR292P')
    tag_sec_real = os.getenv('CR_PLAYER_TAG_SEC', '#2220UQQ0UU')

    print("=" * 60)
    print("COLETANDO INTELIGENCIA DE GUERRA - RIVER RACE")
    print("=" * 60)
    
    results_pri = []
    results_sec = []
    
    try:
        print("\n--- TOP GLOBAL ---")
        results_global = collect_top_global_clans(token, limit=5)
    except:
        results_global = []
    
    print("\n--- CONTA PRINCIPAL ---")
    results_pri = collect_river_race_for_account(token, tag_pri_real, '_pri')
    
    print("\n--- CONTA SECUNDARIA ---")
    results_sec = collect_river_race_for_account(token, tag_sec_real, '_sec')
    
    all_results = results_global + results_pri + results_sec
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%d')
    
    # Campos do CSV (agora inclui estatísticas de guerra)
    fieldnames = [
        'data_coleta', 'player_tag_conta', 'clan_posicao', 'clan_nome', 'clan_tag', 'clan_fame',
        'player_posicao', 'player_nome', 'player_tag', 'player_fame', 'decks_usados', 'boat_attacks',
        'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo',
        'war_vitorias', 'war_derrotas', 'war_medals', 'war_torre', 'war_tipo_principal', 'war_battles_count'
    ]
    
    # Arquivo único com todos os dados
    filename = f"{DATA_DIR}/inteligencia_guerra_{data_hoje}.csv"
    
    # Salvar arquivo unificado INICIAL (pode ter dados vazios)
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(results_global)
        writer.writerows(results_pri)
        writer.writerows(results_sec)
    
    import glob
    previous_files = sorted(glob.glob(f"{DATA_DIR}/inteligencia_guerra_*.csv"))
    previous_files = [f for f in previous_files if '_full_' not in f and '_pri_' not in f and '_sec_' not in f and '_2026_05_' not in f]
    
    # Verificar se dados atuais têm DADOS REAIS
    has_real_data_pri = any(
        (r.get('deck_1') and len(r.get('deck_1', '')) > 10) 
        for r in results_pri
    )
    has_real_data_sec = any(
        (r.get('deck_1') and len(r.get('deck_1', '')) > 10) 
        for r in results_sec
    )
    
    if previous_files and not has_real_data_pri:
        latest = max(previous_files)
        print(f"Buscando dados da conta principal do arquivo: {os.path.basename(latest)}")
        try:
            with open(latest, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    ptc = row.get('player_tag_conta', '')
                    if ptc == tag_pri_real:
                        row['data_coleta'] = data_hoje
                        results_pri.append(row)
        except Exception as e:
            print(f"Aviso: Erro ao buscar dados anteriores da conta principal: {e}")
    
    if previous_files and not has_real_data_sec:
        latest = max(previous_files)
        print(f"Buscando dados da conta secundaria do arquivo: {os.path.basename(latest)}")
        try:
            with open(latest, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    ptc = row.get('player_tag_conta', '')
                    if ptc == tag_sec_real:
                        row['data_coleta'] = data_hoje
                        results_sec.append(row)
        except Exception as e:
            print(f"Aviso: Erro ao buscar dados anteriores da conta secundaria: {e}")
    
    # Re-salvar com dados de fallback incluídos
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(results_global)
        writer.writerows(results_pri)
        writer.writerows(results_sec)
    
    print(f"\n\nSUCESSO!")
    print(f"Arquivo: {filename}")
    print(f"  - TOP Global: {len(results_global)} jogadores")
    print(f"  - Conta Principal: {len(results_pri)} jogadores")
    print(f"  - Conta Secundaria: {len(results_sec)} jogadores")
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO - TOP 5 CLANS DA CORRIDA (AMBAS CONTAS)")
    print("=" * 60)
    
    clans_in_results = {}
    for r in all_results:
        cn = r['clan_nome']
        if cn not in clans_in_results:
            clans_in_results[cn] = {'posicao': r['clan_posicao'], 'fame': r['clan_fame'], 'players': 0}
        clans_in_results[cn]['players'] += 1
    
    for cn, info in sorted(clans_in_results.items(), key=lambda x: x[1]['posicao']):
        print(f"#{info['posicao']} {cn} - {info['fame']} fame - {info['players']} players")
    
    # Resumo de batalhas de guerra
    print("\n" + "=" * 60)
    print("RESUMO - BATALHAS DE GUERRA POR CONTA")
    print("=" * 60)
    
    for tag in ['#2QR292P', '#2220UQQ0UU']:
        account_results = [r for r in all_results if r.get('player_tag_conta') == tag]
        if account_results:
            total_vit = sum(r.get('war_vitorias', 0) for r in account_results)
            total_der = sum(r.get('war_derrotas', 0) for r in account_results)
            total_medals = sum(r.get('war_medals', 0) for r in account_results)
            total_battles = sum(r.get('war_battles_count', 0) for r in account_results)
            print(f"\n{tag}:")
            print(f"  Vitórias: {total_vit} | Derrotas: {total_der}")
            print(f"  Medals: {total_medals} | Batalhas: {total_battles}")

if __name__ == "__main__":
    collect_river_race_intelligence()