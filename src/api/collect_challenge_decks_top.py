#!/usr/bin/env python3
"""
Coleta decks de desafio dos Top 100 Players Globais e Brasil.
- Varre top 100 clãs global + top 100 clãs Brasil
- Pega os melhores jogadores de cada clã
- Filtra batalhas por tipo de desafio (TripleElixir, Draft, etc.)
- Agrega decks repetidos: soma wins/losses/draws, calcula WR média
- Regista tags dos jogadores que usam cada deck
- Salva em CSV compatível com challenge_decks_semanal.csv
"""

import os
import sys
import csv
import json
import requests
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(_PROJECT_ROOT, 'data', 'csv')
OUTPUT_CSV = os.path.join(DATA_DIR, 'challenge_decks_semanal.csv')
PROCESSED_JSON = os.path.join(DATA_DIR, 'processed_challenge_top_battles.json')

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
    'semana_iso', 'tipo_desafio', 'source_type',
    'deck_key', 'jogador_tags', 'total_jogadores'
]

CHALLENGE_KEYWORDS = [
    'tripleelixir'
]


def is_challenge(game_mode_name: str, battle_type: str) -> bool:
    combined = (game_mode_name + ' ' + battle_type).lower().replace(' ', '').replace('_', '').replace('-', '')
    return any(kw.replace('_', '').replace('-', '') in combined for kw in CHALLENGE_KEYWORDS)


def get_week_iso(dt_utc: datetime) -> str:
    return dt_utc.strftime('%G-W%V')


def get_api_token() -> str:
    token = os.getenv('CR_API_TOKEN', '') or os.getenv('API_TOKEN', '')
    if not token:
        print("[ERRO] CR_API_TOKEN nao configurado no .env")
        sys.exit(1)
    return token


def fetch_clan_members(clan_tag: str, headers: dict) -> list:
    """Busca membros de um clã."""
    clean_tag = clan_tag.replace('#', '').strip()
    url = f"https://proxy.royaleapi.dev/v1/clans/%23{clean_tag}/members"
    try:
        resp = requests.get(url, headers=headers, params={'limit': 50}, timeout=15)
        resp.raise_for_status()
        return resp.json().get('items', [])
    except Exception as e:
        print(f"  [WARN] Falha ao buscar membros do clã {clan_tag}: {e}")
        return []


def get_top_players_from_clans(headers: dict, limit_clans: int = 100) -> list:
    """Busca top players a partir do ranking de clãs."""
    all_players = []
    seen_tags = set()

    for region_name, loc_id in [('Global', 'global'), ('Brasil', '57000038')]:
        print(f"\n[INFO] Buscando top {limit_clans} clãs {region_name}...")
        url = f"https://proxy.royaleapi.dev/v1/locations/{loc_id}/rankings/clans"
        try:
            resp = requests.get(url, headers=headers, params={'limit': limit_clans}, timeout=15)
            resp.raise_for_status()
            clans = resp.json().get('items', [])
            print(f"  {len(clans)} clãs retornados")

            for i, clan in enumerate(clans):
                clan_tag = clan.get('tag', '')
                clan_name = clan.get('name', '?')
                if not clan_tag:
                    continue

                members = fetch_clan_members(clan_tag, headers)
                if not members:
                    continue

                # Pegar o jogador com mais troféus do clã
                best = max(members, key=lambda x: x.get('trophies', 0))
                p_tag = best.get('tag', '')
                p_name = best.get('name', '?')

                if p_tag and p_tag not in seen_tags:
                    seen_tags.add(p_tag)
                    all_players.append({
                        'tag': p_tag,
                        'name': p_name,
                        'trophies': best.get('trophies', 0),
                        'clan_name': clan_name,
                        'clan_tag': clan_tag,
                        'source_type': f'{region_name} Meta',
                    })
                    if len(all_players) % 20 == 0:
                        print(f"  ... {len(all_players)} jogadores únicos até agora")

                # Limitar a 100 jogadores por região
                region_count = sum(1 for p in all_players if region_name in p.get('source_type', ''))
                if region_count >= limit_clans:
                    break

        except Exception as e:
            print(f"  [ERRO] Falha ao buscar ranking {region_name}: {e}")

    return all_players


def fetch_battlelog(api_token: str, player_tag: str) -> list:
    """Busca battlelog de um jogador."""
    clean_tag = player_tag.strip().replace('#', '').upper()
    url = f"https://proxy.royaleapi.dev/v1/players/%23{clean_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [WARN] Falha ao buscar battlelog de {player_tag}: {e}")
        return []


