#!/usr/bin/env python3
"""
Coleta batalhas da API Clash Royale e salva diretamente nos CSVs oficiais.
Sem banco de dados - 100% CSV puro.
"""

import os
import sys
import csv
import requests
from datetime import datetime, timedelta
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

FIELDNAMES = [
    'player_tag',
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador',
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente', 
    'vida_torres_princesa_jogador', 'vida_torres_princesa_oponente',
    'trofes_iniciais_jogador', 'trofes_finais_jogador',
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente',
    'torre_jogador', 'torre_oponente'
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')


def get_battle_log(api_token: str, player_tag: str):
    """Busca o historico de batalhas da API Clash Royale."""
    # Garante tag limpa para a URL
    clean_tag = player_tag.strip().replace('#', '').upper()
    url = f"https://proxy.royaleapi.dev/v1/players/%23{clean_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            print(f"[AVISO] Jogador {player_tag} nao encontrado (404).")
            return None
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[ERRO] Falha ao buscar batalhas para {player_tag}: {e}")
        return None


def parse_battle_time(battle_time_str: str):
    """Parseia battleTime da API (20260429T230000.000Z) para datetime UTC."""
    try:
        if len(battle_time_str) >= 15:
            return datetime.strptime(battle_time_str[:15], '%Y%m%dT%H%M%S')
    except (ValueError, TypeError):
        pass
    return None


def format_date_brt(dt_utc: datetime) -> str:
    """Converte datetime UTC para string BRT (DD/MM/YYYY HH:MM)."""
    return (dt_utc - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')


def format_deck(cards: list) -> str:
    """Formata lista de cartas como string separada por ' | ' na ordem original da API."""
    if not cards:
        return ''
    return ' | '.join(card.get('name', '') for card in cards)


def extract_battle_row(battle: dict, player_tag: str):
    """Extrai dados de uma batalha no formato do CSV oficial. Retorna None se invalido."""
    # Normaliza a tag para comparacao
    search_tag = player_tag.strip().upper()
    if not search_tag.startswith('#'):
        search_tag = f"#{search_tag}"

    teams = battle.get('team', [])
    # Comparacao insensivel a caso e espacos
    player_team = next((t for t in teams if t.get('tag', '').strip().upper() == search_tag), None)
    
    if not player_team:
        # Tenta sem o # caso a API retorne diferente (raro)
        alt_tag = search_tag.replace('#', '')
        player_team = next((t for t in teams if t.get('tag', '').strip().upper() == alt_tag), None)
        
    if not player_team:
        return None

    opponents = battle.get('opponent', [])
    opponent_team = opponents[0] if opponents else None
    if not opponent_team:
        return None

    player_crowns = player_team.get('crowns', 0)
    opponent_crowns = opponent_team.get('crowns', 0)

    if player_crowns > opponent_crowns:
        resultado = 'Vitoria'
    elif player_crowns < opponent_crowns:
        resultado = 'Derrota'
    else:
        resultado = 'Empate'

    dt_utc = parse_battle_time(battle.get('battleTime', ''))
    if not dt_utc:
        return None

    # Formata vida das torres como string (ex: "4000 | 4000" ou apenas "4000")
    def format_hp(hp_list):
        if hp_list is None: return "0"
        if isinstance(hp_list, int): return str(hp_list)
        return " | ".join(map(str, hp_list))

    trophy_change = player_team.get('trophyChange', 0)
    starting_trophies = player_team.get('startingTrophies', 0)

    def sanitize(text):
        if not text: return ""
        return str(text).replace(';', '-')

    # Logica de Torres: Antes de 07/05/2026 = Tower Princess, Depois = API (fallback Tower Princess)
    data_limite = datetime(2026, 5, 7)
    
    def get_tower_name(team_data, battle_dt):
        if battle_dt < data_limite:
            return 'Tower Princess'
        
        # Tenta extrair do supportCards
        support = team_data.get('supportCards', [])
        if support and isinstance(support, list) and len(support) > 0:
            return support[0].get('name', 'Tower Princess')
        
        return 'Tower Princess'

    return {
        '_dt_utc': dt_utc,  # campo interno, removido antes de salvar
        'player_tag': search_tag,
        'data': format_date_brt(dt_utc),
        'nome_oponente': sanitize(opponent_team.get('name', 'Desconhecido')),
        'tag_oponente': opponent_team.get('tag', ''),
        'nivel_oponente': opponent_team.get('expLevel', 0),
        'trofes_oponente': opponent_team.get('startingTrophies', 0),
        'clan_oponente': sanitize(opponent_team.get('clan', {}).get('name', 'Sem cla')),
        'resultado': resultado,
        'coroas_jogador': player_crowns,
        'coroas_oponente': opponent_crowns,
        'mudanca_trofes': trophy_change,
        'modo_jogo': battle.get('gameMode', {}).get('name', 'Desconhecido'),
        'tipo_batalha': battle.get('type', 'Desconhecido'),
        'arena': battle.get('arena', {}).get('name', 'Desconhecido'),
        'deck_jogador': format_deck(player_team.get('cards', [])),
        'deck_oponente': format_deck(opponent_team.get('cards', [])),
        'vezes_enfrentado': 1,
        'elixir_vazado_jogador': round(player_team.get('elixirLeaked', 0), 2),
        'elixir_vazado_oponente': round(opponent_team.get('elixirLeaked', 0), 2),
        'nivel_torre_jogador': player_team.get('expLevel', 0),
        'vida_torre_rei_jogador': player_team.get('kingTowerHitPoints', 0),
        'vida_torre_rei_oponente': opponent_team.get('kingTowerHitPoints', 0),
        'vida_torres_princesa_jogador': format_hp(player_team.get('princessTowersHitPoints')),
        'vida_torres_princesa_oponente': format_hp(opponent_team.get('princessTowersHitPoints')),
        'trofes_iniciais_jogador': starting_trophies,
        'trofes_finais_jogador': starting_trophies + trophy_change,
        'posicao_global_jogador': player_team.get('globalRank', 'N/A') or 'N/A',
        'posicao_global_oponente': opponent_team.get('globalRank', 'N/A') or 'N/A',
        'nivel_torre_oponente': opponent_team.get('expLevel', 0),
        'torre_jogador': get_tower_name(player_team, dt_utc),
        'torre_oponente': get_tower_name(opponent_team, dt_utc)
    }


def read_csv(file_path: str) -> list:
    """Le um CSV existente e retorna lista de dicts validos."""
    if not os.path.exists(file_path):
        return []
    try:
        rows = []
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                # Valida se a linha tem o minimo de dados (Data e Oponente)
                if row.get('data') and row.get('tag_oponente'):
                    rows.append(row)
        return rows
    except Exception as e:
        print(f"[ERRO CRITICO] Falha ao ler {file_path}: {e}")
        # Retorna None para sinalizar falha na leitura e evitar sobrescrita
        return None


def write_csv(file_path: str, rows: list):
    """Escreve lista de dicts em CSV oficial."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def make_dedup_key(row: dict) -> tuple:
    """Chave de deduplicacao: (player_tag, data, tag_oponente, deck_jogador, deck_oponente)."""
    return (
        str(row.get('player_tag', '')).strip().upper(),
        str(row.get('data', '')).strip(),
        str(row.get('tag_oponente', '')).strip().upper(),
        str(row.get('deck_jogador', '')).strip(),
        str(row.get('deck_oponente', '')).strip()
    )


def parse_date_for_sort(date_str: str) -> datetime:
    """Parseia data BRT para ordenacao."""
    for fmt in ['%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S']:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.min


def recalculate_vezes_enfrentado(rows: list) -> list:
    """Recalcula vezes_enfrentado baseado no historico completo do arquivo."""
    counts = Counter(str(r.get('tag_oponente', '')).strip().upper() for r in rows)
    for row in rows:
        tag = str(row.get('tag_oponente', '')).strip().upper()
        row['vezes_enfrentado'] = counts.get(tag, 1)
    return rows


def append_new_rows(file_path: str, new_rows: list) -> int:
    """
    Adiciona linhas novas ao CSV deduplicando por (data, tag_oponente).
    Retorna o numero de registros novos inseridos.
    """
    existing = read_csv(file_path)
    
    # Se existing for None, houve erro na leitura. Nao podemos prosseguir para nao apagar dados.
    if existing is None:
        print(f"[ERRO] Abortando atualizacao de {file_path} para preservar dados existentes.")
        return 0
        
    existing_keys = {make_dedup_key(r) for r in existing}

    added = []
    for row in new_rows:
        key = make_dedup_key(row)
        if key not in existing_keys:
            existing_keys.add(key)
            added.append(row)

    if not added:
        return 0

    all_rows = existing + added
    all_rows = recalculate_vezes_enfrentado(all_rows)
    all_rows.sort(key=lambda r: parse_date_for_sort(r.get('data', '')), reverse=True)
    write_csv(file_path, all_rows)
    return len(added)


def collect_for_tag(api_token: str, player_tag: str, label: str = "Principal") -> int:
    """Coleta batalhas de uma unica conta e salva no CSV anual.
    Retorna o numero total de novas batalhas inseridas."""
    print(f"\n{'-' * 50}")
    print(f"  Conta {label}: {player_tag}")
    print(f"{'-' * 50}")

    battles = get_battle_log(api_token, player_tag)
    if not battles:
        print(f"  [AVISO] Nenhuma batalha retornada pela API para {player_tag}.")
        return 0

    print(f"  Batalhas retornadas pela API: {len(battles)}")

    # Parseia todas as batalhas validas
    parsed = []
    for battle in battles:
        row = extract_battle_row(battle, player_tag)
        if row:
            parsed.append(row)

    print(f"  Batalhas parseadas com sucesso: {len(parsed)}")

    if not parsed:
        print(f"  [AVISO] Nenhuma batalha valida para salvar.")
        return 0

    # Agrupa por ano usando a data BRT
    by_year = {}
    for row in parsed:
        dt_utc = row.pop('_dt_utc')  # Remove campo interno antes de salvar
        dt_brt = dt_utc - timedelta(hours=3)
        year_key = dt_brt.strftime('%Y')
        by_year.setdefault(year_key, []).append(row)

    # Processa arquivo anual consolidado
    total_novos = 0
    for year_key, rows in sorted(by_year.items()):
        file_path = os.path.join(DATA_DIR, f"oponentes_ano_{year_key}.csv")
        novos = append_new_rows(file_path, rows)
        total_novos += novos
        print(f"  oponentes_ano_{year_key}.csv: +{novos} novas batalhas")

    return total_novos


def main():
    api_token = os.environ.get('CR_API_TOKEN')
    player_tag = os.environ.get('CR_PLAYER_TAG')
    player_tag_sec = os.environ.get('CR_PLAYER_TAG_SEC')

    if not api_token:
        print("[ERRO] Variavel de ambiente CR_API_TOKEN nao configurada.")
        sys.exit(1)
    if not player_tag:
        print("[ERRO] Variavel de ambiente CR_PLAYER_TAG nao configurada.")
        sys.exit(1)

    # Monta lista de contas para coletar
    accounts = []
    if player_tag:
        accounts.append(("Principal", player_tag.strip().upper()))
    
    if player_tag_sec:
        tag_sec = player_tag_sec.strip().upper()
        if tag_sec and tag_sec != "NONE" and tag_sec != "":
            accounts.append(("Secundaria", tag_sec))

    if not accounts:
        print("[ERRO] Nenhuma conta configurada (CR_PLAYER_TAG / CR_PLAYER_TAG_SEC).")
        sys.exit(1)

    print("=" * 60)
    print("Coleta de Batalhas - Clash Royale (100% CSV)")
    print("=" * 60)
    print(f"Data/Hora UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Contas detectadas: {len(accounts)}")
    for label, tag in accounts:
        print(f"  [{label}] {tag}")
    sys.stdout.flush()

    # Coleta para cada conta
    grand_total = 0
    for label, tag in accounts:
        novos = collect_for_tag(api_token, tag, label)
        grand_total += novos

    print("\n" + "=" * 60)
    print(f"Coleta concluida! Total de novas batalhas: {grand_total}")
    print("=" * 60)
    sys.stdout.flush()

    if grand_total == 0:
        print("[INFO] Nenhuma batalha nova nesta coleta (todas ja existem nos CSVs).")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
