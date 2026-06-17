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

# Modos e tipos de batalha padrao que NAO sao o desafio semanal
NON_CHALLENGE_TYPES = {
    'pvp', 'pathoflegend', 'riverracepvp', 'riverraceduel', 
    'riverraceduelcolosseum', 'boatbattle', 'clanwarwar', 'friendly', 'tournament'
}

NON_CHALLENGE_MODES = {
    'ladder', 'ranked1v1_newarena', 'showdown_friendly', 
    'clanwar_boatbattle', 'challenge', 'grandchallenge', 'tournament'
}


def is_challenge(game_mode_name: str, battle_type: str) -> bool:
    """Verifica se a batalha eh um desafio baseado em exclusao de modos padrao e guerra."""
    b_type = battle_type.lower()
    g_mode = game_mode_name.lower()
    
    if b_type in NON_CHALLENGE_TYPES:
        return False
        
    if g_mode in NON_CHALLENGE_MODES:
        return False
        
    if '2v2' in b_type or '2v2' in g_mode or 'teamvsteam' in g_mode:
        return False
        
    if 'friendly' in g_mode:
        return False
        
    return True


def get_week_iso(dt_utc: datetime) -> str:
    """
    Retorna a semana ISO customizada para Desafios (YYYY-WNN).
    O desafio muda terca-feira as 10:00 UTC (07:00 BRT).
    Subtraimos 34 horas (1 dia + 10 horas) para que terca 10:00 UTC
    seja segunda-feira 00:00 UTC, iniciando a nova semana ISO exatamente no momento certo.
    """
    from datetime import timedelta
    dt_shifted = dt_utc - timedelta(hours=34)
    return dt_shifted.strftime('%G-W%V')


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
        'deck_jogador': 'Aleatório',
        'deck_oponente': 'Aleatório',
        'elixir_vazado_jogador': round(player_team.get('elixirLeaked', 0), 2),
        'elixir_vazado_oponente': round(opponent_team.get('elixirLeaked', 0), 2),
        'nivel_torre_jogador': player_team.get('expLevel', 0),
        'vida_torre_rei_jogador': player_team.get('kingTowerHitPoints', 0),
        'vida_torre_rei_oponente': opponent_team.get('kingTowerHitPoints', 0),
        'torre_jogador': support[0].get('name', 'Tower Princess') if support else 'Tower Princess',
        'torre_oponente': opp_support[0].get('name', 'Tower Princess') if opp_support else 'Tower Princess',
        'elixir_medio_jogador': 0.0,
        'elixir_medio_oponente': 0.0,
        'nivel_medio_deck_jogador': 0.0,
        'nivel_medio_deck_oponente': 0.0,
        'tag_clan_oponente': sanitize(opponent_team.get('clan', {}).get('tag', '')),
        'semana_iso': semana_iso,
        'tipo_desafio': tipo_desafio
    }


