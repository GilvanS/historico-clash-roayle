#!/usr/bin/env python3
"""
Coleta de Decks do Top 5 Global e Top 5 Brasil (Path of Legends).
Obtém os melhores jogadores a partir do ranking de clãs de alta competitividade (Global e Nacional).
Processa o battlelog dinamicamente de forma incremental para consolidar vitórias e derrotas.
"""

import os
import sys
import requests
import json
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Forçar UTF-8 no terminal apenas quando chamado diretamente (sys.stdout real tem .buffer)
import io
if hasattr(sys.stdout, 'buffer') and getattr(sys.stdout, 'encoding', 'utf-8') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# Configuração de diretórios
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
DATA_DIR = os.path.join(project_root, 'data', 'csv')
CSV_PATH = os.path.join(DATA_DIR, 'decks_meta_global.csv')
PROCESSED_JSON_PATH = os.path.join(DATA_DIR, 'processed_meta_battles.json')

def format_deck(cards):
    if not cards: return ""
    return " | ".join(sorted(c.get('name', '') for c in cards))

def load_processed_battles():
    if os.path.exists(PROCESSED_JSON_PATH):
        try:
            with open(PROCESSED_JSON_PATH, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[Aviso] Falha ao carregar batalhas processadas: {e}")
    return set()

def save_processed_battles(processed_set):
    try:
        # Manter o arquivo de tamanho razoável (por exemplo, guardar apenas os últimos 5000 IDs para economizar espaço)
        processed_list = list(processed_set)[-5000:]
        with open(PROCESSED_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(processed_list, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Erro] Falha ao salvar batalhas processadas: {e}")

def load_existing_meta_decks():
    deck_stats = {}
    if os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    deck = row['deck_cards']
                    deck_stats[deck] = {
                        'deck_cards': deck,
                        'total': int(row.get('total', 0)),
                        'wins': int(row.get('wins', 0)),
                        'losses': int(row.get('losses', 0)),
                        'win_rate': float(row.get('win_rate', 0)),
                        'source': row.get('source', 'Global Meta')
                    }
        except Exception as e:
            print(f"[Aviso] Erro ao ler decks_meta_global.csv existente: {e}")
    return deck_stats

def save_meta_decks(deck_stats):
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        # Calcular a taxa de vitória e converter em lista ordenada
        final_list = []
        for d in deck_stats.values():
            if d['total'] > 0:
                d['win_rate'] = round((d['wins'] / d['total'] * 100), 1)
                final_list.append(d)
        
        # Ordenar por partidas jogadas e depois por taxa de vitória
        final_list.sort(key=lambda x: (x['total'], x['win_rate']), reverse=True)
        
        # Limita aos 15 melhores decks mais jogados/relevantes do mês
        final_list = final_list[:15]
        
        with open(CSV_PATH, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['deck_cards', 'total', 'wins', 'losses', 'win_rate', 'source'])
            writer.writeheader()
            for row in final_list:
                writer.writerow(row)
        print(f"[Meta] Sucesso! CSV de decks meta atualizado em: {CSV_PATH}")
    except Exception as e:
        print(f"[Erro] Falha ao salvar decks meta no CSV: {e}")

def get_best_player_from_clan(clan_tag, headers):
    clan_url = clan_tag.replace('#', '%23')
    url = f"https://proxy.royaleapi.dev/v1/clans/{clan_url}/members"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            members = r.json().get('items', [])
            if members:
                # O primeiro membro da lista é ordenado por troféus, ou seja, clanRank: 1
                return members[0]
    except Exception as e:
        print(f"      [Aviso] Falha ao buscar membros para o clã {clan_tag}: {e}")
    return None

def collect_top_meta_decks():
    token = os.getenv('CR_API_TOKEN')
    if not token:
        print("[ERRO] Token da API do Clash Royale não configurado no .env.")
        sys.stdout.flush()
        return
        
    headers = {'Authorization': f'Bearer {token}'}
    processed_battles = load_processed_battles()
    deck_stats = load_existing_meta_decks()
    
    # 1. Obter Clãs do Top Global
    global_clans_url = "https://proxy.royaleapi.dev/v1/locations/global/rankings/clans?limit=10"
    print("[Meta] Buscando clãs do Top Global...")
    sys.stdout.flush()
    
    global_clans = []
    try:
        r = requests.get(global_clans_url, headers=headers, timeout=20)
        if r.status_code == 200:
            global_clans = r.json().get('items', [])
        else:
            print(f"[Erro] Falha ao consultar ranking de clãs Global: Código {r.status_code}")
    except Exception as e:
        print(f"[Erro] Conexão com ranking de clãs Global falhou: {e}")
        
    # 2. Obter Clãs do Top Brasil (location_id: 57000038)
    br_clans_url = "https://proxy.royaleapi.dev/v1/locations/57000038/rankings/clans?limit=10"
    print("[Meta] Buscando clãs do Top Brasil...")
    sys.stdout.flush()
    
    br_clans = []
    try:
        r = requests.get(br_clans_url, headers=headers, timeout=20)
        if r.status_code == 200:
            br_clans = r.json().get('items', [])
        else:
            print(f"[Erro] Falha ao consultar ranking de clãs Brasil: Código {r.status_code}")
    except Exception as e:
        print(f"[Erro] Conexão com ranking de clãs Brasil falhou: {e}")

    # 3. Filtrar sem duplicar: Obter o jogador Top de 5 clãs Globais e 5 clãs do Brasil
    selected_players = []
    processed_tags = set()
    
    print("[Meta] Selecionando jogadores elite dos melhores clãs Globais...")
    sys.stdout.flush()
    globais_added = 0
    for clan in global_clans:
        if globais_added >= 5:
            break
        c_tag = clan.get('tag')
        c_name = clan.get('name')
        if c_tag:
            player = get_best_player_from_clan(c_tag, headers)
            if player:
                p_tag = player.get('tag')
                p_name = player.get('name')
                if p_tag and p_tag not in processed_tags:
                    player['source_type'] = 'Global Meta'
                    player['clan_name'] = c_name
                    selected_players.append(player)
                    processed_tags.add(p_tag)
                    globais_added += 1
                    print(f"  -> Selecionado Top Global: {p_name} ({p_tag}) do clã {c_name}")
                    sys.stdout.flush()

    print("[Meta] Selecionando jogadores elite dos melhores clãs do Brasil...")
    sys.stdout.flush()
    br_added = 0
    for clan in br_clans:
        if br_added >= 5:
            break
        c_tag = clan.get('tag')
        c_name = clan.get('name')
        if c_tag:
            player = get_best_player_from_clan(c_tag, headers)
            if player:
                p_tag = player.get('tag')
                p_name = player.get('name')
                if p_tag and p_tag not in processed_tags:
                    player['source_type'] = 'Global Meta'  # Para exibição em Ranked no dashboard
                    player['clan_name'] = c_name
                    selected_players.append(player)
                    processed_tags.add(p_tag)
                    br_added += 1
                    print(f"  -> Selecionado Top Brasil: {p_name} ({p_tag}) do clã {c_name}")
                    sys.stdout.flush()

    print(f"[Meta] Processo de seleção finalizado. {len(selected_players)} jogadores elite monitorados.")
    sys.stdout.flush()
    
    # 4. Buscar battlelogs dos jogadores
    new_battles_count = 0
    failed_players = []
    
    for idx, p in enumerate(selected_players, 1):
        tag = p.get('tag')
        name = p.get('name')
        source_type = p.get('source_type')
        print(f"  [{idx}/10] Analisando battlelog de: {name} ({tag})")
        sys.stdout.flush()
        
        tag_url = tag.replace('#', '%23')
        battlelog_url = f"https://proxy.royaleapi.dev/v1/players/{tag_url}/battlelog"
        
        try:
            r = requests.get(battlelog_url, headers=headers, timeout=20)
            if r.status_code != 200:
                print(f"    [Aviso] Falha ao buscar battlelog para {name}: {r.status_code}")
                continue
                
            battles = r.json()
            for b in battles:
                battle_type = b.get('type', '')
                # Processa apenas batalhas da rankeada / Rota das Lendas / Ladder
                if battle_type in ['pathOfLegend', 'pathOfLegends', 'ladder']:
                    team = b.get('team', [{}])[0]
                    opp = b.get('opponent', [{}])[0]
                    
                    battle_time = b.get('battleTime', '')
                    battle_id = f"{battle_time}_{tag}"
                    
                    # Ignorar se já processou essa batalha
                    if battle_id in processed_battles:
                        continue
                    
                    cards = team.get('cards', [])
                    deck_str = format_deck(cards)
                    
                    if not deck_str or len(cards) < 8:
                        continue
                        
                    p_crowns = team.get('crowns', 0)
                    o_crowns = opp.get('crowns', 0)
                    is_victory = p_crowns > o_crowns
                    
                    # Registrar nova batalha
                    processed_battles.add(battle_id)
                    new_battles_count += 1
                    
                    # Incrementar estatísticas do deck
                    if deck_str not in deck_stats:
                        deck_stats[deck_str] = {
                            'deck_cards': deck_str,
                            'total': 0,
                            'wins': 0,
                            'losses': 0,
                            'win_rate': 0.0,
                            'source': source_type
                        }
                    
                    deck_stats[deck_str]['total'] += 1
                    if is_victory:
                        deck_stats[deck_str]['wins'] += 1
                    else:
                        deck_stats[deck_str]['losses'] += 1
                        
        except Exception as e:
            print(f"    [Erro] Falha ao obter dados do battlelog do jogador {name}: {e}")
            sys.stdout.flush()
            failed_players.append(p)
            
    # Retentativa no final para os jogadores que falharam
    if failed_players:
        print(f"\n[Meta] Tentando novamente {len(failed_players)} jogador(es) que falhou(aram) por timeout...")
        sys.stdout.flush()
        for p in failed_players:
            tag = p.get('tag')
            name = p.get('name')
            source_type = p.get('source_type')
            print(f"  [Retentativa] Analisando battlelog de: {name} ({tag})")
            sys.stdout.flush()
            
            tag_url = tag.replace('#', '%23')
            battlelog_url = f"https://proxy.royaleapi.dev/v1/players/{tag_url}/battlelog"
            
            try:
                r = requests.get(battlelog_url, headers=headers, timeout=30) # Aumentando timeout na retentativa
                if r.status_code != 200:
                    print(f"    [Aviso] Falha ao buscar battlelog na retentativa para {name}: {r.status_code}")
                    continue
                    
                battles = r.json()
                for b in battles:
                    battle_type = b.get('type', '')
                    if battle_type in ['pathOfLegend', 'pathOfLegends', 'ladder']:
                        team = b.get('team', [{}])[0]
                        opp = b.get('opponent', [{}])[0]
                        
                        battle_time = b.get('battleTime', '')
                        battle_id = f"{battle_time}_{tag}"
                        
                        if battle_id in processed_battles:
                            continue
                        
                        cards = team.get('cards', [])
                        deck_str = format_deck(cards)
                        
                        if not deck_str or len(cards) < 8:
                            continue
                            
                        p_crowns = team.get('crowns', 0)
                        o_crowns = opp.get('crowns', 0)
                        is_victory = p_crowns > o_crowns
                        
                        processed_battles.add(battle_id)
                        new_battles_count += 1
                        
                        if deck_str not in deck_stats:
                            deck_stats[deck_str] = {
                                'deck_cards': deck_str, 'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0.0, 'source': source_type
                            }
                        
                        deck_stats[deck_str]['total'] += 1
                        if is_victory:
                            deck_stats[deck_str]['wins'] += 1
                        else:
                            deck_stats[deck_str]['losses'] += 1
            except Exception as e:
                print(f"    [Erro Crítico] Falha definitiva para o jogador {name} na retentativa: {e}")
                sys.stdout.flush()

    print(f"[Meta] Processamento concluído. {new_battles_count} novas batalhas agregadas.")
    sys.stdout.flush()
    
    # 5. Salvar os arquivos consolidados
    if new_battles_count > 0:
        save_processed_battles(processed_battles)
        save_meta_decks(deck_stats)
    else:
        print("[Meta] Nenhuma batalha nova encontrada nos battlelogs do meta.")
        sys.stdout.flush()

if __name__ == "__main__":
    collect_top_meta_decks()
