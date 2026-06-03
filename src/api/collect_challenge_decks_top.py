#!/usr/bin/env python3
"""
Coleta decks de desafio dos Top Players Globais e Brasil.
Usa os mesmos jogadores do collect_top_meta_global.py.
Filtra batalhas por tipo de desafio (TripleElixir, 7xElixir, etc.)
e salva em CSV semanal para a aba Desafios do dashboard.
"""

import os
import sys
import csv
import requests
import json
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(_PROJECT_ROOT, 'data', 'csv')
OUTPUT_CSV = os.path.join(DATA_DIR, 'challenge_decks_semanal.csv')
PROCESSED_JSON_PATH = os.path.join(DATA_DIR, 'processed_challenge_battles.json')

FIELDNAMES = [
    'player_tag', 'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente',
    'elixir_vazado_jogador', 'elixir_vazado_oponente',
    'nivel_torre_jogador', 'vida_torre_rei_jogador', 'vida_torre_rei_oponente',
    'torre_jogador', 'torre_oponente',
    'elixir_medio_jogador', 'elixir_medio_oponente',
    'nivel_medio_deck_jogador', 'nivel_medio_deck_oponente',
    'tag_clan_oponente',
    'semana_iso', 'tipo_desafio', 'source_type'
]

CHALLENGE_KEYWORDS = [
    'challenge', 'draft', 'event', 'showdown', 'touchdown',
    'heist', 'pickmode', 'crazy', 'overtime', 'rampup',
    'doubleelixir', 'tripleelixir', '7xelixir', 'blizzard',
    'floodhounds', '1v1_showdown', 'boatbattle', 'duel'
]


def is_challenge(game_mode_name: str, battle_type: str) -> bool:
    combined = (game_mode_name + ' ' + battle_type).lower().replace(' ', '').replace('_', '')
    return any(kw.replace('_', '') in combined for kw in CHALLENGE_KEYWORDS)


def get_week_iso(dt_utc: datetime) -> str:
    return dt_utc.strftime('%G-W%V')


def get_api_token() -> str:
    return os.getenv('CR_API_TOKEN', '') or os.getenv('API_TOKEN', '')


def get_best_player_from_clan(clan_tag: str, headers: dict) -> dict:
    """Busca o melhor jogador de um clã (maior trophy)."""
    clan_url = clan_tag.replace('#', '').strip()
    url = f"https://proxy.royaleapi.dev/v1/clans/%23{clan_url}/members"
    try:
        resp = requests.get(url, headers=headers, params={'limit': 50}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get('items', [])
        if not items:
            return None
        # Retorna o jogador com mais troféus
        best = max(items, key=lambda x: x.get('trophies', 0))
        return best
    except Exception as e:
        print(f"      [Aviso] Falha ao buscar membros do clã {clan_tag}: {e}")
        return None


def get_top_players(headers: dict) -> list:
    """Busca top players globais e do Brasil a partir do ranking de clãs."""
    selected_players = []
    processed_tags = set()

    # Ranking Global de Clãs
    print("[INFO] Buscando ranking global de clãs...")
    global_clans_url = "https://proxy.royaleapi.dev/v1/locations/global/rankings/clans?limit=10"
    try:
        r = requests.get(global_clans_url, headers=headers, timeout=15)
        r.raise_for_status()
        clans = r.json().get('items', [])
        for clan in clans:
            c_tag = clan.get('tag')
            c_name = clan.get('name', 'Desconhecido')
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
                        print(f"  -> Top Global: {p_name} ({p_tag}) do clã {c_name}")
    except Exception as e:
        print(f"[ERRO] Falha ao buscar ranking global: {e}")

    # Ranking Brasil de Clãs
    print("[INFO] Buscando ranking Brasil de clãs...")
    br_clans_url = "https://proxy.royaleapi.dev/v1/locations/57000038/rankings/clans?limit=10"
    try:
        r = requests.get(br_clans_url, headers=headers, timeout=15)
        r.raise_for_status()
        clans = r.json().get('items', [])
        for clan in clans:
            c_tag = clan.get('tag')
            c_name = clan.get('name', 'Desconhecido')
            if c_tag:
                player = get_best_player_from_clan(c_tag, headers)
                if player:
                    p_tag = player.get('tag')
                    p_name = player.get('name')
                    if p_tag and p_tag not in processed_tags:
                        player['source_type'] = 'Brasil Meta'
                        player['clan_name'] = c_name
                        selected_players.append(player)
                        processed_tags.add(p_tag)
                        print(f"  -> Top Brasil: {p_name} ({p_tag}) do clã {c_name}")
    except Exception as e:
        print(f"[ERRO] Falha ao buscar ranking Brasil: {e}")

    return selected_players


def fetch_battlelog(api_token: str, player_tag: str) -> list:
    clean_tag = player_tag.strip().replace('#', '').upper()
    url = f"https://proxy.royaleapi.dev/v1/players/%23{clean_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [ERRO] Falha ao buscar batalhas de {player_tag}: {e}")
        return []


