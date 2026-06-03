#!/usr/bin/env python3
"""
Coleta batalhas de desafio da API Clash Royale e salva em CSV semanal.
Identifica por semana ISO e tipo de desafio (gameMode.name).
Formato: mesmo padrao do oponentes_ano_2026.csv + coluna 'semana_iso' e 'tipo_desafio'.
"""

import os
import sys
import csv
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# Config
# Caminho absoluto para data/csv/ (raiz do projeto)
# O script esta em src/api/, entao subimos 2 niveis
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(_PROJECT_ROOT, 'data', 'csv')
OUTPUT_CSV = os.path.join(DATA_DIR, 'challenge_decks_semanal.csv')
# Garantir que o diretorio existe
os.makedirs(DATA_DIR, exist_ok=True)

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
    'semana_iso', 'tipo_desafio'
]

# Keywords para identificar modos de desafio/evento
CHALLENGE_KEYWORDS = [
    'challenge', 'draft', 'event', 'showdown', 'touchdown',
    'heist', 'pickmode', 'crazy', 'overtime', 'rampup',
    'doubleelixir', 'tripleelixir', '7xelixir', 'blizzard',
    'floodhounds', '1v1_showdown', 'boatbattle', 'duel'
]


def is_challenge(game_mode_name: str, battle_type: str) -> bool:
    """Verifica se a batalha eh um desafio/evento especial."""
    combined = (game_mode_name + ' ' + battle_type).lower().replace(' ', '').replace('_', '')
    return any(kw.replace('_', '') in combined for kw in CHALLENGE_KEYWORDS)


def get_week_iso(dt_utc: datetime) -> str:
    """Retorna a semana ISO no formato YYYY-WNN (ex: 2026-W23)."""
    return dt_utc.strftime('%G-W%V')


def get_api_token() -> str:
    return os.getenv('CR_API_TOKEN', '') or os.getenv('API_TOKEN', '')


def get_player_tags() -> list:
    """Retorna lista de tags de jogadores do .env."""
    tags = []
    primary = os.getenv('CR_PLAYER_TAG', '')
    secondary = os.getenv('CR_PLAYER_TAG_SEC', '')
    if primary:
        tags.append(primary.strip())
    if secondary:
        tags.append(secondary.strip())
    return tags


def fetch_battlelog(api_token: str, player_tag: str) -> list:
    """Busca historico de batalhas da API."""
    clean_tag = player_tag.strip().replace('#', '').upper()
    url = f"https://proxy.royaleapi.dev/v1/players/%23{clean_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ERRO] Falha ao buscar batalhas de {player_tag}: {e}")
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


def extract_challenge_row(battle: dict, player_tag: str) -> dict:
    """Extrai dados de batalha de desafio no formato do CSV."""
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

    # Tipo de desafio: nome do gameMode
    tipo_desafio = game_mode

    def format_hp(hp_list):
        if hp_list is None:
            return "0"
        if isinstance(hp_list, int):
            return str(hp_list)
        return " | ".join(map(str, hp_list))

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
        'tipo_desafio': tipo_desafio
    }


def load_existing_weeks() -> set:
    """Carrega semanas ja existentes no CSV para nao duplicar."""
    weeks = set()
    if not os.path.exists(OUTPUT_CSV):
        return weeks
    with open(OUTPUT_CSV, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            w = row.get('semana_iso', '').strip()
            if w:
                weeks.add(w)
    return weeks


def main():
    api_token = get_api_token()
    if not api_token:
        print("[ERRO] CR_API_TOKEN nao configurado no .env")
        sys.exit(1)

    tags = get_player_tags()
    if not tags:
        print("[ERRO] Nenhuma tag de jogador configurada no .env")
        sys.exit(1)

    # Carregar semanas ja existentes
    existing_weeks = load_existing_weeks()
    today_week = get_week_iso(datetime.now(timezone.utc))
    print(f"[INFO] Semana atual: {today_week}")
    print(f"[INFO] Semanas ja existentes: {existing_weeks}")

    all_rows = []
    for tag in tags:
        print(f"[INFO] Coletando batalhas de desafio para {tag}...")
        battles = fetch_battlelog(api_token, tag)
        if not battles:
            print(f"[AVISO] Nenhuma batalha retornada para {tag}")
            continue

        count = 0
        seen_battles = set()  # evitar duplicatas por battleTime

        for battle in battles:
            bt = battle.get('battleTime', '')
            if bt in seen_battles:
                continue
            seen_battles.add(bt)

            row = extract_challenge_row(battle, tag)
            if row:
                all_rows.append(row)
                count += 1

        print(f"[OK] {count} batalhas de desafio encontradas para {tag}")

    if not all_rows:
        print("[AVISO] Nenhuma batalha de desafio encontrada.")
        return

    # Filtrar: manter apenas linhas de semanas novas ou todas se CSV nao existe
    if existing_weeks:
        new_rows = [r for r in all_rows if r['semana_iso'] not in existing_weeks]
        if not new_rows:
            print(f"[INFO] Todas as semanas ja existem no CSV. Nada a adicionar.")
            return
        rows_to_write = new_rows
        print(f"[INFO] {len(rows_to_write)} batalhas de desafio de semanas novas.")
    else:
        rows_to_write = all_rows
        # Modo append: CSV existe; modo write: CSV novo
        mode = 'a' if os.path.exists(OUTPUT_CSV) else 'w'
    csv_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, 'a' if csv_exists else 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';', extrasaction='ignore')
        if not csv_exists or os.path.getsize(OUTPUT_CSV) == 0:
            writer.writeheader()
        for row in rows_to_write:
            writer.writerow(row)

    print(f"[OK] {len(rows_to_write)} batalhas salvas em {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
