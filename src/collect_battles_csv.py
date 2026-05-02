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
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador',
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente', 
    'vida_torres_princesa_jogador', 'vida_torres_princesa_oponente',
    'trofes_iniciais_jogador', 'trofes_finais_jogador',
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente'
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')


def get_battle_log(api_token: str, player_tag: str):
    """Busca o historico de batalhas da API Clash Royale."""
    clean_tag = player_tag.replace('#', '')
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
        print(f"[ERRO] Falha ao buscar batalhas: {e}")
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
    """Formata lista de cartas como string separada por ' | '."""
    if not cards:
        return ''
    return ' | '.join(sorted(card.get('name', '') for card in cards))


def extract_battle_row(battle: dict, player_tag: str):
    """Extrai dados de uma batalha no formato do CSV oficial. Retorna None se invalido."""
    teams = battle.get('team', [])
    player_team = next((t for t in teams if t.get('tag') == player_tag), None)
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

    return {
        '_dt_utc': dt_utc,  # campo interno, removido antes de salvar
        'data': format_date_brt(dt_utc),
        'nome_oponente': opponent_team.get('name', 'Desconhecido'),
        'tag_oponente': opponent_team.get('tag', ''),
        'nivel_oponente': opponent_team.get('expLevel', 0),
        'trofes_oponente': opponent_team.get('startingTrophies', 0),
        'clan_oponente': opponent_team.get('clan', {}).get('name', 'Sem cla'),
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
        'nivel_torre_oponente': opponent_team.get('expLevel', 0)
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
    """Chave de deduplicacao: (data, tag_oponente)."""
    return (
        str(row.get('data', '')).strip(),
        str(row.get('tag_oponente', '')).strip().upper()
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


def main():
    api_token = os.environ.get('CR_API_TOKEN')
    player_tag = os.environ.get('CR_PLAYER_TAG')

    if not api_token:
        print("[ERRO] Variavel de ambiente CR_API_TOKEN nao configurada.")
        sys.exit(1)
    if not player_tag:
        print("[ERRO] Variavel de ambiente CR_PLAYER_TAG nao configurada.")
        sys.exit(1)

    print("=" * 60)
    print("Coleta de Batalhas - Clash Royale (100% CSV)")
    print("=" * 60)
    print(f"Jogador: {player_tag}")
    print(f"Data/Hora UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    battles = get_battle_log(api_token, player_tag)
    if not battles:
        print("[AVISO] Nenhuma batalha retornada pela API.")
        sys.exit(0)

    print(f"Batalhas retornadas pela API: {len(battles)}")

    # Parseia todas as batalhas validas
    parsed = []
    for battle in battles:
        row = extract_battle_row(battle, player_tag)
        if row:
            parsed.append(row)

    print(f"Batalhas parseadas com sucesso: {len(parsed)}")

    if not parsed:
        print("[AVISO] Nenhuma batalha valida para salvar.")
        sys.exit(0)

    # Agrupa por periodo (dia, mes, ano) usando a data BRT
    by_day = {}
    by_month = {}
    by_year = {}

    for row in parsed:
        dt_utc = row.pop('_dt_utc')  # Remove campo interno antes de salvar
        dt_brt = dt_utc - timedelta(hours=3)
        day_key = dt_brt.strftime('%Y%m%d')
        month_key = dt_brt.strftime('%Y%m')
        year_key = dt_brt.strftime('%Y')
        by_year.setdefault(year_key, []).append(row)

    # Processa apenas o arquivo anual consolidado (Ano atual)
    total_novos = 0
    print("\n--- Processando Arquivo Anual Consolidado ---")
    for year_key, rows in sorted(by_year.items()):
        file_path = os.path.join(DATA_DIR, f"oponentes_ano_{year_key}.csv")
        novos = append_new_rows(file_path, rows)
        total_novos += novos
        print(f"  oponentes_ano_{year_key}.csv: +{novos} novas batalhas")

    print("\n" + "=" * 60)
    print(f"Coleta concluida! Total de novas batalhas: {total_novos}")
    print("=" * 60)

    if total_novos == 0:
        print("[INFO] Nenhuma batalha nova nesta coleta (todas ja existem nos CSVs).")


if __name__ == "__main__":
    main()