def parse_battle_time(bt_str: str):
    try:
        if bt_str and len(bt_str) >= 15:
            return datetime.strptime(bt_str[:15], '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    return None


def format_deck(cards: list) -> str:
    if not cards:
        return ''
    return ' | '.join(c.get('name', '') for c in cards)


def canonical_deck(deck_str: str) -> str:
    """Normaliza o deck para comparação (ordem alfabética)."""
    if not deck_str:
        return ''
    cards = [c.strip() for c in deck_str.split('|') if c.strip()]
    return ' | '.join(sorted(cards))


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


def extract_challenge_battle(battle: dict, player_tag: str, player_info: dict) -> dict:
    """Extrai dados de uma batalha de desafio."""
    search_tag = player_tag.strip().upper()
    if not search_tag.startswith('#'):
        search_tag = f"#{search_tag}"

    teams = battle.get('team', [])
    player_team = next((t for t in teams if t.get('tag', '').strip().upper() == search_tag), None)
    if not player_team:
        alt = search_tag.replace('#', '')
        player_team = next((t for t in teams if t.get('tag', '').strip().upper().lstrip('#') == alt), None)
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

    deck_raw = 'Aleatório'
    deck_canonical = 'Aleatório'
    semana_iso = get_week_iso(dt_utc)

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
        'tipo_desafio': game_mode,
        'source_type': player_info.get('source_type', 'Global Meta'),
        'deck_key': deck_canonical,
        'jogador_nome': player_info.get('name', '?'),
    }


def aggregate_battles(all_battles: list) -> list:
    """Agrega batalhas por deck_key + tipo_desafio + semana_iso.
    Para cada grupo:
    - Soma wins, losses, draws, total
    - Calcula win_rate média
    - Coleta tags únicas dos jogadores
    - Usa os dados da batalha mais recente para campos descritivos
    """
    groups = defaultdict(lambda: {
        'wins': 0, 'losses': 0, 'draws': 0, 'total': 0,
        'jogador_tags': set(), 'jogador_nomes': set(),
        'elixir_medio': [], 'nivel_medio': [],
        'latest_battle': None,
        'decks_raw': set(),  # decks na ordem original
    })

    for battle in all_battles:
        key = (
            battle.get('deck_key', ''),
            battle.get('tipo_desafio', ''),
            battle.get('semana_iso', ''),
            battle.get('source_type', ''),
        )

        g = groups[key]
        resultado = battle.get('resultado', '')
        if resultado == 'Vitoria':
            g['wins'] += 1
        elif resultado == 'Derrota':
            g['losses'] += 1
        else:
            g['draws'] += 1
        g['total'] += 1

        g['jogador_tags'].add(battle.get('player_tag', ''))
        g['jogador_nomes'].add(battle.get('jogador_nome', ''))
        g['elixir_medio'].append(battle.get('elixir_medio_jogador', 0))
        g['nivel_medio'].append(battle.get('nivel_medio_deck_jogador', 0))
        g['decks_raw'].add(battle.get('deck_jogador', ''))

        # Manter a batalha mais recente para campos descritivos
        if not g['latest_battle']:
            g['latest_battle'] = battle
        else:
            dt_curr = battle.get('data', '')
            dt_latest = g['latest_battle'].get('data', '')
            if dt_curr > dt_latest:
                g['latest_battle'] = battle

    # Converter grupos em linhas de CSV
    rows = []
    for (deck_key, tipo_desafio, semana_iso, source_type), g in groups.items():
        b = g['latest_battle']
        total = g['total']
        win_rate = round(g['wins'] / total * 100, 1) if total > 0 else 0
        avg_elixir = round(sum(g['elixir_medio']) / len(g['elixir_medio']), 2) if g['elixir_medio'] else 0
        avg_nivel = round(sum(g['nivel_medio']) / len(g['nivel_medio']), 2) if g['nivel_medio'] else 0

        rows.append({
            'player_tag': ','.join(sorted(g['jogador_tags'])),
            'data': b.get('data', ''),
            'nome_oponente': b.get('nome_oponente', ''),
            'tag_oponente': b.get('tag_oponente', ''),
            'nivel_oponente': b.get('nivel_oponente', 0),
            'trofes_oponente': b.get('trofes_oponente', 0),
            'clan_oponente': b.get('clan_oponente', ''),
            'resultado': f"{g['wins']}V/{g['losses']}D/{g['draws']}E",
            'coroas_jogador': 0,
            'coroas_oponente': 0,
            'mudanca_trofes': 0,
            'modo_jogo': tipo_desafio,
            'tipo_batalha': b.get('tipo_batalha', ''),
            'arena': b.get('arena', ''),
            'deck_jogador': deck_key,  # deck canônico (ordem alfabética)
            'deck_oponente': '',
            'elixir_vazado_jogador': 0,
            'elixir_vazado_oponente': 0,
            'nivel_torre_jogador': b.get('nivel_torre_jogador', 0),
            'vida_torre_rei_jogador': 0,
            'vida_torre_rei_oponente': 0,
            'torre_jogador': 'Tower Princess',
            'torre_oponente': 'Tower Princess',
            'elixir_medio_jogador': avg_elixir,
            'elixir_medio_oponente': 0,
            'nivel_medio_deck_jogador': avg_nivel,
            'nivel_medio_deck_oponente': 0,
            'tag_clan_oponente': '',
            'semana_iso': semana_iso,
            'tipo_desafio': tipo_desafio,
            'source_type': source_type,
            'deck_key': deck_key,
            'jogador_tags': ','.join(sorted(g['jogador_tags'])),
            'total_jogadores': len(g['jogador_tags']),
        })

    return rows


