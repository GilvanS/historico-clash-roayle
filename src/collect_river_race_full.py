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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data_clan')
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

def get_clan_tag(token, player_tag, fallback_tag=None):
    """Obtém a tag do clã do jogador usando a API, com fallback para env var ou tag fornecida"""
    clean = player_tag.replace('#', '%23')
    try:
        r = requests.get(f"https://proxy.royaleapi.dev/v1/players/{clean}", headers={'Authorization': f'Bearer {token}'}, timeout=10)
        if r.status_code == 200:
            clan_tag = r.json().get('clan', {}).get('tag')
            if clan_tag:
                return clan_tag
    except Exception as e:
        print(f"Aviso: API do jogador {player_tag} falhou: {e}")
    
    # Fallback: usar tag fornecida ou env var
    if fallback_tag:
        print(f"Usando fallback de clã fornecido: {fallback_tag}")
        return fallback_tag
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
                                    
                                    if len(cards) > 8:
                                        for idx in range(0, len(cards), 8):
                                            sub_cards = cards[idx:idx+8]
                                            deck_str = format_deck(sub_cards)
                                            if deck_str and deck_str not in decks_collected:
                                                decks_collected.append(deck_str)
                                                deck_types.append(BATTLE_TYPE_LABELS.get(battle_type, battle_type))
                                    else:
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

def collect_river_race_for_account(token, player_tag, suffix="", clan_tag_fallback=None):
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    
    my_clan_tag = get_clan_tag(token, player_tag, fallback_tag=clan_tag_fallback)
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
                        
                        # Coletar decks
                        decks_collected = []
                        deck_types = []
                        
                        for b in battles:
                            battle_type = b.get('type', '')
                            if battle_type in WAR_BATTLE_TYPES:
                                team = b.get('team', [{}])[0]
                                cards = team.get('cards', [])
                                
                                if len(cards) > 8:
                                    for idx in range(0, len(cards), 8):
                                        sub_cards = cards[idx:idx+8]
                                        deck_str = format_deck(sub_cards)
                                        if deck_str and deck_str not in decks_collected:
                                            decks_collected.append(deck_str)
                                            deck_types.append(BATTLE_TYPE_LABELS.get(battle_type, battle_type))
                                else:
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