def parse_battle_time(bt_str: str):
    try:
        if len(bt_str) >= 15:
            return datetime.strptime(bt_str[:15], '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    return None


def format_deck(cards: list) -> str:
    if not cards:
        return ''
    return ' | '.join(c.get('name', '') for c in cards)


def sanitize(text) -> str:
    if not text:
        return ""
    return str(text).replace(';', '-')


def avg_elixir(cards: list) -> float:
    if not cards:
        return 0.0
    vals = [c.get('elixirCost', 0) for c in cards if 'elixirCost' in c]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def avg_level(cards: list) -> float:
    if not cards:
        return 0.0
    vals = [c.get('level', 0) for c in cards if 'level' in c]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def extract_challenge_row(battle: dict, player_tag: str, source_type: str) -> dict:
    search_tag = player_tag.strip().upper()
    if not search_tag.startswith('#'):
        search_tag = f"#{search_tag}"

    teams = battle.get('team', [])
    player_team = next((t for t in teams if t.get('tag', '').strip().upper() == search_tag), None)
    if not player_team:
        alt = search_tag.replace('#', '')
        player_team = next((t for t in teams if t.get('tag', '').strip().upper() == alt), None)
    if not player_team:
        return None

    opponents = battle.get('opponent', [])
    opponent_team = opponents[0] if opponents else None
    if not opponent_team:
        return None

    game_mode = battle.get('gameMode', {}).get('name', 'Desconhecido')
    battle_type = battle.get('type', 'Desconhecido')

    if not is_challenge(game_mode, battle_type):
        return None

    dt_utc = parse_battle_time(battle.get('battleTime', ''))
    if not dt_utc:
        return None

    player_crowns = player_team.get('crowns', 0)
    opponent_crowns = opponent_team.get('crowns', 0)

    if player_crowns > opponent_crowns:
        resultado = 'Vitoria'
    elif player_crowns < opponent_crowns:
        resultado = 'Derrota'
    else:
        resultado = 'Empate'

    semana_iso = get_week_iso(dt_utc)
    tipo_desafio = game_mode

    support = player_team.get('supportCards', [])
    opp_support = opponent_team.get('supportCards', [])

    return {
        'player_tag': search_tag,
        'data': dt_utc.strftime('%d/%m/%Y %H:%M'),
        'nome_oponente': sanitize(opponent_team.get('name', 'Desconhecido')),
        'tag_oponente': opponent_team.get('tag', ''),
        'nivel_oponente': opponent_team.get('expLevel', 0),
        'trofes_oponente': opponent_team.get('startingTrophies', 0),
        'clan_oponente': sanitize(opponent_team.get('clan', {}).get('name', 'Sem cla')),
        'resultado': resultado,
        'coroas_jogador': player_crowns,
        'coroas_oponente': opponent_crowns,
        'mudanca_trofes': player_team.get('trophyChange', 0),
        'modo_jogo': game_mode,
        'tipo_batalha': battle_type,
        'arena': battle.get('arena', {}).get('name', 'Desconhecido'),
        'deck_jogador': format_deck(player_team.get('cards', [])),
        'deck_oponente': format_deck(opponent_team.get('cards', [])),
        'elixir_vazado_jogador': round(player_team.get('elixirLeaked', 0), 2),
        'elixir_vazado_oponente': round(opponent_team.get('elixirLeaked', 0), 2),
        'nivel_torre_jogador': player_team.get('expLevel', 0),
        'vida_torre_rei_jogador': player_team.get('kingTowerHitPoints', 0),
        'vida_torre_rei_oponente': opponent_team.get('kingTowerHitPoints', 0),
        'torre_jogador': support[0].get('name', 'Tower Princess') if support else 'Tower Princess',
        'torre_oponente': opp_support[0].get('name', 'Tower Princess') if opp_support else 'Tower Princess',
        'elixir_medio_jogador': avg_elixir(player_team.get('cards', [])),
        'elixir_medio_oponente': avg_elixir(opponent_team.get('cards', [])),
        'nivel_medio_deck_jogador': avg_level(player_team.get('cards', [])),
        'nivel_medio_deck_oponente': avg_level(opponent_team.get('cards', [])),
        'tag_clan_oponente': sanitize(opponent_team.get('clan', {}).get('tag', '')),
        'semana_iso': semana_iso,
        'tipo_desafio': tipo_desafio,
        'source_type': source_type,
    }


def load_processed_battles() -> set:
    if os.path.exists(PROCESSED_JSON_PATH):
        try:
            with open(PROCESSED_JSON_PATH, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            pass
    return set()


def save_processed_battles(processed_set: set):
    try:
        processed_list = list(processed_set)[-5000:]
        with open(PROCESSED_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(processed_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Erro] Falha ao salvar batalhas processadas: {e}")


def main():
    api_token = get_api_token()
    if not api_token:
        print("[ERRO] CR_API_TOKEN nao configurado no .env")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {api_token}"}
    os.makedirs(DATA_DIR, exist_ok=True)

    # Carregar batalhas já processadas
    processed_battles = load_processed_battles()
    print(f"[INFO] Batalhas ja processadas: {len(processed_battles)}")

    # Buscar top players
    top_players = get_top_players(headers)
    print(f"[INFO] Total de top players: {len(top_players)}")

    if not top_players:
        print("[ERRO] Nenhum top player encontrado.")
        sys.exit(1)

    all_rows = []
    for player in top_players:
        p_tag = player.get('tag', '')
        p_name = player.get('name', '?')
        source = player.get('source_type', 'Global Meta')
        print(f"\n[INFO] Coletando batalhas de desafio de {p_name} ({p_tag}) [{source}]...")

        battles = fetch_battlelog(api_token, p_tag)
        if not battles:
            print(f"  [AVISO] Nenhuma batalha retornada")
            continue

        count = 0
        for battle in battles:
            bt = battle.get('battleTime', '')
            if bt in processed_battles:
                continue

            row = extract_challenge_row(battle, p_tag, source)
            if row:
                all_rows.append(row)
                processed_battles.add(bt)
                count += 1

        print(f"  [OK] {count} batalhas de desafio encontradas")

    if not all_rows:
        print("\n[AVISO] Nenhuma batalha de desafio encontrada dos top players.")
        return

    # Salvar no CSV
    csv_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, 'a' if csv_exists else 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';', extrasaction='ignore')
        if not csv_exists or os.path.getsize(OUTPUT_CSV) == 0:
            writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    # Salvar batalhas processadas
    save_processed_battles(processed_battles)

    print(f"\n[OK] {len(all_rows)} batalhas de desafio dos top players salvas em {OUTPUT_CSV}")

    # Resumo por tipo de desafio
    from collections import Counter
    counter = Counter(r['tipo_desafio'] for r in all_rows)
    print("\n[RESUMO] Batalhas por tipo de desafio:")
    for tipo, cnt in counter.most_common():
        print(f"  {cnt:3d} | {tipo}")


if __name__ == '__main__':
    main()