def load_processed() -> set:
    if os.path.exists(PROCESSED_JSON):
        try:
            with open(PROCESSED_JSON, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            pass
    return set()


def save_processed(processed: set):
    try:
        data = list(processed)[-10000:]
        with open(PROCESSED_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Falha ao salvar processed: {e}")


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    api_token = get_api_token()
    headers = {"Authorization": f"Bearer {api_token}"}
    os.makedirs(DATA_DIR, exist_ok=True)

    # Carregar batalhas já processadas (por battleTime)
    processed = load_processed()
    print(f"[INFO] Batalhas ja processadas: {len(processed)}")

    # 1. Buscar top 100 players
    print("\n" + "=" * 60)
    print("FASE 1: Buscando top 100 players globais + Brasil")
    print("=" * 60)
    top_players = get_top_players_from_clans(headers, limit_clans=100)
    print(f"\n[INFO] Total de jogadores únicos: {len(top_players)}")

    if not top_players:
        print("[ERRO] Nenhum jogador encontrado.")
        sys.exit(1)

    # 2. Coletar batalhas de desafio
    print("\n" + "=" * 60)
    print("FASE 2: Coletando batalhas de desafio")
    print("=" * 60)

    all_battles = []
    for i, player in enumerate(top_players, 1):
        p_tag = player['tag']
        p_name = player['name']
        p_source = player['source_type']
        trophies = player.get('trophies', 0)

        p_name_safe = sanitize(p_name)
        print(f"[{i:3d}/{len(top_players)}] {p_name_safe} ({p_tag}) | {trophies} troféus | {p_source}")

        battles = fetch_battlelog(api_token, p_tag)
        if not battles:
            continue

        count = 0
        for battle in battles:
            bt = battle.get('battleTime', '')
            if bt in processed:
                continue

            row = extract_challenge_battle(battle, p_tag, player)
            if row:
                all_battles.append(row)
                count += 1

            processed.add(bt)  # Marcar como processado (mesmo se não for desafio)

        if count > 0:
            print(f"  -> {count} batalhas de desafio")

    print(f"\n[INFO] Total de batalhas de desafio coletadas: {len(all_battles)}")

    if not all_battles:
        print("[AVISO] Nenhuma batalha de desafio encontrada.")
        return

    # 3. Agregar por deck
    print("\n" + "=" * 60)
    print("FASE 3: Agregando decks repetidos")
    print("=" * 60)
    aggregated = aggregate_battles(all_battles)
    print(f"[INFO] Decks únicos após agregação: {len(aggregated)}")

    # Ordenar por win_rate decrescente
    aggregated.sort(key=lambda r: (
        r.get('tipo_desafio', ''),
        -int(r.get('resultado', '0V').split('V')[0]) / max(r.get('total_jogadores', 1), 1),
    ))

    # 4. Salvar no CSV
    csv_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, 'a' if csv_exists else 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';', extrasaction='ignore')
        if not csv_exists or os.path.getsize(OUTPUT_CSV) == 0:
            writer.writeheader()
        for row in aggregated:
            writer.writerow(row)

    # Salvar batalhas processadas
    save_processed(processed)

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Jogadores analisados: {len(top_players)}")
    print(f"Batalhas de desafio: {len(all_battles)}")
    print(f"Decks únicos: {len(aggregated)}")

    # Por tipo de desafio
    from collections import Counter
    by_type = Counter(r.get('tipo_desafio', '?') for r in aggregated)
    print(f"\nDecks por tipo de desafio:")
    for tipo, cnt in by_type.most_common():
        print(f"  {cnt:3d} | {tipo}")

    # Top 10 decks
    print(f"\nTop 10 decks (por mais jogadores usando):")
    aggregated_by_players = sorted(aggregated, key=lambda r: -r.get('total_jogadores', 0))
    for r in aggregated_by_players[:10]:
        deck_short = r.get('deck_jogador', '')[:60]
        n_jog = r.get('total_jogadores', 0)
        result = r.get('resultado', '?')
        tipo = r.get('tipo_desafio', '?')
        print(f"  {n_jog} jogadores | {result} | {tipo} | {deck_short}...")

    print(f"\n[OK] Dados salvos em {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