def get_logical_date_and_battle_day():
    """Retorna data coleta logica e dia batalha com base no reset pontual das 07:00:00 da manha."""
    now = datetime.now()
    if now.hour < 7:
        logical_date = now - timedelta(days=1)
    else:
        logical_date = now
    
    data_str = logical_date.strftime('%Y-%m-%d')
    wd = logical_date.weekday()
    
    # Quinta=Reset (3), Sexta=Dia 1 (4), Sabado=Dia 2 (5), Domingo=Dia 3 (6), Segunda=Dia 4 (0), outros=Reset
    if wd == 3:
        dia_batalha = 'Reset'
    elif wd == 4:
        dia_batalha = 'Dia 1'
    elif wd == 5:
        dia_batalha = 'Dia 2'
    elif wd == 6:
        dia_batalha = 'Dia 3'
    elif wd == 0:
        dia_batalha = 'Dia 4'
    else:
        dia_batalha = 'Reset'
        
    return data_str, dia_batalha

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
    
    # Tags de cla fixas (fallback caso API nao retorne)
    clan_tag_pri = os.getenv('CR_CLAN_TAG') or ''
    clan_tag_sec = os.getenv('CR_CLAN_TAG_SEC') or ''

    print("=" * 60)
    print("COLETANDO INTELIGENCIA DE GUERRA - RIVER RACE")
    print("=" * 60)
    
    results_pri = []
    results_sec = []
    
    try:
        print("\n--- TOP GLOBAL ---")
        results_global = collect_top_global_clans(token, limit=5)
    except Exception as e:
        print(f"Aviso: Erro ao coletar TOP Global: {e}")
        results_global = []
    
    print("\n--- CONTA PRINCIPAL ---")
    results_pri = collect_river_race_for_account(token, tag_pri_real, '_pri', clan_tag_fallback=clan_tag_pri)
    
    print("\n--- CONTA SECUNDARIA ---")
    results_sec = collect_river_race_for_account(token, tag_sec_real, '_sec', clan_tag_fallback=clan_tag_sec)
    
    data_hoje, dia_batalha = get_logical_date_and_battle_day()
    
    # Verificar se dados atuais têm DADOS REAIS
    has_real_data_global = any(
        (r.get('deck_1') and len(r.get('deck_1', '')) > 10)
        for r in results_global
    )
    has_real_data_pri = any(
        (r.get('deck_1') and len(r.get('deck_1', '')) > 10) 
        for r in results_pri
    )
    has_real_data_sec = any(
        (r.get('deck_1') and len(r.get('deck_1', '')) > 10) 
        for r in results_sec
    )
    
    guerra_hist_path = f"{DATA_DIR}/guerra_historico.csv"
    
    # Mapear fallbacks a partir do arquivo guerra_historico.csv mestre se necessario
    if not has_real_data_global or not has_real_data_pri or not has_real_data_sec:
        if os.path.exists(guerra_hist_path):
            try:
                historical_rows = []
                with open(guerra_hist_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        historical_rows.append(row)
                
                # Achar a data mais recente que nao seja a data de hoje
                dates_before_today = sorted(list(set(
                    row['data_coleta'] for row in historical_rows 
                    if row['data_coleta'] < data_hoje
                )), reverse=True)
                
                if dates_before_today:
                    latest_date = dates_before_today[0]
                    print(f"Buscando fallback de dados anteriores da data: {latest_date}")
                    
                    if not has_real_data_global:
                        print("Fallback para TOP Global...")
                        results_global = []
                        for row in historical_rows:
                            if row['data_coleta'] == latest_date and row.get('conta_tipo') == 'TOP_GLOBAL':
                                new_row = row.copy()
                                new_row['data_coleta'] = data_hoje
                                new_row['dia_batalha'] = dia_batalha
                                results_global.append(new_row)
                    
                    if not has_real_data_pri:
                        print("Fallback para Conta Principal...")
                        results_pri = []
                        for row in historical_rows:
                            if row['data_coleta'] == latest_date and row.get('conta_tipo') == tag_pri_real:
                                new_row = row.copy()
                                new_row['data_coleta'] = data_hoje
                                new_row['dia_batalha'] = dia_batalha
                                results_pri.append(new_row)
                                
                    if not has_real_data_sec:
                        print("Fallback para Conta Secundaria...")
                        results_sec = []
                        for row in historical_rows:
                            if row['data_coleta'] == latest_date and row.get('conta_tipo') == tag_sec_real:
                                new_row = row.copy()
                                new_row['data_coleta'] = data_hoje
                                new_row['dia_batalha'] = dia_batalha
                                results_sec.append(new_row)
            except Exception as e:
                print(f"Aviso: Erro ao buscar dados do historico para fallback: {e}")

    # Campos oficiais do guerra_historico.csv mestre
    fieldnames = [
        'data_coleta', 'dia_batalha', 'conta_tipo', 'player_tag', 'player_nome', 
        'player_fame', 'player_posicao', 'clan_tag', 'clan_nome', 'clan_posicao', 
        'clan_fame', 'decks_usados', 'boat_attacks', 
        'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 
        'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo',
        'war_vitorias', 'war_derrotas', 'war_medals', 'war_torre', 'war_battles_count'
    ]
    
    # Preparar novos registros mapeando chaves
    new_records = []
    for r in results_global + results_pri + results_sec:
        # Resolve conta_tipo e player_tag_conta de forma unificada
        conta_tipo_val = r.get('player_tag_conta', r.get('conta_tipo', 'TOP_GLOBAL'))
        if not conta_tipo_val:
            conta_tipo_val = 'TOP_GLOBAL'
            
        rec = {
            'data_coleta': data_hoje,
            'dia_batalha': dia_batalha,
            'conta_tipo': conta_tipo_val,
            'player_tag': r.get('player_tag', ''),
            'player_nome': r.get('player_nome', ''),
            'player_fame': r.get('player_fame', '0'),
            'player_posicao': r.get('player_posicao', '0'),
            'clan_tag': r.get('clan_tag', ''),
            'clan_nome': r.get('clan_nome', ''),
            'clan_posicao': r.get('clan_posicao', '0'),
            'clan_fame': r.get('clan_fame', '0'),
            'decks_usados': r.get('decks_usados', '0'),
            'boat_attacks': r.get('boat_attacks', '0'),
            'deck_1': r.get('deck_1') if r.get('deck_1') else '',
            'deck_1_tipo': r.get('deck_1_tipo') if r.get('deck_1_tipo') else '',
            'deck_2': r.get('deck_2') if r.get('deck_2') else '',
            'deck_2_tipo': r.get('deck_2_tipo') if r.get('deck_2_tipo') else '',
            'deck_3': r.get('deck_3') if r.get('deck_3') else '',
            'deck_3_tipo': r.get('deck_3_tipo') if r.get('deck_3_tipo') else '',
            'deck_4': r.get('deck_4') if r.get('deck_4') else '',
            'deck_4_tipo': r.get('deck_4_tipo') if r.get('deck_4_tipo') else '',
            'war_vitorias': r.get('war_vitorias', '0'),
            'war_derrotas': r.get('war_derrotas', '0'),
            'war_medals': r.get('war_medals', '0'),
            'war_torre': r.get('war_torre', 'Tower Princess'),
            'war_battles_count': r.get('war_battles_count', '0')
        }
        new_records.append(rec)
        
    # Determinar quais tipos de conta TEM dados novos (para nao remover dados sem substituto)
    account_types_com_new_data = set(r.get('conta_tipo', '') for r in new_records)
    
    # Carregar registros existentes
    existing_records = []
    if os.path.exists(guerra_hist_path):
        try:
            with open(guerra_hist_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    row_conta = row.get('conta_tipo', '')
                    # Idempotencia segura: so remove registros de hoje se tiver dados NOVOS para ESSE tipo de conta
                    if row.get('data_coleta') == data_hoje and row_conta in account_types_com_new_data:
                        continue
                    existing_records.append(row)
        except Exception as e:
            print(f"Aviso: Erro ao ler guerra_historico.csv para idempotencia: {e}")
            
    # Concatenar todos os registros
    final_records = existing_records + new_records
    
    # Ordenar registros finais por data decrescente e fama decrescente do jogador
    final_records = sorted(
        final_records,
        key=lambda x: (x['data_coleta'], -int(x.get('player_fame', 0) or 0)),
        reverse=True
    )
    
    # Gravar no guerra_historico.csv consolidado
    try:
        with open(guerra_hist_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(final_records)
        print(f"SUCESSO: Gravado de forma idempotente em {guerra_hist_path} ({len(new_records)} novos, {len(final_records)} total)")
    except Exception as e:
        print(f"ERRO ao gravar guerra_historico.csv consolidado: {e}")

    # Salvar tambem um arquivo temporario diario para debug se necessario (opcional, mantendo compatibilidade)
    temp_filename = f"{DATA_DIR}/inteligencia_guerra_{data_hoje}.csv"
    try:
        with open(temp_filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            # Filtra registros apenas do dia de hoje para o arquivo diario
            today_records = [r for r in final_records if r['data_coleta'] == data_hoje]
            writer.writerows(today_records)
    except Exception as e:
        print(f"Aviso: Erro ao criar copia diaria de debug: {e}")

    print(f"\n\nSUCESSO!")
    print(f"Arquivo Consolidado: {guerra_hist_path}")
    print(f"  - TOP Global: {len([r for r in new_records if r['conta_tipo'] == 'TOP_GLOBAL'])} jogadores")
    print(f"  - Conta Principal: {len([r for r in new_records if r['conta_tipo'] == tag_pri_real])} jogadores")
    print(f"  - Conta Secundaria: {len([r for r in new_records if r['conta_tipo'] == tag_sec_real])} jogadores")

if __name__ == "__main__":
    collect_river_race_intelligence()