def load_existing_battles() -> set:
    """Carrega batalhas ja existentes no CSV para nao duplicar."""
    battles = set()
    if not os.path.exists(OUTPUT_CSV):
        return battles
    with open(OUTPUT_CSV, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            tag = row.get('player_tag', '').strip()
            data = row.get('data', '').strip()
            if tag and data:
                battles.add((tag, data))
    return battles


def collect_from_csv(player_tag: str) -> list:
    """Coleta batalhas de desafio do CSV historico (oponentes_ano_2026.csv)."""
    csv_path = os.path.join(_PROJECT_ROOT, 'data', 'csv', f'oponentes_ano_{datetime.now().year}.csv')
    if not os.path.exists(csv_path):
        print(f"[AVISO] CSV historico nao encontrado: {csv_path}")
        return []

    clean_tag = player_tag.strip().upper()
    if not clean_tag.startswith('#'):
        clean_tag = f'#{clean_tag}'

    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            # Filtrar por player_tag
            row_tag = row.get('player_tag', '').strip().upper()
            if row_tag != clean_tag:
                continue

            modo_jogo = row.get('modo_jogo', '').strip()
            tipo_batalha = row.get('tipo_batalha', '').strip()

            if not is_challenge(modo_jogo, tipo_batalha):
                continue

            # Parse da data
            data_str = row.get('data', '').strip()
            dt_utc = None
            for fmt in ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                try:
                    dt_utc = datetime.strptime(data_str, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue

            if not dt_utc:
                continue

            semana_iso = get_week_iso(dt_utc)

            # Mapear resultado
            resultado = row.get('resultado', '').strip()
            if resultado not in ('Vitoria', 'Derrota', 'Empate'):
                try:
                    coroas_j = int(row.get('coroas_jogador', 0) or 0)
                    coroas_o = int(row.get('coroas_oponente', 0) or 0)
                    if coroas_j > coroas_o:
                        resultado = 'Vitoria'
                    elif coroas_j < coroas_o:
                        resultado = 'Derrota'
                    else:
                        resultado = 'Empate'
                except (ValueError, TypeError):
                    resultado = 'Desconhecido'

            def safe_int(val, default=0):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return default

            def safe_float(val, default=0.0):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default

            rows.append({
                'player_tag': clean_tag,
                'data': dt_utc.strftime('%d/%m/%Y %H:%M'),
                'nome_oponente': sanitize(row.get('nome_oponente', 'Desconhecido')),
                'tag_oponente': row.get('tag_oponente', ''),
                'nivel_oponente': safe_int(row.get('nivel_oponente', 0)),
                'trofes_oponente': safe_int(row.get('trofes_oponente', 0)),
                'clan_oponente': sanitize(row.get('clan_oponente', 'Sem cla')),
                'resultado': resultado,
                'coroas_jogador': safe_int(row.get('coroas_jogador', 0)),
                'coroas_oponente': safe_int(row.get('coroas_oponente', 0)),
                'mudanca_trofes': safe_int(row.get('mudanca_trofes', 0)),
                'modo_jogo': modo_jogo,
                'tipo_batalha': tipo_batalha,
                'arena': row.get('arena', 'Desconhecido'),
                'deck_jogador': row.get('deck_jogador', ''),
                'deck_oponente': row.get('deck_oponente', ''),
                'elixir_vazado_jogador': 0,
                'elixir_vazado_oponente': 0,
                'nivel_torre_jogador': safe_int(row.get('nivel_oponente', 0)),
                'vida_torre_rei_jogador': 0,
                'vida_torre_rei_oponente': 0,
                'torre_jogador': 'Tower Princess',
                'torre_oponente': 'Tower Princess',
                'elixir_medio_jogador': safe_float(row.get('elixir_medio_jogador', 0)),
                'elixir_medio_oponente': safe_float(row.get('elixir_medio_oponente', 0)),
                'nivel_medio_deck_jogador': safe_float(row.get('nivel_medio_deck_jogador', 0)),
                'nivel_medio_deck_oponente': safe_float(row.get('nivel_medio_deck_oponente', 0)),
                'tag_clan_oponente': row.get('tag_clan_oponente', ''),
                'semana_iso': semana_iso,
                'tipo_desafio': modo_jogo,
            })

    return rows


def main():
    api_token = get_api_token()
    if not api_token:
        print("[ERRO] CR_API_TOKEN nao configurado no .env")
        sys.exit(1)

    tags = get_player_tags()
    if not tags:
        print("[ERRO] Nenhuma tag de jogador configurada no .env")
        sys.exit(1)

    # Determinar a semana ISO atual para filtrar (considerando a virada na terca)
    current_week_iso = get_week_iso(datetime.now(timezone.utc))
    print(f"[INFO] Semana ISO atual: {current_week_iso}")

    # Carregar batalhas ja existentes
    existing_battles = load_existing_battles()
    print(f"[INFO] Batalhas ja existentes: {len(existing_battles)}")

    all_rows = []
    for tag in tags:
        print(f"[INFO] Coletando batalhas de desafio para {tag}...")

        # 1. Tentar coletar do CSV historico
        csv_rows = collect_from_csv(tag)
        csv_rows_filtered = [r for r in csv_rows 
                            if r.get('semana_iso') == current_week_iso]
        print(f"[OK] {len(csv_rows_filtered)} batalhas de desafio da {current_week_iso} para {tag} (de {len(csv_rows)} totais)")
        all_rows.extend(csv_rows_filtered)

        # 2. Tentar coletar da API (batalhas mais recentes que podem nao estar no CSV ainda)
        battles = fetch_battlelog(api_token, tag)
    if battles:
        seen_battles = set()
        api_count = 0
        for battle in battles:
            bt = battle.get('battleTime', '')
            if bt in seen_battles:
                continue
            seen_battles.add(bt)
            row = extract_challenge_row(battle, tag)
            if row:
                all_rows.append(row)
                api_count += 1
        print(f"[OK] {api_count} batalhas de desafio da API para {tag}")

    if not all_rows:
        print("[AVISO] Nenhuma batalha de desafio encontrada.")
        return

    # Filtrar: manter apenas batalhas novas
    if existing_battles:
        new_rows = [r for r in all_rows if (r['player_tag'], r['data']) not in existing_battles]
        if not new_rows:
            print(f"[INFO] Todas as batalhas coletadas ja existem no CSV. Nada a adicionar.")
            return
        rows_to_write = new_rows
        print(f"[INFO] {len(rows_to_write)} batalhas de desafio novas para adicionar.")
    else:
        rows_to_write = all_rows

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
