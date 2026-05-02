#!/usr/bin/env python3
"""
HTML Report Generator for GitHub Pages
Generates Clash Royale analytics with relative paths for GitHub Pages
"""

import os
import re
import requests
import time
import csv
import glob
import logging
import json
import sqlite3
from datetime import datetime, timezone, timedelta
try:
    from datetime import UTC
except ImportError:
    # Python < 3.11 compatibility
    UTC = timezone.utc
from typing import List, Dict, Optional
from csv_database_manager import CSVDatabaseManager

logger = logging.getLogger(__name__)

class GitHubPagesHTMLGenerator:
    def __init__(self, db_path: str = None):
        self.src_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.src_dir)
        self.data_csv_dir = os.path.join(self.src_dir, "data_csv_oficial")

        # Inicializa o gerenciador de CSV e carrega os dados para a memoria
        self.csv_manager = CSVDatabaseManager()
        self.csv_manager.load_all_csvs()
        
        # Define o path como a URI de memoria compartilhada
        self.db_path = self.csv_manager.db_path
        logger.info(f"DEBUG: Banco de dados em memoria (CSV-First) configurado")
        self.base_url = "https://proxy.royaleapi.dev/v1"
        self.api_token = os.getenv("CR_API_TOKEN")
        self.headers = None
        if self.api_token:
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        
        self.player_tag = os.getenv('CR_PLAYER_TAG', '#2QR292P')
        self.failed_tags = set()
        # Caches carregados diretamente do CSV (ignora SQL)
        self.battles_cache = self._load_all_battles_from_csv(self.player_tag)
        self.clan_members_cache = self._load_clan_members_csv()
        self.rankings_history_cache = [] # Arquivo removido por redundancia
        self.clan_decks_cache = []       # Arquivo removido por redundancia
        self.players_cache = self._load_csv_as_list('players.csv')
        self.card_name_mapping = self._get_card_name_mapping()
        self.cards_master = self._load_cards_master_csv()
        
    def _load_csv_as_list(self, filename: str) -> List[Dict]:
        """Auxiliar para carregar qualquer CSV da pasta oficial como lista de dicts"""
        path = os.path.join(self.data_csv_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Aviso: {path} não encontrado")
            return []
        try:
            with open(path, mode='r', encoding='utf-8') as f:
                return list(csv.DictReader(f))
        except Exception as e:
            logger.error(f"Erro ao ler {filename}: {e}")
            return []

    def _load_clan_members_csv(self) -> List[Dict]:
        """Lê clan_members.csv diretamente"""
        return self._load_csv_as_list('clan_members.csv')

    def _load_cards_master_csv(self) -> Dict[str, Dict]:
        """Lê cards_master_icons.csv e retorna um dicionario indexado pelo nome da carta"""
        path = os.path.join(self.data_csv_dir, 'cards_master_icons.csv')
        master = {}
        if not os.path.exists(path):
            return master
        try:
            with open(path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    master[row['card_name']] = row
            logger.info(f"Mestre de {len(master)} icones carregado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao ler cards_master_icons.csv: {e}")
        return master

    def _load_all_battles_from_csv(self, player_tag: str = None) -> List[Dict]:
        """Loads all battles from the consolidated CSV file for a specific player tag"""
        if not player_tag:
            player_tag = self.player_tag
        """Lê todos os CSVs de batalha e unifica em uma lista, com deduplicação rigorosa"""
        battles_dict = {}
        # Carrega apenas arquivos particionados (ano, mes, semana, dia)
        # Ignora battles.csv, oponentes_todos.csv e oponentes_batalhas.csv que são redundantes
        pattern = os.path.join(self.data_csv_dir, 'oponentes_*.csv')
        all_files = glob.glob(pattern)
        
        # Filtra para evitar arquivos que sabidamente contêm dados duplicados de forma massiva
        files = []
        ignored_files = ['oponentes_todos.csv', 'oponentes_batalhas.csv', 'battles.csv']
        for f in all_files:
            basename = os.path.basename(f)
            if basename not in ignored_files:
                files.append(f)
            
        logger.info(f"Lendo {len(files)} arquivos CSV de batalha para o player {player_tag}...")
        
        for file in files:
            try:
                # Usa encoding latin1 para lidar com nomes com acento se utf-8 falhar
                data = []
                for encoding in ['utf-8-sig', 'utf-8', 'latin1']:
                    try:
                        with open(file, mode='r', encoding=encoding) as f:
                            reader = csv.DictReader(f)
                            # Se o arquivo tiver delimitador diferente (ex: ;), tenta detectar
                            if reader.fieldnames and len(reader.fieldnames) == 1 and ';' in reader.fieldnames[0]:
                                f.seek(0)
                                reader = csv.DictReader(f, delimiter=';')
                            data = list(reader)
                        if data: break
                    except:
                        continue
                if not data:
                    continue

                for row in data:
                    # Filtro de player_tag
                    row_tag = row.get('player_tag') or player_tag
                    if row_tag and row_tag != player_tag:
                        continue
                            
                    # Normaliza campos
                    raw_battle_time = row.get('data') or row.get('battle_time') or ''
                    # Obtém datetime real para comparação fuzzy
                    b_time_str = self._normalize_battle_time(raw_battle_time)
                    try:
                        if b_time_str.endswith('Z'):
                            b_time = datetime.strptime(b_time_str, '%Y-%m-%dT%H:%M:%SZ')
                        else:
                            b_time = datetime.strptime(b_time_str, '%Y-%m-%dT%H:%M:%S')
                    except:
                        b_time = datetime.min
                    
                    # Normaliza resultado
                    res = str(row.get('resultado') or row.get('result') or '').strip().lower()
                    norm_res = 'unknown'
                    if any(x in res for x in ['vitoria', 'victory', 'vitória']):
                        norm_res = 'victory'
                    elif any(x in res for x in ['derrota', 'defeat']):
                        norm_res = 'defeat'
                    elif any(x in res for x in ['empate', 'draw']):
                        norm_res = 'draw'
                    
                    # Tenta inferir pelas coroas (sempre, para confirmar ou preencher unknown)
                    try:
                        cp = int(row.get('coroas_jogador', row.get('crowns', 0)) or 0)
                        co = int(row.get('coroas_oponente', row.get('opponent_crowns', 0)) or 0)
                        if norm_res == 'unknown':
                            if cp > co: norm_res = 'victory'
                            elif cp < co: norm_res = 'defeat'
                            else: norm_res = 'draw'
                    except:
                        pass

                    opp_tag = str(row.get('tag_oponente') or row.get('opponent_tag') or '').strip().upper()
                    
                    # Extração e normalização básica de campos
                    opp_name = row.get('nome_oponente', row.get('oponente', row.get('opponent_name', 'Oponente')))
                    crowns = row.get('coroas_jogador', row.get('coroas', row.get('crowns', '0')))
                    opp_crowns = row.get('coroas_oponente', row.get('opponent_crowns', '0'))
                    
                    # Validação de Tag/Nome para evitar oponentes "fantasmas"
                    if not opp_tag or len(opp_tag) < 3 or opp_tag.startswith('<<<') or ' ' in opp_tag:
                        if not opp_name or opp_name in ['Oponente', 'Unknown', 'Desconhecido'] or opp_name.startswith('<<<'):
                            continue
                    
                    # Chave de deduplicação e Lógica Fuzzy
                    opp_identifier = opp_tag if opp_tag and not opp_tag.startswith('<<<') else str(opp_name or 'Unknown')
                    
                    is_duplicate = False
                    # Procura se já carregamos essa partida (fuzzy timing: 2 min)
                    for existing_key, existing_battle in battles_dict.items():
                        existing_time, existing_opp = existing_key
                        if existing_opp == opp_identifier:
                            time_diff = abs((b_time - existing_time).total_seconds()) / 60.0
                            if time_diff <= 2:
                                # Verifica se os dados principais batem
                                if existing_battle.get('result') == norm_res and \
                                   str(existing_battle.get('crowns')) == str(crowns) and \
                                   str(existing_battle.get('opponent_crowns')) == str(opp_crowns):
                                    is_duplicate = True
                                    break
                    
                    if is_duplicate:
                        continue
                    
                    dedup_key = (b_time, opp_identifier)
                    
                    opp_name = row.get('nome_oponente', row.get('oponente', row.get('opponent_name', 'Oponente')))
                    crowns = row.get('coroas_jogador', row.get('coroas', row.get('crowns', '0')))
                    arena = row.get('arena', row.get('arena_name', 'Arena'))
                    deck_p = row.get('deck_jogador', row.get('deck_cards', ''))
                    deck_o = row.get('deck_oponente', row.get('opponent_deck_cards', ''))
                    clan_o = row.get('clan_oponente', row.get('cla_oponente', row.get('opponent_clan_name', '')))
                    opp_trophies = row.get('trofes_oponente', row.get('opponent_trophies', '0'))
                    
                    # Níveis de cartas (se houver)
                    levels_p = row.get('deck_card_levels', '')
                    levels_o = row.get('opponent_deck_card_levels', '')
                    p_level = row.get('player_level', row.get('nivel_jogador', '0'))
                    o_level = row.get('opponent_level', row.get('nivel_oponente', '0'))
                    
                    try:
                        t_change = int(row.get('mudanca_trofes', row.get('trophy_change', 0)) or 0)
                    except:
                        t_change = 0
                        
                    # Extrai coroas do oponente (campo do CSV de batalha)
                    opp_crowns_val = row.get('coroas_oponente', row.get('opponent_crowns', '0'))
                    player_crowns_val = row.get('coroas_jogador', row.get('coroas', row.get('crowns', '0')))
                    game_mode_val = row.get('modo_jogo', row.get('game_mode', row.get('mode', 'Desconhecido')))
                    
                    battle_obj = {
                        'battle_time': b_time_str, # Mantém string para compatibilidade
                        '_dt': b_time,             # Campo interno para ordenação
                        'result': norm_res,
                        'player_tag': row_tag,
                        'opponent_name': opp_name,
                        'opponent_tag': opp_tag,
                        'crowns': player_crowns_val,
                        'opponent_crowns': opp_crowns_val,
                        'arena_name': arena,
                        'deck_cards': deck_p,
                        'deck_card_levels': levels_p,
                        'player_level': self._safe_int(p_level, 0),
                        'opponent_deck_cards': deck_o,
                        'opponent_deck_card_levels': levels_o,
                        'opponent_level': self._safe_int(o_level, 0),
                        'opponent_clan_name': clan_o,
                        'opponent_trophies': self._safe_int(opp_trophies, 0),
                        'trophy_change': t_change,
                        'game_mode': game_mode_val,
                        # Novos campos premium
                        'elixir_vazado_jogador': row.get('elixir_vazado_jogador', '0'),
                        'elixir_vazado_oponente': row.get('elixir_vazado_oponente', '0'),
                        'vida_torre_rei_jogador': row.get('vida_torre_rei_jogador', '0'),
                        'vida_torre_rei_oponente': row.get('vida_torre_rei_oponente', '0'),
                        'vida_torres_princesa_jogador': row.get('vida_torres_princesa_jogador', '0'),
                        'vida_torres_princesa_oponente': row.get('vida_torres_princesa_oponente', '0')
                    }
                    
                    battles_dict[dedup_key] = battle_obj
            except Exception as e:
                logger.error(f"Erro ao processar {file}: {e}")
        
        # Converte o dicionário de volta para lista e ordena por tempo
        final_battles = list(battles_dict.values())
        final_battles.sort(key=lambda x: x.get('_dt', datetime.min), reverse=True)
        
        logger.info(f"Total de batalhas únicas carregadas: {len(final_battles)}")
        return final_battles

    def _get_canonical_deck(self, deck_str: str) -> str:
        """Gera uma representação canônica do deck (cartas ordenadas alfabeticamente)."""
        if not deck_str or deck_str == 'N/D':
            return 'N/D'
        cards = [c.strip() for c in deck_str.replace(' | ', '|').split('|')]
        return " | ".join(sorted(cards))

    def _normalize_battle_time(self, raw_time: str) -> str:
        """Normaliza datas de batalha para formato ISO para manter agregacoes consistentes."""
        if not raw_time:
            return ''

        value = raw_time.strip()
        for fmt in (
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y %H:%M:%S',
            '%Y%m%dT%H%M%S.%fZ',
            '%Y%m%dT%H%M%SZ',
            '%Y%m%dT%H%M%S.%f',
            '%Y%m%dT%H%M%S',
        ):
            try:
                dt = datetime.strptime(value, fmt)
                if fmt.endswith('Z'):
                    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                return dt.strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                continue
        return value

    def _safe_int(self, value, default: int = 0) -> int:
        """Converte para inteiro com fallback para evitar quebra de leitura de CSV."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


    def _load_players_csv(self, player_tag: str) -> Optional[Dict]:
        """Busca jogador no cache de players carregado de CSV."""
        if not self.players_cache:
            return None

        for row in self.players_cache:
            if row.get('player_tag') == player_tag:
                return row
        return None

    def get_card_filename(self, card_name: str) -> str:
        """Convert card name to filename"""
        card_mapping = {
            'Three Musketeers': '3M',
            'Musketeer': 'Musk',
            'Archer Queen': 'ArcherQueen',
            'Baby Dragon': 'BabyD',
            'Barbarian Barrel': 'BarbBarrel',
            'Barbarians': 'Barbs',
            'Battle Healer': 'BattleHealer',
            'Goblin Barrel': 'Barrel',
            'Bomb Tower': 'BombTower',
            'Boss Bandit': 'BossBandit',
            'Cannon Cart': 'CannonCart',
            'Dark Prince': 'DarkPrince',
            'Dart Goblin': 'DartGob',
            'Electro Giant': 'ElectroGiant',
            'Electro Spirit': 'ElectroSpirit',
            'Elixir Golem': 'ElixirGolem',
            'Executioner': 'Exe',
            'Fire Spirit': 'FireSpirit',
            'Flying Machine': 'FlyingMachine',
            'Goblin Gang': 'GobGang',
            'Goblin Giant': 'GobGiant',
            'Goblin Hut': 'GobHut',
            'Goblin Cage': 'GoblinCage',
            'Goblin Curse': 'GoblinCurse',
            'Goblin Demolisher': 'GoblinDemolisher',
            'Goblin Drill': 'GoblinDrill',
            'Goblin Machine': 'GoblinMachine',
            'Spear Goblins': 'Gobs',
            'Goblins': 'Gobs',
            'Golden Knight': 'GoldenKnight',
            'Giant Skeleton': 'GiantSkelly',
            'Heal Spirit': 'HealSpirit',
            'Hog Rider': 'Hog',
            'Minion Horde': 'Horde',
            'Ice Golem': 'IceGolem',
            'Ice Spirit': 'IceSpirit',
            'Ice Wizard': 'IceWiz',
            'Inferno Tower': 'Inferno',
            'Inferno Dragon': 'InfernoD',
            'Knight': 'Knight',
            'Lava Hound': 'Lava',
            'Lumberjack': 'Lumber',
            'Magic Archer': 'MagicArcher',
            'Mega Knight': 'MegaKnight',
            'Mighty Miner': 'MightyMiner',
            'Mini P.E.K.K.A': 'MP',
            'Minions': 'Minions',
            'Mortar': 'Mortar',
            'Mother Witch': 'MotherWitch',
            'Night Witch': 'NightWitch',
            'P.E.K.K.A': 'PEKKA',
            'Prince': 'Prince',
            'Princess': 'Princess',
            'Royal Giant': 'RG',
            'Royal Ghost': 'RoyalGhost',
            'Royal Hogs': 'RoyalHogs',
            'Royal Recruits': 'RoyalRecruits',
            'Skeleton Army': 'Skarmy',
            'Skeleton Dragons': 'SkeletonDragons',
            'Skeleton King': 'SkeletonKing',
            'Skeletons': 'Skellies',
            'Skeleton Barrel': 'SkellyBarrel',
            'Sparky': 'Sparky',
            'Tesla': 'Tesla',
            'The Log': 'Log',
            'Valkyrie': 'Valk',
            'Wall Breakers': 'WallBreakers',
            'Witch': 'Witch',
            'Wizard': 'Wiz',
            'X-Bow': 'XBow',
            'Zap': 'Zap',
            'Zappies': 'Zappies'
        }
        return card_mapping.get(card_name, card_name.replace(' ', '').replace('.', '').replace('-', ''))

    def get_card_image_path(self, card_name: str) -> str:
        """Retorna a URL da imagem da carta usando o cards_master_icons.csv"""
        if not card_name or card_name == 'N/D':
            return "https://royaleapi.github.io/cr-api-assets/cards/unknown.png"

        is_evolution = "Evolution" in card_name
        clean_name = card_name.replace(" (Evolution)", "").strip()
        
        # Tenta buscar no mestre de icones
        card_data = self.cards_master.get(clean_name)
        if card_data:
            if is_evolution and card_data.get('url_evolution') and card_data['url_evolution'] != 'N/A':
                return card_data['url_evolution']
            if card_data.get('url_hero') and card_data['url_hero'] != 'N/A':
                return card_data['url_hero']
            if card_data.get('url_icon') and card_data['url_icon'] != 'N/A':
                return card_data['url_icon']
        
        # Fallback para RoyaleAPI se não encontrar
        filename = clean_name.lower().replace(' ', '-').replace('.', '').replace('-', '-')
        return f"https://royaleapi.github.io/cr-api-assets/cards/{filename}.png"

    def _get_card_name_mapping(self) -> Dict[str, str]:
        """Retorna mapeamento de nomes de cartas para nomes de assets."""
        mapping = {
            'Three Musketeers': '3M',
            'Hero Musketeer': 'Musk',  # Hero version of Musketeer
            'Musketeer': 'Musk',  # Keep regular Musketeer mapping
            'Archer Queen': 'ArcherQueen',
            'Baby Dragon': 'BabyD',
            'Barbarian Barrel': 'BarbBarrel',
            'Barbarians': 'Barbs',
            'Battle Healer': 'BattleHealer',
            'Goblin Barrel': 'Barrel',
            'Bomb Tower': 'BombTower',
            'Boss Bandit': 'BossBandit',
            'Cannon Cart': 'CannonCart',
            'Dark Prince': 'DarkPrince',
            'Dart Goblin': 'DartGob',
            'Electro Giant': 'ElectroGiant',
            'Electro Spirit': 'ElectroSpirit',
            'Elixir Golem': 'ElixirGolem',
            'Executioner': 'Exe',
            'Fire Spirit': 'FireSpirit',
            'Flying Machine': 'FlyingMachine',
            'Goblin Gang': 'GobGang',
            'Goblin Giant': 'GobGiant',
            'Goblin Hut': 'GobHut',
            'Goblin Cage': 'GoblinCage',
            'Goblin Curse': 'GoblinCurse',
            'Goblin Demolisher': 'GoblinDemolisher',
            'Goblin Drill': 'GoblinDrill',
            'Goblin Machine': 'GoblinMachine',
            'Spear Goblins': 'Gobs',
            'Golden Knight': 'GoldenKnight',
            'Giant Skeleton': 'GiantSkelly',
            'Heal Spirit': 'HealSpirit',
            'Hog Rider': 'Hog',
            'Minion Horde': 'Horde',
            'Ice Golem': 'IceGolem',
            'Ice Spirit': 'IceSpirit',
            'Ice Wizard': 'IceWiz',
            'Inferno Tower': 'Inferno',
            'Inferno Dragon': 'InfernoD',
            'Lava Hound': 'Lava',
            'Little Prince': 'LittlePrince',
            'The Log': 'Log',
            'Lumberjack': 'Lumber',
            'Mega Minion': 'MM',
            'Mini P.E.K.K.A': 'MP',
            'Magic Archer': 'MagicArcher',
            'Mega Knight': 'MegaKnight',
            'Mighty Miner': 'MightyMiner',
            'Mother Witch': 'MotherWitch',
            'Musketeer': 'Musk',
            'Night Witch': 'NightWitch',
            'P.E.K.K.A': 'PEKKA',
            'Elixir Collector': 'Pump',
            'Royal Giant': 'RG',
            'Battle Ram': 'Ram',
            'Ram Rider': 'RamRider',
            'Royal Delivery': 'RoyalDelivery',
            'Royal Hogs': 'RoyalHogs',
            'Royal Recruits': 'RoyalRecruits',
            'Skeleton Army': 'Skarmy',
            'Skeleton Dragons': 'SkeletonDragons',
            'Skeleton King': 'SkeletonKing',
            'Skeletons': 'Skellies',
            'Skeleton Barrel': 'SkellyBarrel',
            'Giant Snowball': 'Snowball',
            'Spear Goblins': 'SpearGobs',
            'Goblins': 'Gobs',
            'Spirit Empress': 'SpiritEmpress',
            'Suspicious Bush': 'SuspiciousBush',
            'Tesla': 'Tesla',
            'Valkyrie': 'Valk',
            'Wall Breakers': 'WallBreakers',
            'Wizard': 'Wiz',
            'X-Bow': 'XBow',
            'Elite Barbarians': 'eBarbs',
            'Electro Dragon': 'eDragon',
            'Electro Wizard': 'eWiz'
        }
        
        # Mapeamento de custo de elixir para calculos de deck
        self.card_elixir_costs = {
            'Skeletons': 1, 'Electro Spirit': 1, 'Fire Spirit': 1, 'Ice Spirit': 1, 'Heal Spirit': 1,
            'Zap': 2, 'The Log': 2, 'Giant Snowball': 2, 'Rage': 2, 'Barbarian Barrel': 2,
            'Goblins': 2, 'Spear Goblins': 2, 'Bats': 2, 'Wall Breakers': 2, 'Ice Golem': 2, 'Bomber': 2,
            'Arrows': 3, 'Royal Delivery': 3, 'Tornado': 3, 'Clone': 3, 'Skeleton Army': 3,
            'Guards': 3, 'Minions': 3, 'Archers': 3, 'Firecracker': 3, 'Knight': 3, 'Mega Minion': 3,
            'Dart Goblin': 3, 'Princess': 3, 'Miner': 3, 'Bandit': 3, 'Royal Ghost': 3, 'Fisherman': 3,
            'Skeleton Barrel': 3, 'Elixir Golem': 3, 'Ice Wizard': 3, 'Tombstone': 3, 'Goblin Gang': 3,
            'Little Prince': 3, 'Cannon': 3, 'Phoenix': 4, 'Battle Healer': 4, 'Hunter': 4, 'Electro Wizard': 4,
            'Mother Witch': 4, 'Magic Archer': 4, 'Lumberjack': 4, 'Night Witch': 4, 'Inferno Dragon': 4,
            'Baby Dragon': 4, 'Dark Prince': 4, 'Battle Ram': 4, 'Hog Rider': 4, 'Mini P.E.K.K.A': 4,
            'Valkyrie': 4, 'Musketeer': 4, 'Fireball': 4, 'Poison': 4, 'Freeze': 4, 'Goblin Cage': 4,
            'Bomb Tower': 4, 'Tesla': 4, 'Furnace': 4, 'Zappies': 4, 'Flying Machine': 4, 'Skeleton Dragons': 4,
            'Golden Knight': 4, 'Mighty Miner': 4, 'Skeleton King': 4, 'Giant': 5, 'Prince': 5, 'Witch': 5,
            'Balloon': 5, 'Executioner': 5, 'Wizard': 5, 'Bowler': 5, 'Ram Rider': 5, 'Electro Dragon': 5,
            'Inferno Tower': 5, 'Goblin Hut': 5, 'Barbarians': 5, 'Minion Horde': 5, 'Rascals': 5, 'Royal Hogs': 5,
            'Monk': 5, 'Archer Queen': 5, 'Graveyard': 5, 'Giant Skeleton': 6, 'Royal Giant': 6, 'Goblin Giant': 6,
            'Sparky': 6, 'X-Bow': 6, 'Elixir Collector': 6, 'Rocket': 6, 'Lightning': 6, 'Barbarian Hut': 6,
            'Elite Barbarians': 6, 'P.E.K.K.A': 7, 'Mega Knight': 7, 'Lava Hound': 7, 'Electro Giant': 7,
            'Royal Recruits': 7, 'Golem': 8, 'Three Musketeers': 9,
            'Goblin Curse': 2, 'Goblin Demolisher': 4, 'Goblin Machine': 5, 'Suspicious Bush': 2, 'Spirit Empress': 3
        }
        return mapping
    
    def _get_tower_hp(self, level: int) -> int:
        """Retorna o HP da Torre do Rei baseado no nivel."""
        hp_map = {
            1: 2400, 2: 2568, 3: 2736, 4: 2904, 5: 3096, 
            6: 3312, 7: 3528, 8: 3816, 9: 4056, 10: 4416, 
            11: 4824, 12: 5304, 13: 5832, 14: 6408, 15: 7032
        }
        return hp_map.get(int(level), 0)

    def _get_deck_metrics(self, deck_str: str) -> Dict:
        """Calcula media de elixir e ciclo de 4 cartas."""
        if not deck_str or deck_str == 'N/D':
            return {'avg': 0, 'cycle': 0}
        
        cards = [c.strip() for c in deck_str.replace(' | ', '|').split('|')]
        costs = []
        for c in cards:
            # Tenta encontrar o custo no mapeamento
            cost = self.card_elixir_costs.get(c, 3.5) # Fallback para media se nao encontrar
            costs.append(cost)
        
        if not costs:
            return {'avg': 0, 'cycle': 0}
            
        avg = sum(costs) / len(costs)
        # Ciclo de 4 cartas: as 4 mais baratas
        cycle = sum(sorted(costs)[:4])
        
        return {'avg': round(avg, 1), 'cycle': cycle}
    
    def fetch_opponent_data_from_api(self, opponent_tag: str) -> Optional[Dict]:
        """Fetch opponent data from API and save to database"""
        if not self.api_token or not opponent_tag or opponent_tag in self.failed_tags:
            return None
        
        # Valid tag check (should start with # and have alphanumeric chars)
        if not opponent_tag.startswith('#'):
            # If it's a name instead of a tag, it's likely a data issue from the source
            print(f"Skipping invalid player tag: {opponent_tag}")
            self.failed_tags.add(opponent_tag)
            return None

        clean_tag = opponent_tag.replace('#', '')
        url = f"{self.base_url}/players/%23{clean_tag}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 404:
                print(f"Player not found (404): {opponent_tag}")
                self.failed_tags.add(opponent_tag)
                return None
                
            response.raise_for_status()
            player_data = response.json()
            
            # Save to players table
            conn = sqlite3.connect(self.db_path, uri=True)
            cursor = conn.cursor()
            
            clan_info = player_data.get('clan', {})
            cursor.execute("""
                INSERT OR REPLACE INTO players 
                (player_tag, name, trophies, best_trophies, level, clan_tag, clan_name, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_data['tag'],
                player_data['name'],
                player_data.get('trophies', 0),
                player_data.get('bestTrophies', 0),
                player_data.get('expLevel', 0),
                clan_info.get('tag'),
                clan_info.get('name'),
                datetime.now(UTC).isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            # Rate limiting
            time.sleep(0.5)
            
            return player_data
        except requests.RequestException as e:
            print(f"Error fetching opponent data for {opponent_tag}: {e}")
            return None
    
    def fetch_opponent_battles_from_api(self, opponent_tag: str) -> Optional[List[Dict]]:
        """Fetch opponent battles from API and save to database"""
        if not self.api_token or not opponent_tag:
            return None
        
        clean_tag = opponent_tag.replace('#', '')
        url = f"{self.base_url}/players/%23{clean_tag}/battlelog"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            battles = response.json()
            
            # Save battles to database (similar to analyzer.py)
            if battles:
                conn = sqlite3.connect(self.db_path, uri=True)
                cursor = conn.cursor()
                
                for battle in battles:
                    teams = battle.get('team', [])
                    player_team = None
                    
                    # Find the opponent's team (they are the player in their own battles)
                    for team in teams:
                        if team.get('tag') == opponent_tag:
                            player_team = team
                            break
                    
                    if not player_team:
                        continue
                    
                    opponents = battle.get('opponent', [])
                    opponent_team = opponents[0] if opponents else None
                    
                    # Format deck cards
                    deck_cards = ' | '.join(sorted([card['name'] for card in player_team.get('cards', [])]))
                    
                    # Determine result from crowns (same logic as analyzer.py)
                    player_crowns = player_team.get('crowns', 0)
                    opponent_crowns = opponent_team.get('crowns', 0) if opponent_team else 0
                    
                    if player_crowns > opponent_crowns:
                        result = 'victory'
                    elif player_crowns < opponent_crowns:
                        result = 'defeat'
                    else:
                        result = 'draw'
                    
                    trophy_change = battle.get('trophyChange', 0)
                    
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO battles 
                            (player_tag, battle_time, battle_type, game_mode, is_ladder_tournament,
                             arena_id, arena_name, result, crowns, deck_cards, 
                             opponent_tag, opponent_name, opponent_trophies, opponent_deck_cards,
                             trophy_change)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            opponent_tag,
                            battle['battleTime'],
                            battle.get('type'),
                            battle.get('gameMode', {}).get('name'),
                            battle.get('isLadderTournament', False),
                            battle.get('arena', {}).get('id'),
                            battle.get('arena', {}).get('name'),
                            result,
                            player_crowns,
                            deck_cards,
                            opponent_team.get('tag') if opponent_team else None,
                            opponent_team.get('name') if opponent_team else None,
                            opponent_team.get('startingTrophies') if opponent_team else None,
                            ' | '.join(sorted([card['name'] for card in opponent_team.get('cards', [])])) if opponent_team else None,
                            trophy_change
                        ))
                    except sqlite3.Error as e:
                        print(f"Error inserting battle: {e}")
                        continue
                
                conn.commit()
                conn.close()
            
            # Rate limiting
            time.sleep(1)
            
            return battles
        except requests.RequestException as e:
            print(f"Error fetching opponent battles for {opponent_tag}: {e}")
            return None
    
    
    def safe_filename(self, name: str) -> str:
        """Convert member name to safe filename"""
        # Remove special characters and spaces
        safe_name = re.sub(r'[^\w\s-]', '', name)
        safe_name = re.sub(r'\s+', '_', safe_name)
        return safe_name.lower()
    
    
    def get_player_stats(self) -> Optional[Dict]:
        """Get player statistics from CSV files"""
        player_row = self._load_players_csv(self.player_tag)
        if not player_row:
            # Tenta com outra tag se falhar
            player_row = self._load_players_csv('#YVJR0JLY')
            if not player_row:
                return None
        
        player_tag = player_row.get('player_tag')
        
        # Get battle stats from CSV
        battles = self._load_all_battles_from_csv(player_tag)
        
        total_battles = len(battles)
        wins = sum(1 for b in battles if b['result'] == 'victory')
        losses = sum(1 for b in battles if b['result'] == 'defeat')
        draws = sum(1 for b in battles if b['result'] == 'draw')
        total_trophy_change = sum(b['trophy_change'] for b in battles)
        last_battle = battles[0]['battle_time'] if battles else None
        first_battle = battles[-1]['battle_time'] if battles else None
        
        # Clan info can still be None if not in players.csv or if we want to skip SQL for clan_members too
        # For now, let's keep it simple and focus on the main request: CSV data only.
        
        return {
            'player_tag': player_tag,
            'name': player_row.get('name', 'Unknown'),
            'trophies': int(player_row.get('trophies', 0) or 0),
            'best_trophies': int(player_row.get('best_trophies', 0) or 0),
            'level': int(player_row.get('level', 0) or 0),
            'clan_tag': player_row.get('clan_tag', ''),
            'clan_name': player_row.get('clan_name', ''),
            'last_updated': player_row.get('last_updated', datetime.now(UTC).isoformat()),
            'total_battles': total_battles,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'total_trophy_change': total_trophy_change,
            'last_battle': last_battle,
            'first_battle': first_battle
        }
    
    def get_deck_performance(self, limit: int = 10, player_tag: str = None) -> List[Dict]:
        """Get deck performance data using CSV cache"""
        if not self.battles_cache:
            return []
            
        deck_stats = {}
        for b in self.battles_cache:
            deck = b.get('deck_cards')
            if not deck:
                continue
                
            if deck not in deck_stats:
                deck_stats[deck] = {
                    'deck_cards': deck,
                    'total_battles': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_trophy_change': 0,
                    'total_crowns': 0
                }
            
            s = deck_stats[deck]
            s['total_battles'] += 1
            if b.get('result') == 'victory':
                s['wins'] += 1
            elif b.get('result') == 'defeat':
                s['losses'] += 1
                
            s['total_trophy_change'] += b.get('trophy_change', 0)
            try:
                s['total_crowns'] += int(b.get('crowns', 0) or 0)
            except:
                pass
        
        all_decks = []
        for deck, s in deck_stats.items():
            s['win_rate'] = round((s['wins'] / s['total_battles']) * 100, 2)
            s['avg_trophy_change'] = round(s['total_trophy_change'] / s['total_battles'], 2)
            s['avg_crowns'] = round(s['total_crowns'] / s['total_battles'], 2)
            all_decks.append(s)
            
        # Ordena por win_rate desc, total_battles desc
        all_decks.sort(key=lambda x: (x['win_rate'], x['total_battles']), reverse=True)
        return all_decks[:limit]
    
    def get_deck_performance_same_level(self, limit: int = 10, player_tag: str = None) -> List[Dict]:
        """Get deck performance data from clan members with same trophies level (>=10K) as user using CSV caches"""
        if not player_tag:
            return []
            
        # Get user info from players_cache
        user_info = next((p for p in self.players_cache if p.get('player_tag') == player_tag), None)
        if not user_info:
            return []
            
        user_trophies = int(user_info.get('trophies', 0) or 0)
        clan_tag = user_info.get('clan_tag')
        
        if user_trophies < 10000 or not clan_tag:
            return []
            
        # Get active clan members with trophies >= 10000
        same_level_members = [
            m for m in self.clan_members_cache 
            if m.get('clan_tag') == clan_tag and int(m.get('trophies', 0) or 0) >= 10000
        ]
        
        active_tags = {m['player_tag'] for m in same_level_members}
        active_tags.add(player_tag) # Ensure user is included
        
        # Maps to store stats
        member_decks = {}
        member_overall = {}
        
        # Process battles_cache once
        for battle in self.battles_cache:
            p_tag = battle.get('player_tag')
            if p_tag not in active_tags:
                continue
                
            if p_tag not in member_overall:
                member_overall[p_tag] = {'total': 0, 'wins': 0, 'losses': 0, 'trophy_change': 0, 'crowns': []}
            
            res = battle.get('result')
            member_overall[p_tag]['total'] += 1
            if res == 'victory': member_overall[p_tag]['wins'] += 1
            elif res == 'defeat': member_overall[p_tag]['losses'] += 1
            member_overall[p_tag]['trophy_change'] += int(battle.get('trophy_change', 0) or 0)
            member_overall[p_tag]['crowns'].append(int(battle.get('crowns', 0) or 0))
            
            deck = battle.get('deck_cards')
            if not deck: continue
            
            if p_tag not in member_decks: member_decks[p_tag] = {}
            if deck not in member_decks[p_tag]:
                member_decks[p_tag][deck] = {'total': 0, 'wins': 0, 'losses': 0, 'trophy_change': 0, 'crowns': []}
                
            member_decks[p_tag][deck]['total'] += 1
            if res == 'victory': member_decks[p_tag][deck]['wins'] += 1
            elif res == 'defeat': member_decks[p_tag][deck]['losses'] += 1
            member_decks[p_tag][deck]['trophy_change'] += int(battle.get('trophy_change', 0) or 0)
            member_decks[p_tag][deck]['crowns'].append(int(battle.get('crowns', 0) or 0))

        results = []
        for p_tag in active_tags:
            decks = member_decks.get(p_tag, {})
            if not decks:
                current_deck = next((d['deck_cards'] for d in reversed(self.clan_decks_cache) if d['player_tag'] == p_tag), None)
                if not current_deck: continue
                best_deck = current_deck
                deck_stats = {'total': 0, 'wins': 0, 'losses': 0, 'trophy_change': 0, 'crowns': [0]}
            else:
                best_deck, deck_stats = max(decks.items(), key=lambda x: (x[1]['wins']/x[1]['total'] if x[1]['total']>0 else 0, x[1]['total']))
            
            overall = member_overall.get(p_tag, {'total': 0, 'wins': 0, 'losses': 0, 'trophy_change': 0, 'crowns': [0]})
            m_name = next((m['name'] for m in same_level_members if m['player_tag'] == p_tag), 'Usuario' if p_tag == player_tag else 'Membro')
            
            wr = (deck_stats['wins'] / deck_stats['total'] * 100) if deck_stats['total'] > 0 else 0
            res_item = {
                'deck_cards': best_deck,
                'total_battles': deck_stats['total'],
                'wins': deck_stats['wins'],
                'losses': deck_stats['losses'],
                'win_rate': round(wr, 2),
                'total_trophy_change': deck_stats['trophy_change'],
                'avg_trophy_change': round(deck_stats['trophy_change']/deck_stats['total'] if deck_stats['total']>0 else 0, 2),
                'avg_crowns': round(sum(deck_stats['crowns'])/len(deck_stats['crowns']) if deck_stats['crowns'] else 0, 2),
                'member_tag': p_tag,
                'member_name': m_name,
                'member_total_battles': overall['total'],
                'member_wins': overall['wins'],
                'member_losses': overall['losses'],
                'member_trophy_change': overall['trophy_change'],
                'member_avg_crowns': round(sum(overall['crowns'])/len(overall['crowns']) if overall['crowns'] else 0, 2)
            }
            if p_tag == player_tag: results.insert(0, res_item)
            else: results.append(res_item)

        if len(results) > 1:
            user_part = [results[0]]
            others = sorted(results[1:], key=lambda x: (x['win_rate'], x['total_battles']), reverse=True)
            results = user_part + others[:limit]
        return results

    def get_opponent_frequency(self, limit: int = 15, player_tag: str = None) -> List[Dict]:
        """Get opponent deck frequency data using CSV cache"""
        if not self.battles_cache:
            return []
            
        from datetime import timedelta
        now = datetime.now(UTC)
        days_since_monday = now.weekday()
        week_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_start_str = week_start.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Filtra batalhas de derrota da semana
        defeats_this_week = [b for b in self.battles_cache 
                            if b.get('result') == 'defeat' 
                            and b.get('battle_time', '') >= week_start_str]
        
        if not defeats_this_week:
            return []
            
        deck_stats = {}
        for b in defeats_this_week:
            deck = b.get('opponent_deck_cards')
            if not deck:
                continue
                
            if deck not in deck_stats:
                deck_stats[deck] = {
                    'deck_cards': deck,
                    'total_battles': 0,
                    'wins': 0, 
                    'losses': 0,
                    'total_trophy_change': 0,
                    'total_crowns': 0,
                    'opponent_tag': b.get('opponent_tag'),
                    'opponent_name': b.get('opponent_name')
                }
            
            s = deck_stats[deck]
            s['total_battles'] += 1
            s['wins'] += 1
            s['total_trophy_change'] += b.get('trophy_change', 0)
            try:
                s['total_crowns'] += int(b.get('crowns', 0) or 0)
            except:
                pass
                
        results = []
        for deck, s in deck_stats.items():
            s['win_rate'] = 100.0
            s['avg_trophy_change'] = round(s['total_trophy_change'] / s['total_battles'], 2)
            s['avg_crowns'] = round(s['total_crowns'] / s['total_battles'], 2)
            results.append(s)
            
        results.sort(key=lambda x: x['total_battles'], reverse=True)
        return results[:limit]

    def get_repeated_opponents_stats(self, player_tag: str = None) -> List[Dict]:
        """Get statistics for opponents faced multiple times using CSV cache"""
        if not self.battles_cache:
            return []
            
        # Agrupar batalhas por oponente
        opponents_battles = {}
        for b in self.battles_cache:
            o_tag = b.get('opponent_tag')
            if not o_tag: continue
            if o_tag not in opponents_battles:
                opponents_battles[o_tag] = []
            opponents_battles[o_tag].append(b)
            
        results = []
        for o_tag, battles in opponents_battles.items():
            if len(battles) < 2: continue
            
            latest_b = battles[0]
            o_name = latest_b.get('opponent_name') or latest_b.get('oponente')
            if not o_name or o_name == 'Desconhecido' or o_name == 'Oponente':
                # Tenta em outras batalhas do mesmo oponente
                for b in battles:
                    name = b.get('opponent_name') or b.get('oponente')
                    if name and name not in ['Desconhecido', 'Oponente']:
                        o_name = name
                        break
            
            if not o_name:
                o_name = o_tag
                
            latest_o_trophies = latest_b.get('opponent_trophies', 0)
            
            period_stats = self._get_opponent_period_stats_from_cache(battles)
            encounter_stats = []
            for b in battles:
                encounter_stats.append({
                    'result': b.get('result', 'draw'),
                    'battle_time': b.get('battle_time', ''),
                    'my_deck': b.get('deck_cards', ''),
                    'opp_deck': b.get('opponent_deck_cards', ''),
                    'crowns': self._safe_int(b.get('crowns', 0), 0),
                    'opponent_crowns': self._safe_int(b.get('opponent_crowns', 0), 0),
                    'game_mode': b.get('game_mode', 'Desconhecido'),
                    'trophy_change': self._safe_int(b.get('trophy_change', 0), 0)
                })
            encounter_stats.sort(key=lambda x: x.get('battle_time', ''), reverse=True)
            
            deck_stats = {}
            for b in battles:
                deck = b.get('opponent_deck_cards')
                if not deck: continue
                if deck not in deck_stats:
                    deck_stats[deck] = {'total': 0, 'wins': 0}
                deck_stats[deck]['total'] += 1
                if b.get('result') == 'defeat': # Se o usuário foi derrotado, o deck do oponente "venceu"
                    deck_stats[deck]['wins'] += 1
            
            best_deck = None
            if deck_stats:
                sorted_decks = sorted(deck_stats.items(), key=lambda x: (x[1]['wins']/x[1]['total'], x[1]['total']), reverse=True)
                deck_id, d_s = sorted_decks[0]
                best_deck = {
                    'deck_cards': deck_id,
                    'total_battles': d_s['total'],
                    'wins': d_s['wins'],
                    'losses': d_s['total'] - d_s['wins'],
                    'win_rate': round(d_s['wins']/d_s['total']*100, 2)
                }
                
            # Estatísticas do usuário contra este oponente
            user_wins = sum(1 for b in battles if b.get('result') == 'victory')
            user_losses = sum(1 for b in battles if b.get('result') == 'defeat')
            user_draws = sum(1 for b in battles if b.get('result') == 'draw')
            total_encounters = len(battles)
            user_wr = (user_wins / total_encounters * 100) if total_encounters > 0 else 0
            
            # Categorização
            if user_wr < 40:
                category = "Nêmese"
                category_class = "nemesis"
            elif user_wr > 60:
                category = "Freguês"
                category_class = "customer"
            else:
                category = "Equilibrado"
                category_class = "balanced"

            results.append({
                'opponent_tag': o_tag,
                'opponent_name': o_name,
                'latest_opponent_trophies': latest_o_trophies,
                'total_battles': total_encounters,
                'user_wins': user_wins,
                'user_losses': user_losses,
                'user_draws': user_draws,
                'user_win_rate': round(user_wr, 2),
                'category': category,
                'category_class': category_class,
                'last_encounter': latest_b.get('battle_time'),
                'stats': encounter_stats,
                'period_stats': period_stats,
                'best_deck': best_deck
            })
            
        # Ordena por total de batalhas desc, win rate do usuário asc (nemeses primeiro)
        results.sort(key=lambda x: (x['total_battles'], -x['user_win_rate']), reverse=True)
        return results

    def get_lethal_opponent_decks(self, limit: int = 10) -> List[Dict]:
        """Analisa quais decks de oponentes causam mais derrotas ao usuário usando agrupamento canônico."""
        if not self.battles_cache: return []
        
        lethal_decks = {}
        for b in self.battles_cache:
            if b.get('result') != 'defeat': continue
            
            opp_deck_raw = b.get('opp_deck')
            if not opp_deck_raw or opp_deck_raw == 'N/D': continue
            
            # Usa chave canônica para agrupar decks idênticos em ordens diferentes
            deck_key = self._get_canonical_deck(opp_deck_raw)
            
            if deck_key not in lethal_decks:
                lethal_decks[deck_key] = {
                    'deck': deck_key,
                    'losses_caused': 0,
                    'opponents': set(),
                    'last_encounter': b.get('battle_time'),
                    'cards': [c.strip() for c in deck_key.split(' | ')]
                }
            
            lethal_decks[deck_key]['losses_caused'] += 1
            lethal_decks[deck_key]['opponents'].add(b.get('opponent_name', 'Desconhecido'))
            if b.get('battle_time') > lethal_decks[deck_key]['last_encounter']:
                lethal_decks[deck_key]['last_encounter'] = b.get('battle_time')
                
        # Converte para lista e ordena por impacto
        results = list(lethal_decks.values())
        results.sort(key=lambda x: x['losses_caused'], reverse=True)
        
        # Formata para o template
        for r in results:
            r['opponents_list'] = ", ".join(list(r['opponents'])[:3])
            if len(r['opponents']) > 3:
                r['opponents_list'] += f" e outros {len(r['opponents'])-3}"
        
        return results[:limit]

    def _get_opponent_period_stats_from_cache(self, battles: List[Dict]) -> Dict:
        """Helper to calculate period stats from a list of battles"""
        from datetime import timedelta
        now_utc = datetime.now(UTC)
        brt_offset = timedelta(hours=-3)
        now_brt = now_utc + brt_offset
        
        today_start = (now_brt.replace(hour=0, minute=0, second=0, microsecond=0) - brt_offset).strftime('%Y-%m-%dT%H:%M:%S')
        week_start = ((now_brt - timedelta(days=now_brt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0) - brt_offset).strftime('%Y-%m-%dT%H:%M:%S')
        month_start = (now_brt.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - brt_offset).strftime('%Y-%m-%dT%H:%M:%S')
        year_start = (now_brt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - brt_offset).strftime('%Y-%m-%dT%H:%M:%S')
        
        periods = {'day': today_start, 'week': week_start, 'month': month_start, 'year': year_start}
        stats = {}
        for p_name, p_start in periods.items():
            p_battles = [b for b in battles if b.get('battle_time', '') >= p_start]
            total = len(p_battles)
            wins = sum(1 for b in p_battles if b.get('result') == 'victory')
            losses = sum(1 for b in p_battles if b.get('result') == 'defeat')
            draws = sum(1 for b in p_battles if b.get('result') == 'draw')
            trophy_change = sum(b.get('trophy_change', 0) for b in p_battles)
            stats[p_name] = {
                'total': total, 'wins': wins, 'losses': losses, 'draws': draws,
                'win_rate': round(wins/total*100, 1) if total > 0 else 0,
                'trophy_change': trophy_change
            }
        return stats
    
    def get_card_level_analytics(self) -> Dict:
        """Get card level analytics from CSV cache"""
        if not self.battles_cache:
            return {}
            
        analytics = {}
        total_player_level = 0
        total_opponent_level = 0
        level_advantage_wins = 0
        level_disadvantage_wins = 0
        total_with_levels = 0
        
        # Pega as últimas 50 batalhas do cache
        recent_50 = self.battles_cache[:50]
        
        for b in recent_50:
            p_lvl = b.get('player_level', 0)
            o_lvl = b.get('opponent_level', 0)
            res = b.get('result')
            
            if p_lvl and o_lvl:
                total_player_level += p_lvl
                total_opponent_level += o_lvl
                total_with_levels += 1
                
                if res == 'victory':
                    if p_lvl > o_lvl:
                        level_advantage_wins += 1
                    elif p_lvl < o_lvl:
                        level_disadvantage_wins += 1
        
        if total_with_levels > 0:
            analytics['avg_player_level'] = round(total_player_level / total_with_levels, 1)
            analytics['avg_opponent_level'] = round(total_opponent_level / total_with_levels, 1)
            analytics['level_advantage_wins'] = level_advantage_wins
            analytics['level_disadvantage_wins'] = level_disadvantage_wins
            analytics['total_with_levels'] = total_with_levels
            
        # Opponent clan analysis
        clan_stats = {}
        for b in self.battles_cache:
            c_name = b.get('opponent_clan_name')
            if not c_name:
                continue
            if c_name not in clan_stats:
                clan_stats[c_name] = {'battles': 0, 'wins': 0}
            clan_stats[c_name]['battles'] += 1
            if b.get('result') == 'victory':
                clan_stats[c_name]['wins'] += 1
                
        opp_clans = []
        for name, stats in clan_stats.items():
            opp_clans.append({
                'opponent_clan_name': name,
                'battles': stats['battles'],
                'wins': stats['wins']
            })
        opp_clans.sort(key=lambda x: x['battles'], reverse=True)
        analytics['opponent_clans'] = opp_clans[:10]
        
        return analytics

    def get_recent_battles(self, limit: int = 15, player_tag: str = None) -> List[Dict]:
        """Get recent battles from CSV cache"""
        return self.battles_cache[:limit]
    
    def get_clan_members(self) -> List[Dict]:
        """Get clan member data from CSV cache"""
        if not self.clan_members_cache:
            return []
            
        members = []
        for m in self.clan_members_cache:
            members.append({
                'name': m.get('name', 'Desconhecido'),
                'role': m.get('role', 'member'),
                'trophies': int(m.get('trophies', 0) or 0),
                'donations': int(m.get('donations', 0) or 0),
                'donations_received': int(m.get('donations_received', 0) or 0),
                'last_seen': m.get('last_seen', '')
            })
            
        # Ordenação: role priority, then trophies
        role_priority = {'leader': 1, 'coLeader': 2, 'elder': 3, 'member': 4}
        members.sort(key=lambda x: (role_priority.get(x['role'], 5), -x['trophies']))
        
        return members
    
    def get_daily_battle_stats(self, days_limit: int = 30, player_tag: str = None) -> List[Dict]:
        """Get daily wins/losses aggregation from CSV files"""
        if not player_tag:
            player_tag = self.player_tag
            
        battles = self._load_all_battles_from_csv(player_tag)
        
        # Aggregate by date
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_limit - 1)
        
        daily_map = {}
        curr = start_date
        while curr <= end_date:
            date_str = curr.strftime('%Y-%m-%d')
            daily_map[date_str] = {'wins': 0, 'losses': 0, 'draws': 0, 'total_battles': 0}
            curr += timedelta(days=1)
            
        for b in battles:
            b_time = b['battle_time']
            if not b_time: continue
            
            # Extract date part
            b_date = b_time.split('T')[0] if 'T' in b_time else b_time.split(' ')[0]
            
            if b_date in daily_map:
                res = b['result']
                if res == 'victory':
                    daily_map[b_date]['wins'] += 1
                elif res == 'defeat':
                    daily_map[b_date]['losses'] += 1
                elif res == 'draw':
                    daily_map[b_date]['draws'] += 1
                daily_map[b_date]['total_battles'] += 1
                
        # Convert map to sorted list
        daily_stats = []
        for date_str in sorted(daily_map.keys()):
            stats = daily_map[date_str]
            daily_stats.append({
                'date': date_str,
                'wins': stats['wins'],
                'losses': stats['losses'],
                'draws': stats['draws'],
                'total_battles': stats['total_battles']
            })
            
        return daily_stats
    
    def get_clan_rankings_data(self, days_limit: int = 7) -> List[Dict]:
        """Get latest clan rankings with progression data using CSV caches"""
        if not self.rankings_history_cache:
            return []
            
        # Group by player_tag to get the latest entry
        latest_rankings = {}
        for row in self.rankings_history_cache:
            p_tag = row['player_tag']
            recorded_at = row['recorded_at']
            if p_tag not in latest_rankings or recorded_at > latest_rankings[p_tag]['recorded_at']:
                latest_rankings[p_tag] = row
                
        # Merge with clan_members for role and last_seen
        members_map = {m['player_tag']: m for m in self.clan_members_cache}
        
        rankings = []
        for p_tag, data in latest_rankings.items():
            member = members_map.get(p_tag, {})
            rankings.append({
                'player_tag': p_tag,
                'name': data.get('name'),
                'clan_rank': int(data.get('clan_rank', 0) or 0),
                'trophies': int(data.get('trophies', 0) or 0),
                'donations': int(data.get('donations', 0) or 0),
                'donations_received': int(data.get('donations_received', 0) or 0),
                'trophy_change': int(data.get('trophy_change', 0) or 0),
                'donation_change': int(data.get('donation_change', 0) or 0),
                'recorded_at': data.get('recorded_at'),
                'role': member.get('role', 'member'),
                'last_seen': member.get('last_seen')
            })
            
        # Sort by rank
        rankings.sort(key=lambda x: x['clan_rank'])
        return rankings
    
    def get_player_clan_progression(self, player_tag: str, days_limit: int = 30) -> List[Dict]:
        """Get specific player's clan ranking progression over time using CSV cache"""
        if not self.rankings_history_cache:
            return []
            
        # Filter by player_tag
        progression = [
            {
                'date': r.get('recorded_at', '').split('T')[0],
                'clan_rank': int(r.get('clan_rank', 0) or 0),
                'trophies': int(r.get('trophies', 0) or 0),
                'trophy_change': int(r.get('trophy_change', 0) or 0),
                'donations': int(r.get('donations', 0) or 0),
                'donation_change': int(r.get('donation_change', 0) or 0)
            }
            for r in self.rankings_history_cache
            if r.get('player_tag') == player_tag
        ]
        
        # Sort by date descending
        progression.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Apply limit
        return progression[:days_limit]
    
    def get_clan_deck_analytics(self) -> Dict:
        """Analyze clan deck usage and changes using CSV cache"""
        analytics = {
            'popular_decks': [],
            'favorite_cards': [],
            'deck_experimenters': []
        }
        
        if not self.clan_decks_cache:
            return analytics
            
        # Get latest deck for each player
        latest_decks = {}
        for entry in self.clan_decks_cache:
            p_tag = entry.get('player_tag')
            # Assuming cache is sorted by recorded_at or sequential, last one wins
            latest_decks[p_tag] = entry
            
        # Popular Decks
        deck_counts = {}
        for entry in latest_decks.values():
            deck = entry.get('deck_cards')
            if not deck: continue
            if deck not in deck_counts:
                deck_counts[deck] = {'usage_count': 0, 'users': []}
            deck_counts[deck]['usage_count'] += 1
            deck_counts[deck]['users'].append(entry.get('name', 'Unknown'))
            
        popular_decks = [
            {'deck_cards': d, 'usage_count': s['usage_count'], 'users': ", ".join(s['users'])}
            for d, s in deck_counts.items()
        ]
        popular_decks.sort(key=lambda x: x['usage_count'], reverse=True)
        analytics['popular_decks'] = popular_decks[:10]
        
        # Favorite Cards
        card_counts = {}
        for entry in latest_decks.values():
            card = entry.get('favorite_card')
            if not card or card == '': continue
            if card not in card_counts:
                card_counts[card] = {'usage_count': 0, 'users': []}
            card_counts[card]['usage_count'] += 1
            card_counts[card]['users'].append(entry.get('name', 'Unknown'))
            
        favorite_cards = [
            {'card_name': c, 'usage_count': s['usage_count'], 'users': ", ".join(s['users'])}
            for c, s in card_counts.items()
        ]
        favorite_cards.sort(key=lambda x: x['usage_count'], reverse=True)
        analytics['favorite_cards'] = favorite_cards[:10]
        
        # Deck Experimenters (Counting unique deck combinations per player)
        player_changes = {}
        for entry in self.clan_decks_cache:
            p_tag = entry.get('player_tag')
            deck = entry.get('deck_cards')
            if not p_tag or not deck: continue
            
            if p_tag not in player_changes:
                player_changes[p_tag] = {
                    'name': entry.get('name', 'Unknown'),
                    'unique_decks': set(),
                    'first_seen': entry.get('first_seen', ''),
                    'last_seen': entry.get('last_seen', '')
                }
            player_changes[p_tag]['unique_decks'].add(deck)
            # Update dates
            if entry.get('first_seen', '') < player_changes[p_tag]['first_seen']:
                player_changes[p_tag]['first_seen'] = entry.get('first_seen')
            if entry.get('last_seen', '') > player_changes[p_tag]['last_seen']:
                player_changes[p_tag]['last_seen'] = entry.get('last_seen')
                
        deck_experimenters = [
            {
                'player_tag': p_tag,
                'name': info['name'],
                'deck_changes': len(info['unique_decks']),
                'first_deck': info['first_seen'],
                'latest_deck': info['last_seen']
            }
            for p_tag, info in player_changes.items()
        ]
        deck_experimenters.sort(key=lambda x: x['deck_changes'], reverse=True)
        analytics['deck_experimenters'] = deck_experimenters
        
        return analytics
    
    def format_time_ago(self, timestamp: str) -> str:
        """Format timestamp as time ago"""
        if not timestamp or timestamp == 'never':
            return "never"
            
        try:
            if 'T' in timestamp:
                if timestamp.endswith('Z'):
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromisoformat(timestamp)
            else:
                dt = datetime.fromisoformat(timestamp)
                
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                # Se não tem timezone (caso dos CSVs locais), assumimos que é horário do Brasil (UTC-3)
                dt = dt.replace(tzinfo=timezone(timedelta(hours=-3)))
            
            # Garantir que dt esteja em UTC para comparação
            dt_utc = dt.astimezone(timezone.utc)
            time_diff = now - dt_utc
            
            # Se for negativo (por causa de relógios levemente dessincronizados), mostrar como "just now"
            total_seconds = time_diff.total_seconds()
            
            if total_seconds < 0:
                return "just now"
            elif total_seconds < 60:
                return "just now"
            elif total_seconds < 3600:
                minutes = int(total_seconds // 60)
                return f"{minutes} minutes ago"
            elif total_seconds < 86400:
                hours = int(total_seconds // 3600)
                return f"{hours} hours ago"
            else:
                days = int(total_seconds // 86400)
                return f"{days} days ago"
        except:
            return "unknown"
    
    def format_date(self, timestamp: str) -> str:
        """Format timestamp as readable date"""
        if not timestamp:
            return "unknown"
            
        try:
            # Tenta lidar com formatos ISO (com T ou espaco)
            clean_str = timestamp.replace('Z', '+00:00').replace(' ', 'T')
            if 'T' in clean_str:
                dt = datetime.fromisoformat(clean_str)
            else:
                # Fallback para outros formatos comuns
                dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                
            return dt.strftime('%B %d, %Y')
        except:
            return "unknown"
    
    def generate_deck_cards_html(self, deck_cards: str, show_names: bool = True) -> str:
        """Generate HTML for deck cards with images"""
        if not deck_cards:
            return ""
        
        # Handle both ' | ' and '|' separators
        if ' | ' in deck_cards:
            cards = deck_cards.split(' | ')
        else:
            cards = [c.strip() for c in deck_cards.split('|')]
        cards_html = ""
        
        for card in cards:
            img_path = self.get_card_image_path(card)
            name_html = f'<div class="card-name">{card}</div>' if show_names else ''
            if show_names:
                cards_html += f"""
                <div class="card-container">
                    <img src="{img_path}" alt="{card}" class="card-image" title="{card}" loading="lazy">
                    {name_html}
                </div>
            """
            else:
                cards_html += f'<div class="card-container"><img src="{img_path}" alt="{card}" class="card-image" title="{card}" loading="lazy">{name_html}</div>'
        
        css_class = "deck-cards-compact" if not show_names else "deck-cards"
        return f'<div class="{css_class}">{cards_html}</div>'
    
    def generate_daily_histogram_html(self, daily_stats: List[Dict], css_class: str = "", include_legend: bool = True) -> str:
        """Generate HTML for daily wins/losses stacked histogram"""
        if not daily_stats:
            return "<p>No daily battle data available for histogram.</p>"
        
        # Find max battles for scaling
        max_battles = max((day['total_battles'] for day in daily_stats), default=1)
        
        # Create custom stacked histogram
        histogram_html = f'''
            <div class="chart-container {css_class}">
                <div class="stacked-histogram">
        '''
        
        for day in daily_stats:
            wins = day['wins']
            losses = day['losses']
            draws = day['draws']
            total = day['total_battles']
            date = day['date']
            
            # Calculate heights as percentages of max battles
            if total == 0:
                win_height = 0
                loss_height = 0
                draw_height = 3
            else:
                # Scale based on max battles, with minimum heights for visibility
                scale_factor = (total / max_battles) * 180  # 180px max height
                win_height = max((wins / total) * scale_factor, 3 if wins > 0 else 0)
                loss_height = max((losses / total) * scale_factor, 3 if losses > 0 else 0)
                draw_height = max((draws / total) * scale_factor, 3 if draws > 0 else 0)
            
            # Create tooltip
            tooltip = f"{date}: {wins}W/{losses}L/{draws}D" if total > 0 else f"{date}: No battles"
            
            histogram_html += f'''
                <div class="histogram-bar" title="{tooltip}">
                    <div class="bar-date">{date[-2:]}</div>
                    <div class="bar-stack">
            '''
            
            # Add segments from top to bottom: wins, draws, losses
            if win_height > 0:
                histogram_html += f'''
                    <div class="bar-segment bar-wins" style="height: {win_height}px;">
                        {f'<span class="segment-value">{wins}</span>' if wins > 0 else ''}
                    </div>
                '''
            
            if draw_height > 0:
                histogram_html += f'''
                    <div class="bar-segment bar-draws" style="height: {draw_height}px;">
                        {f'<span class="segment-value">{draws}</span>' if draws > 0 else ''}
                    </div>
                '''
            
            if loss_height > 0:
                histogram_html += f'''
                    <div class="bar-segment bar-losses" style="height: {loss_height}px;">
                        {f'<span class="segment-value">{losses}</span>' if losses > 0 else ''}
                    </div>
                '''
            
            # Handle empty days
            if total == 0:
                histogram_html += f'''
                    <div class="bar-segment bar-empty" style="height: {draw_height}px;">
                    </div>
                '''
            
            histogram_html += '''
                    </div>
                </div>
            '''
        
        histogram_html += '''
                </div>
            </div>
        '''
        
        # Add legend only if requested
        legend_html = ""
        if include_legend:
            legend_html = '''
            <div class="histogram-legend">
                <div class="legend-item">
                    <span class="legend-color legend-wins"></span>
                    <span>Wins</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color legend-losses"></span>
                    <span>Losses</span>
                </div>
            </div>
            '''
        
        return histogram_html + legend_html
    
    def generate_clan_rankings_html(self, clan_rankings: List[Dict], player_name: str) -> str:
        """Generate HTML for clan rankings with progression indicators"""
        if not clan_rankings:
            return "<p>No clan rankings data available.</p>"
        
        rankings_html = '<div class="clan-rankings">'
        
        for member in clan_rankings:
            is_current_player = member['name'] == player_name
            row_class = "current-player-ranking" if is_current_player else ""
            
            # Trophy change indicator
            trophy_change = member['trophy_change']
            trophy_indicator = ""
            if trophy_change > 0:
                trophy_indicator = f'<span class="trophy-up">+{trophy_change}</span>'
            elif trophy_change < 0:
                trophy_indicator = f'<span class="trophy-down">{trophy_change}</span>'
            else:
                trophy_indicator = '<span class="trophy-neutral">0</span>'
            
            # Donation change indicator
            donation_change = member['donation_change']
            donation_indicator = ""
            if donation_change > 0:
                donation_indicator = f'<span class="donation-up">+{donation_change}</span>'
            elif donation_change < 0:
                donation_indicator = f'<span class="donation-down">{donation_change}</span>'
            else:
                donation_indicator = '<span class="donation-neutral">0</span>'
            
            role_class = {
                'leader': 'leader',
                'coLeader': 'co-leader', 
                'elder': 'elder',
                'member': 'member'
            }.get(member['role'], 'member')
            
            role_display = member['role'].replace('coLeader', 'Co-Leader')
            
            rankings_html += f'''
                <div class="ranking-item {row_class}">
                    <div class="ranking-position">#{member['clan_rank']}</div>
                    <div class="ranking-info">
                        <div class="ranking-header">
                            <span class="member-name">{member['name']}</span>
                            <span class="role-{role_class} member-role">{role_display}</span>
                        </div>
                        <div class="ranking-stats">
                            <div class="stat-group">
                                <span class="trophy-count">🏆 {member['trophies']:,}</span>
                                {trophy_indicator}
                            </div>
                            <div class="stat-group">
                                <span class="donation-count">📦 {member['donations']}↑ {member['donations_received']}↓</span>
                                {donation_indicator}
                            </div>
                            <div class="last-seen-info">
                                🕒 {self.format_time_ago(member['last_seen'])}
                            </div>
                        </div>
                    </div>
                </div>
            '''
        
        rankings_html += '</div>'
        return rankings_html
    
    def generate_clan_deck_analytics_html(self, deck_analytics: Dict) -> str:
        """Generate HTML for clan deck analytics"""
        if not deck_analytics:
            return "<p>No clan deck data available yet. Data will appear after the next hourly collection.</p>"
        
        html = ""
        
        # Popular decks section - REMOVED: Most Popular Clan Decks section
        # popular_decks = deck_analytics.get('popular_decks', [])
        # if popular_decks:
        #     html += '<div class="analytics-section"><h3>🎯 Most Popular Clan Decks</h3>'
        #     for i, deck in enumerate(popular_decks[:5], 1):
        #         deck_cards_html = self.generate_deck_cards_html(deck['deck_cards'], show_names=False)
        #         html += f'''
        #             <div class="popular-deck-item">
        #                 <div class="deck-popularity">
        #                     <span class="deck-rank">#{i}</span>
        #                     <div class="deck-info">
        #                         <span class="usage-count">{deck['usage_count']} member{"s" if deck['usage_count'] > 1 else ""}</span>
        #                         <span class="users-list">{deck['users']}</span>
        #                     </div>
        #                 </div>
        #                 {deck_cards_html}
        #             </div>
        #         '''
        #     html += '</div>'
        
        # Favorite cards section
        favorite_cards = deck_analytics.get('favorite_cards', [])
        if favorite_cards:
            html += '<div class="analytics-section"><h3>⭐ Most Popular Favorite Cards</h3>'
            html += '<div class="favorite-cards-grid">'
            for card in favorite_cards[:8]:
                img_path = self.get_card_image_path(card['card_name'])
                html += f'''
                    <div class="favorite-card-item">
                        <img src="{img_path}" alt="{card['card_name']}" class="favorite-card-image">
                        <div class="favorite-card-info">
                            <span class="card-name">{card['card_name']}</span>
                            <span class="usage-count">{card['usage_count']} member{"s" if card['usage_count'] > 1 else ""}</span>
                        </div>
                    </div>
                '''
            html += '</div></div>'
        
        # Deck experimenters section - REMOVED: Moved to clan member activity table
        # deck_experimenters = deck_analytics.get('deck_experimenters', [])
        # if deck_experimenters:
        #     html += '<div class="analytics-section"><h3>🔄 Deck Experimenters</h3>'
        #     html += '<div class="experimenters-list">'
        #     for member in deck_experimenters[:10]:
        #         changes = member['deck_changes']
        #         if changes > 1:  # Only show people who have changed decks
        #             html += f'''
        #                 <div class="experimenter-item">
        #                     <span class="member-name">{member['name']}</span>
        #                     <span class="change-count">{changes} deck change{"s" if changes > 1 else ""}</span>
        #                 </div>
        #             '''
        #     html += '</div></div>'
        
        return html if html else "<p>No clan deck analytics available yet.</p>"
    
    def generate_card_level_analytics_html(self, analytics: Dict) -> str:
        """Generate HTML for card level and opponent analytics"""
        if not analytics:
            return "<p>Enhanced battle analytics not available yet.</p>"
        
        if 'message' in analytics:
            return f"<p style='color: #666; font-style: italic;'>{analytics['message']}</p>"
        
        html = ""
        
        # Player vs Opponent Level Analysis
        if 'avg_player_level' in analytics:
            html += '<div class="analytics-section">'
            html += '<h3>⚖️ Level Matchmaking Analysis</h3>'
            html += f'''
                <div class="level-comparison">
                    <div class="level-stat">
                        <span class="level-label">Your Avg Level:</span>
                        <span class="level-value">{analytics['avg_player_level']}</span>
                    </div>
                    <div class="level-stat">
                        <span class="level-label">Opponent Avg Level:</span>
                        <span class="level-value">{analytics['avg_opponent_level']}</span>
                    </div>
                </div>
                <div class="level-win-stats">
                    <div class="win-stat">
                        <span class="win-label">Wins with Level Advantage:</span>
                        <span class="win-count">{analytics['level_advantage_wins']}</span>
                    </div>
                    <div class="win-stat">
                        <span class="win-label">Wins with Level Disadvantage:</span>
                        <span class="win-count">{analytics['level_disadvantage_wins']}</span>
                    </div>
                </div>
            '''
            html += '</div>'
        
        # Opponent Clan Analysis
        opponent_clans = analytics.get('opponent_clans', [])
        if opponent_clans:
            html += '<div class="analytics-section">'
            html += '<h3>🏰 Opponent Clan Battles</h3>'
            html += '<div class="opponent-clans-list">'
            
            for clan in opponent_clans[:5]:  # Show top 5
                html += f'''
                    <div class="opponent-clan-item">
                        <div class="clan-name">{clan['name']}</div>
                        <div class="clan-stats">
                            <span class="battles-count">{clan['battles']} battles</span>
                            <span class="win-rate" style="color: {'#38a169' if clan['win_rate'] >= 50 else '#e53e3e'}">{clan['win_rate']}% win rate</span>
                        </div>
                    </div>
                '''
            
            html += '</div></div>'
        
        return html
    
    def generate_clan_favorite_cards_html(self, deck_analytics: Dict) -> str:
        """Generate HTML for just clan favorite cards (for main page)"""
        favorite_cards = deck_analytics.get('favorite_cards', [])
        if not favorite_cards:
            return "<p>No favorite card data available yet. <a href='clan.html' style='color: #4299e1;'>View full clan analytics →</a></p>"
        
        html = '<div class="favorite-cards-grid">'
        for card in favorite_cards[:6]:  # Show only top 6 on main page
            img_path = self.get_card_image_path(card['card_name'])
            html += f'''
                <div class="favorite-card-item">
                    <img src="{img_path}" alt="{card['card_name']}" class="favorite-card-image">
                    <div class="favorite-card-info">
                        <span class="card-name">{card['card_name']}</span>
                        <span class="usage-count">{card['usage_count']} member{"s" if card['usage_count'] > 1 else ""}</span>
                    </div>
                </div>
            '''
        html += '</div>'
        
        # Add link to full clan analytics
        html += '<div style="text-align: center; margin-top: 15px;">'
        html += '<a href="clan.html" style="color: #4299e1; text-decoration: none; font-weight: bold;">View Full Clan Analytics →</a>'
        html += '</div>'
        
        return html
    
    def generate_deck_list_html(self, decks: List[Dict], stats: Dict, player_tag: str = None, is_opponent_decks: bool = False) -> str:
        """Generate HTML for a list of decks"""
        if not decks:
            return "<p>Nenhum deck encontrado.</p>"
        
        html = ""
        user_deck_cards = None
        if player_tag:
            conn = sqlite3.connect(self.db_path, uri=True)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT deck_cards
                FROM battles
                WHERE player_tag = ? AND deck_cards IS NOT NULL AND deck_cards != ''
                ORDER BY battle_time DESC
                LIMIT 1
            """, (player_tag,))
            user_deck_row = cursor.fetchone()
            if user_deck_row:
                user_deck_cards = user_deck_row[0]
            conn.close()
        
        for i, deck in enumerate(decks, 1):
            trophy_color = "green" if deck['total_trophy_change'] >= 0 else "red"
            deck_cards_html = self.generate_deck_cards_html(deck['deck_cards'], show_names=False)
            
            # Identify deck owner
            deck_owner_info = ""
            conn = sqlite3.connect(self.db_path, uri=True)
            cursor = conn.cursor()
            
            if is_opponent_decks:
                # For opponent decks, get opponent info
                cursor.execute("""
                    SELECT DISTINCT b.opponent_name, b.opponent_tag
                    FROM battles b
                    WHERE b.opponent_deck_cards = ? AND b.opponent_deck_cards IS NOT NULL
                        AND b.player_tag = ?
                        AND b.result = 'defeat'
                    LIMIT 1
                """, (deck['deck_cards'], player_tag or ''))
                
                opponent_row = cursor.fetchone()
                if opponent_row:
                    opponent_name = opponent_row[0] or 'Oponente Desconhecido'
                    opponent_tag = opponent_row[1] or ''
                    deck_owner_info = f" - {opponent_name} ({opponent_tag}) [Oponente]"
            else:
                # Check if deck has member info (from same_level query)
                if 'member_tag' in deck and 'member_name' in deck:
                    # This is a clan member's deck from same_level query
                    member_name = deck.get('member_name', 'Membro do Clã')
                    member_tag = deck.get('member_tag', '')
                    deck_owner_info = f" - {member_name} ({member_tag}) [Clã]"
                else:
                    # For "Todos os Decks" tab, this should ONLY be user's decks
                    # So we verify it's the user's deck and show their name
                    if player_tag and stats:
                        # Verify this deck belongs to the user
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM battles 
                            WHERE deck_cards = ? 
                                AND player_tag = ?
                            LIMIT 1
                        """, (deck['deck_cards'], player_tag))
                        
                        is_user_deck = cursor.fetchone()[0] > 0
                        
                        if is_user_deck:
                            deck_owner_info = f" - {stats.get('name', 'Você')} ({player_tag})"
                        else:
                            # This shouldn't happen in "Todos os Decks" tab, but just in case
                            deck_owner_info = ""
                    else:
                        deck_owner_info = ""
            
            conn.close()
            
            # Adjust title and stats display for opponent decks
            if is_opponent_decks:
                title = f"#{i} - {deck['total_battles']} Derrotas{deck_owner_info}"
                
                # Get opponent game stats if available
                opponent_game_stats = deck.get('opponent_game_stats')
                if opponent_game_stats:
                    trophy_change_color = "green" if opponent_game_stats.get('total_trophy_change', 0) >= 0 else "red"
                    stats_html = f"""
                        <div class="deck-stats">
                            <span class="stat">🏆 {opponent_game_stats.get('total_battles', 0)} batalhas</span>
                            <span class="stat">✅ {opponent_game_stats.get('wins', 0)} vitórias</span>
                            <span class="stat">❌ {opponent_game_stats.get('losses', 0)} derrotas</span>
                            <span class="stat" style="color: {trophy_change_color}">📈 {int(opponent_game_stats.get('total_trophy_change', 0)):+d} trofeus</span>
                            <span class="stat">👑 {opponent_game_stats.get('avg_crowns', 0):.1f} coroas médias</span>
                        </div>
                    """
                else:
                    stats_html = f"""
                        <div class="deck-stats">
                            <span class="stat">🏆 {deck['total_battles']} vezes que me derrotou</span>
                            <span class="stat" style="color: #718096; font-size: 0.9em;">Dados do oponente não disponíveis</span>
                        </div>
                    """
            else:
                title = f"#{i} - {deck['win_rate']}% Taxa de Vitória{deck_owner_info}"
                
                # Check if this is a clan member's deck with member stats
                if 'member_tag' in deck and deck.get('member_total_battles', 0) > 0:
                    member_name = deck.get('member_name', 'Membro do Clã')
                    member_tag = deck.get('member_tag', '')
                    member_total = deck.get('member_total_battles', 0)
                    member_wins = deck.get('member_wins', 0)
                    member_losses = deck.get('member_losses', 0)
                    member_trophy_change = deck.get('member_trophy_change', 0)
                    member_avg_crowns = deck.get('member_avg_crowns', 0)
                    member_trophy_color = "green" if member_trophy_change >= 0 else "red"
                    
                    stats_html = f"""
                        <div class="deck-stats">
                            <span class="stat">🏆 {member_total} batalhas</span>
                            <span class="stat">✅ {member_wins} vitórias</span>
                            <span class="stat">❌ {member_losses} derrotas</span>
                            <span class="stat" style="color: {member_trophy_color}">📈 {int(member_trophy_change):+d} trofeus</span>
                            <span class="stat">👑 {member_avg_crowns:.1f} coroas médias</span>
                        </div>
                    """
                else:
                    stats_html = f"""
                        <div class="deck-stats">
                            <span class="stat">🏆 {deck['total_battles']} batalhas</span>
                            <span class="stat">✅ {deck['wins']} vitórias</span>
                            <span class="stat">❌ {deck['losses']} derrotas</span>
                            <span class="stat" style="color: {trophy_color}">📈 {int(deck['total_trophy_change']):+d} trofeus</span>
                            <span class="stat">👑 {deck['avg_crowns']:.1f} coroas médias</span>
                        </div>
                    """
            
            html += f"""
                <div class="deck-item">
                    <div class="deck-header">
                        <h3>{title}</h3>
                        {stats_html}
                    </div>
                    {deck_cards_html}
                </div>
            """
        
        return html
    


    def generate_deck_performance_with_tabs(self, decks: List[Dict], decks_same_level: List[Dict],
                                            decks_defeated_by: List[Dict], repeated_opponents: List[Dict],
                                            stats: Dict, player_tag: str = None, lethal_decks_html: str = "") -> str:
        """Generate HTML for deck performance section with 4 tabs: 
        Oponentes Repetidos + Meus Decks da Semana + Decks Inimigos Letais + Mais Vencedores"""

        # Aba 1: Meus Decks da Semana - le CSVs diarios
        weekly_data = self.get_weekly_decks_from_csv()
        weekly_decks_html = self.generate_weekly_decks_html(weekly_data)

        # Aba 2: Oponentes Repetidos - usa estatisticas consolidadas do cache CSV
        csv_repeated = self.get_repeated_opponents_stats(player_tag=player_tag)
        repeated_opponents_html = self.generate_repeated_opponents_html(csv_repeated)
        
        # Aba 4: Decks Mais Vencedores (Global/Clã)
        winning_data = self.get_top_winning_decks_weekly()
        winning_decks_html = self.generate_winning_decks_html(winning_data)

        return f"""
        <div class="deck-tabs-container">
            <div class="deck-tabs">
                <button class="tab-button active" onclick="switchDeckTab(event, 'repeated-opponents')">Oponentes Repetidos</button>
                <button class="tab-button" onclick="switchDeckTab(event, 'weekly-decks')">Meus Decks da Semana</button>
                <button class="tab-button" onclick="switchDeckTab(event, 'lethal-decks')">Decks Inimigos Letais</button>
                <button class="tab-button" onclick="switchDeckTab(event, 'winning-decks')">Melhores Decks (Semana)</button>
            </div>

            <div id="tab-repeated-opponents" class="tab-content active">
                {repeated_opponents_html if repeated_opponents_html else '<p>Nenhum oponente encontrado que voce enfrentou mais de uma vez.</p>'}
            </div>

            <div id="tab-weekly-decks" class="tab-content">
                {weekly_decks_html}
            </div>
            
            <div id="tab-lethal-decks" class="tab-content">
                {lethal_decks_html if lethal_decks_html else '<p>Analise de decks letais pendente de mais derrotas.</p>'}
            </div>
            
            <div id="tab-winning-decks" class="tab-content">
                {winning_decks_html}
            </div>
        </div>
        {self.generate_dashboard_scripts()}
        """
    def load_all_data_rows(self) -> List[Dict]:
        """Carrega e unifica dados de todas as fontes disponíveis via CSV diretamente."""
        logger.info("Carregando dados das batalhas de todos os CSVs disponíveis")
        
        # Carrega todas as batalhas usando o helper
        battles_list = self._load_all_battles_from_csv(self.player_tag)
        
        all_data = []
        for b in battles_list:
            battle_time = b.get('battle_time', '')
            dt = self._parse_dt(battle_time)
            result = (b.get('result') or '').strip().lower()
            opponent_tag = b.get('opponent_tag', '')
            player_deck = b.get('deck_cards', '')
            opponent_deck = b.get('opponent_deck_cards', '')

            all_data.append({
                'battle_time': battle_time,
                'dt': dt,
                'opponent_name': b.get('opponent_name', 'Oponente'),
                'opponent_tag': opponent_tag,
                'tag_oponente': opponent_tag,
                'result': result,
                'resultado': result,
                'deck_cards': player_deck,
                'deck_jogador': player_deck,
                'opponent_deck_cards': opponent_deck,
                'deck_oponente': opponent_deck,
                'opponent_clan_name': b.get('opponent_clan_name', ''),
                'nome_oponente': b.get('opponent_name', 'Oponente')
            })
            
        return all_data


    def _parse_dt(self, b_time_str: str):
        from datetime import datetime
        if not b_time_str: return None
        # Formatos comuns nos CSVs do projeto
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y%m%dT%H%M%S.000Z']:
            try:
                return datetime.strptime(b_time_str, fmt)
            except ValueError: continue
        return None

    def get_weekly_decks_from_csv(self) -> List[Dict]:
        """Consolida os 10 melhores decks dos últimos 7 dias usando todas as fontes."""
        from datetime import datetime, timedelta
        all_rows = self.load_all_data_rows()
        if not all_rows: return []
            
        today = datetime.now()
        seven_days_ago = today - timedelta(days=7)
        deck_stats = {}

        for row in all_rows:
            dt = row.get('dt') or self._parse_dt(row.get('battle_time', ''))
            if not dt:
                continue
            is_recent = dt >= seven_days_ago
            cards_raw = row.get('deck_jogador') or row.get('deck_cards')
            if not cards_raw: continue
            
            # Normaliza o deck para garantir que a ordem não afete
            cards = self._get_canonical_deck(cards_raw)
            
            if cards not in deck_stats:
                deck_stats[cards] = {
                    'deck_cards': cards, 
                    'wins': 0, 
                    'losses': 0, 
                    'total': 0, 
                    'battles': [], 
                    'recent_total': 0,
                    'last_played': dt
                }
            
            if is_recent:
                deck_stats[cards]['recent_total'] += 1
            
            deck_stats[cards]['total'] += 1
            if dt > deck_stats[cards]['last_played']:
                deck_stats[cards]['last_played'] = dt
                
            res = (row.get('resultado') or row.get('result') or '').strip().lower()
            if res in ['vitoria', 'victory', 'vitória']: deck_stats[cards]['wins'] += 1
            elif res in ['derrota', 'defeat']: deck_stats[cards]['losses'] += 1
            
            if len(deck_stats[cards]['battles']) < 30:
                deck_stats[cards]['battles'].append({
                    'resultado': res, 
                    'data': dt.strftime('%d/%m %H:%M'),
                    'dt_obj': dt,
                    'my_deck': cards_raw,
                    'opp_deck': row['deck_oponente']
                })

        # Fallback se não houver NADA na última semana
        use_fallback = not any(d['recent_total'] > 0 for d in deck_stats.values())
        
        final_list = []
        for d in deck_stats.values():
            if not use_fallback and d['recent_total'] == 0:
                continue
            
            # Ordenar batalhas do deck por data
            d['battles'].sort(key=lambda x: x['dt_obj'], reverse=True)
            d['win_rate'] = round((d['wins'] / d['total'] * 100), 1) if d['total'] > 0 else 0
            final_list.append(d)
            
        # ORDENAÇÃO: Decks usados RECENTEMENTE e com maior volume na semana no topo
        final_list.sort(key=lambda x: (x['recent_total'], x['win_rate'], x['total']), reverse=True)
        return final_list[:10]

    def get_top_winning_decks_weekly(self) -> List[Dict]:
        """Consolida os decks com maior taxa de vitória na semana priorizando dados mundiais do CSV."""
        # 1. Tenta carregar do arquivo meta global separado
        meta_global_path = os.path.join(self.data_csv_dir, 'decks_meta_global.csv')
        if os.path.exists(meta_global_path):
            try:
                meta_list = []
                with open(meta_global_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        meta_list.append({
                            'deck_cards': row['deck_cards'],
                            'total': int(row.get('total', 0)),
                            'wins': int(row.get('wins', 0)),
                            'losses': int(row.get('losses', 0)),
                            'win_rate': float(row.get('win_rate', 0)),
                            'source': row.get('source', 'Global Meta')
                        })
                if meta_list:
                    return meta_list[:5]
            except Exception as e:
                logger.error(f"Erro ao ler decks_meta_global.csv: {e}")

        # 2. Fallback para lógica de clã se o arquivo global não existir
        from datetime import datetime, timedelta
        global_battles = self._load_all_battles_from_csv(player_tag='#YVJR0JLY')
        if not global_battles: return []
            
        today = datetime.now()
        seven_days_ago = today - timedelta(days=7)
        deck_stats = {}

        for row in global_battles:
            battle_time = row.get('battle_time', '')
            dt = self._parse_dt(battle_time)
            if not dt or dt < seven_days_ago:
                continue
            
            cards_raw = row.get('deck_cards') or row.get('deck_jogador')
            if not cards_raw or cards_raw == 'N/D': continue
            
            cards = self._get_canonical_deck(cards_raw)
            
            if cards not in deck_stats:
                deck_stats[cards] = {
                    'deck_cards': cards, 
                    'wins': 0, 
                    'losses': 0, 
                    'draws': 0,
                    'total': 0,
                    'win_rate': 0,
                    'battles': []
                }
            
            deck_stats[cards]['total'] += 1
            res = str(row.get('resultado') or row.get('result') or '').strip().lower()
            if res in ['vitoria', 'victory', 'vitória']: 
                deck_stats[cards]['wins'] += 1
            elif res in ['derrota', 'defeat']: 
                deck_stats[cards]['losses'] += 1
            else:
                deck_stats[cards]['draws'] += 1
            
            deck_stats[cards]['battles'].append({
                'result': res,
                'my_deck': cards_raw,
                'opp_deck': row.get('deck_oponente') or row.get('opponent_deck_cards', ''),
                'battle_time': row.get('battle_time', ''),
                'modo_jogo': row.get('modo_jogo', 'Batalha')
            })

        final_list = []
        for d in deck_stats.values():
            if d['total'] >= 1:
                d['win_rate'] = round((d['wins'] / d['total'] * 100), 1)
                # Ordena batalhas por tempo
                d['battles'].sort(key=lambda x: self._parse_dt(x['battle_time']) or datetime.min, reverse=True)
                final_list.append(d)
            
        final_list.sort(key=lambda x: (x['win_rate'], x['total']), reverse=True)
        return final_list[:10]

    def generate_weekly_decks_html(self, weekly_data: List[Dict]) -> str:
        """Gera HTML da aba 'Meus Decks' com timeline interativa e preview."""
        if not weekly_data: return '<p>Nenhum dado encontrado para os últimos 7 dias.</p>'
        import json, urllib.parse
        html = '<div class="cr-decks-list">'
        for i, deck in enumerate(weekly_data, 1):
            total = deck['total']
            win_rate = deck['win_rate']
            wins_pct = round((deck['wins']/total*100), 1) if total > 0 else 0
            losses_pct = round((deck['losses']/total*100), 1) if total > 0 else 0
            draws_pct = round(max(0, 100 - wins_pct - losses_pct), 1)
            deck_id = f"deck-{i}"
            
            cards_list = [c.strip() for c in deck['deck_cards'].replace(' | ', '|').split('|')]
            metrics = self._get_deck_metrics(deck['deck_cards'])
            
            # Pega o primeiro combate para extrair o modo de jogo
            first_battle = deck['battles'][0] if deck['battles'] else {}
            game_mode = first_battle.get('modo_jogo', 'Batalha')
            
            grid_h = f'''
            <div class="cr-deck-side" style="flex:1; width:100%;">
                <div class="cr-game-mode-badge" style="margin-bottom:10px;">{game_mode}</div>
                <div class="cr-grid-4x2">
                    {"".join(f'<div class="cr-card-wrap" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img" loading="lazy"></div>' for c in cards_list)}
                </div>
                <div class="cr-deck-metrics" style="margin-top:10px; justify-content:center;">
                    <div class="cr-metric-item"><span class="cr-elixir-icon">💧</span> {metrics["avg"]}</div>
                    <div class="cr-metric-item"><span class="cr-elixir-icon">🔄</span> {metrics["cycle"]}</div>
                </div>
            </div>'''

            # Timeline com data e hora
            timeline_h = ""
            for idx, b in enumerate(deck['battles'][:15]):
                # Calcula métricas para o JSON
                my_m = self._get_deck_metrics(b['my_deck'])
                opp_m = self._get_deck_metrics(b['opp_deck'])
                
                b_json = urllib.parse.quote(json.dumps({
                    'my_deck': b['my_deck'], 
                    'opp_deck': b['opp_deck'],
                    'player_name': self.players_cache[0].get('name', 'Jogador') if self.players_cache else 'Jogador',
                    'opp_name': b.get('nome_oponente', 'Oponente'),
                    'my_metrics': {**my_m, 'leaked': b.get('elixir_vazado_jogador', 0), 'level': b.get('nivel_torre_jogador', 14), 'hp': self._get_tower_hp(b.get('nivel_torre_jogador', 14))},
                    'opp_metrics': {**opp_m, 'leaked': b.get('elixir_vazado_oponente', 0), 'level': b.get('nivel_oponente', 14), 'hp': self._get_tower_hp(b.get('nivel_oponente', 14))},
                    'game_mode': b.get('modo_jogo', 'Batalha'),
                    'crowns': b.get('coroas_jogador', 0),
                    'opponent_crowns': b.get('coroas_oponente', 0),
                    'trophy_change': b.get('trofeus', 0)
                }))
                active = "box-shadow: 0 0 0 3px #4299e1; transform: scale(1.1);" if idx == 0 else ""
                
                # Formata data para a timeline usando o objeto datetime
                d_short = b['dt_obj'].strftime('%d/%m')
                h_short = b['dt_obj'].strftime('%H:%M')
                
                res = b['resultado'].lower()
                cor = '#48bb78' if res in ['vitoria','victory', 'vitória'] else ('#f56565' if res in ['derrota','defeat'] else '#ed8936')
                ic = 'V' if res in ['vitoria','victory', 'vitória'] else ('D' if res in ['derrota','defeat'] else 'E')
                
                timeline_h += f'''
                <div style="display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;" onclick="updateBattlePreview('{deck_id}', {idx}, '{b_json}')">
                    <span class="cr-battle-badge" style="background:{cor};{active}" title="{b["data"]}">{ic}</span>
                    <span style="font-size:0.6em;color:#4a5568;font-weight:bold;">{d_short}</span>
                </div>'''

            # Preview VS aprimorado
            my_deck_init = first_battle.get('my_deck', deck['deck_cards'])
            opp_deck_init = first_battle.get('opp_deck', '')
            
            def get_preview_grid(d_str, side_class, p_name="Jogador", is_opponent=False):
                if not d_str: return f'<div class="{side_class} cr-empty-grid">N/D</div>'
                cards = [c.strip() for c in d_str.replace(' | ','|').split('|')]
                metrics = self._get_deck_metrics(d_str)
                
                # Torres locais
                tower_img = "assets/images/towers/opp_tower.png" if is_opponent else "assets/images/towers/player_tower.png"
                fallback_tower = "https://static.wikia.nocookie.net/character-catalogue/images/c/cf/Tower_Princess.png/revision/latest?cb=20231217222258"
                
                # Métricas extras
                leaked = metrics.get('leaked', 0)
                t_level = metrics.get('level', 14)
                t_hp = metrics.get('hp', self._get_tower_hp(t_level))
                
                grid_html = f'''
                    <div class="cr-grid-4x2-premium">
                        {"".join(f'<div class="cr-card-wrap-premium" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img"></div>' for c in cards)}
                    </div>'''
                
                metrics_html = f'''
                    <div class="cr-deck-metrics-premium">
                        <div class="cr-metric-item-p" title="Media Elixir"><span class="cr-metric-icon">💧</span> {metrics["avg"]}</div>
                        <div class="cr-metric-item-p" title="Ciclo 4 Cartas"><span class="cr-metric-icon">🔄</span> {metrics["cycle"]}</div>
                        <div class="cr-metric-item-p" title="Elixir Vazado" style="color: {'#f56565' if float(leaked) > 0 else '#48bb78'}"><span class="cr-metric-icon">🚫</span> {leaked}</div>
                    </div>'''
                
                return f'''
                    <div class="{side_class} cr-deck-side">
                        <div class="cr-player-header-premium">
                            <div class="cr-player-name-premium">{p_name}</div>
                            <div class="cr-clan-name-premium">Analytics Squad</div>
                        </div>
                        <div class="cr-tower-container-premium">
                            <img src="{tower_img}" class="cr-tower-img-premium" onerror="this.src='{fallback_tower}'">
                            <div class="cr-tower-info-premium">HP {t_hp} (Lvl {t_level})</div>
                        </div>
                        {grid_html}
                        {metrics_html}
                    </div>'''

            wr_c = '#48bb78' if win_rate >= 50 else '#f56565'
            html += f'''
            <div class="cr-deck-card">
                <div class="cr-deck-header">
                    <div class="cr-deck-meta">
                        <span class="cr-deck-rank">#{i}</span>
                        <span class="cr-deck-label">WR: {win_rate}% ({deck['recent_total']} partidas na semana)</span>
                    </div>
                    <span class="cr-wr-badge" style="background:{wr_c};">{total} Total</span>
                </div>
                <div class="cr-progress-bar"><div class="cr-bar-wins" style="width:{wins_pct}%;"></div><div class="cr-bar-draws" style="width:{draws_pct}%;"></div><div class="cr-bar-losses" style="width:{losses_pct}%;"></div></div>
                <div class="cr-deck-body">
                    {grid_h}
                    <div class="cr-stats-panel" style="flex:1;">
                        <div id="preview-{deck_id}" class="cr-battle-preview">
                            <div class="cr-battle-header-premium">
                                <div class="cr-battle-result-label">VITÓRIA</div>
                                <div class="cr-battle-score-premium">1 - 0</div>
                                <div class="cr-battle-mode-label">{first_battle.get('game_mode', 'Batalha')}</div>
                            </div>
                            <div class="cr-vs-row-premium">
                                {get_preview_grid(my_deck_init, 'my-deck-side', p_name=self.players_cache[0].get('name', 'Jogador') if self.players_cache else 'Jogador')}
                                <div class="cr-vs-divider-vertical">vs</div>
                                {get_preview_grid(opp_deck_init, 'opp-deck-side', p_name="Oponente", is_opponent=True)}
                            </div>
                        </div>
                        <div class="cr-battles-timeline"><div class="cr-timeline-badges timeline-{deck_id}" style="display:flex; gap:8px; overflow-x:auto; padding:5px 0;">{timeline_h}</div></div>
                    </div>
                </div>
            </div>'''
        return html + '</div>'

    def generate_winning_decks_html(self, winning_data: List[Dict]) -> str:
        """Gera HTML para a aba de melhores decks da semana (Meta/Global)."""
        if not winning_data: return '<div class="cr-empty-state">Dados globais insuficientes para o Top Vencedores.</div>'
        
        html = '<div class="cr-decks-list">'
        for i, deck in enumerate(winning_data, 1):
            total = deck['total']
            win_rate = deck['win_rate']
            
            cards_list = [c.strip() for c in deck['deck_cards'].split(' | ')]
            metrics = self._get_deck_metrics(deck['deck_cards'])
            
            grid_h = f'''
            <div class="cr-deck-side" style="flex:1; width:100%;">
                <div class="cr-grid-4x2">
                    {"".join(f'<div class="cr-card-wrap" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img" loading="lazy"></div>' for c in cards_list)}
                </div>
                <div class="cr-deck-metrics" style="margin-top:10px; justify-content:center;">
                    <div class="cr-metric-item"><span class="cr-elixir-icon">💧</span> {metrics["avg"]}</div>
                    <div class="cr-metric-item"><span class="cr-elixir-icon">🔄</span> {metrics["cycle"]}</div>
                </div>
            </div>'''

            source_label = deck.get('source', 'Dados do Clã')
            is_global = source_label == 'Global Meta'
            game_mode = "Ranked" if is_global else "Guerra/Desafio"
            
            wr_c = '#48bb78' if win_rate >= 55 else ('#4299e1' if win_rate >= 50 else '#718096')
            html += f'''
            <div class="cr-deck-card" style="border-top: 4px solid {wr_c};">
                <div class="cr-deck-header">
                    <div class="cr-deck-meta">
                        <span class="cr-deck-rank" style="background:{wr_c};">#{i} {source_label.upper()}</span>
                        <span class="cr-deck-label">Taxa de Vitoria: {win_rate}%</span>
                    </div>
                    <span class="cr-wr-badge" style="background:#edf2f7; color:#4a5568; border:1px solid #e2e8f0;">{total} Partidas</span>
                </div>
                <div class="cr-deck-body">
                    <div class="cr-mode-badge" style="background:{wr_c};">{game_mode}</div>
                    {grid_h}
                    <div class="cr-stats-panel" style="flex:1; display:flex; align-items:center; justify-content:center;">
                        <div style="text-align:center; padding:10px; background:#f7fafc; border-radius:12px; width:100%;">
                            <div style="font-size:0.7em; color:#718096; font-weight:700; text-transform:uppercase; margin-bottom:5px;">Performance Global</div>
                            <div style="font-size:1.5em; font-weight:900; color:{wr_c};">{win_rate}%</div>
                            <div style="font-size:0.6em; color:#a0aec0;">Baseado em dados {"mundiais" if is_global else "de todos os jogadores do cla"}</div>
                        </div>
                    </div>
                </div>
            </div>'''
        return html + '</div>'

    def get_repeated_opponents_from_csv(self) -> List[Dict]:
        """Agrupa oponentes repetidos usando todas as fontes de dados disponíveis."""
        all_rows = self.load_all_data_rows()
        if not all_rows: return []
            
        opp_stats = {}
        for b in all_rows:
            tag = b.get('tag_oponente') or b.get('opponent_tag')
            if not tag: continue
            
            if tag not in opp_stats:
                opp_stats[tag] = {
                    'tag': tag, 
                    'nome': b.get('nome_oponente') or b.get('opponent_name', 'Oponente'), 
                    'total': 0, 
                    'wins': 0, 
                    'losses': 0, 
                    'battles': [], 
                    'last_deck': b.get('deck_oponente') or b.get('opponent_deck_cards', '')
                }
            
            opp_stats[tag]['total'] += 1
            res = (b.get('resultado') or b.get('result') or '').strip().lower()
            if res in ['vitoria', 'victory']: opp_stats[tag]['wins'] += 1
            elif res in ['derrota', 'defeat']: opp_stats[tag]['losses'] += 1
            
            dt = b.get('dt') or self._parse_dt(b.get('battle_time', ''))
            if not dt:
                continue
            d_display = dt.strftime('%d/%m %H:%M')
                
            opp_stats[tag]['battles'].append({
                'resultado': res, 
                'data_str': d_display,
                'my_deck': b.get('deck_jogador') or b.get('deck_cards', ''),
                'opp_deck': b.get('deck_oponente') or b.get('opponent_deck_cards', ''),
                'dt_obj': dt # Para ordenação posterior
            })
            if b.get('deck_oponente') or b.get('opponent_deck_cards'):
                opp_stats[tag]['last_deck'] = b.get('deck_oponente') or b.get('opponent_deck_cards')

        # Filtra quem apareceu > 1 vez
        repeated = []
        for o in opp_stats.values():
            if o['total'] > 1:
                # Ordena as batalhas por data (mais recente primeiro)
                o['battles'].sort(key=lambda x: x['dt_obj'], reverse=True)
                # Define a data da última batalha para ordenação global
                o['last_battle_dt'] = o['battles'][0]['dt_obj']
                repeated.append(o)

        # ORDENAÇÃO: Oponentes enfrentados RECENTEMENTE no topo
        repeated.sort(key=lambda x: x['last_battle_dt'], reverse=True)
        return repeated[:20]

    def generate_dashboard_scripts(self) -> str:
        """Gera os scripts globais necessários para a interatividade do dashboard."""
        return r"""
        <script>
        function updateBattlePreview(deckId, battleIdx, battleDataJson) {
            try {
                const data = JSON.parse(decodeURIComponent(battleDataJson));
                const previewContainer = document.getElementById('preview-' + deckId);
                if (!previewContainer) return;
                
                const myDeckHtml = getMiniGridJS(data.my_deck, 'my-deck-side', data.player_name, data.my_metrics);
                const oppDeckHtml = getMiniGridJS(data.opp_deck, 'opp-deck-side', data.opp_name, data.opp_metrics);
                
                const score = `${data.crowns || 0} - ${data.opponent_crowns || 0}`;
                const tropChange = data.trophy_change || 0;
                const tropColor = tropChange > 0 ? '#48bb78' : (tropChange < 0 ? '#f56565' : '#718096');
                const tropSign = tropChange > 0 ? '+' : '';
                const tropText = tropChange !== 0 ? tropSign + tropChange : '';

                previewContainer.innerHTML = `
                    <div class="cr-vs-row-premium-v2">
                        <div class="cr-battle-score-header-premium">
                            <div class="cr-mode-tag-premium">${data.game_mode || 'Batalha'}</div>
                            <div class="cr-score-display-premium">
                                <span class="cr-score-val">${score}</span>
                                <span class="cr-trophy-change-p" style="color: ${tropColor}">${tropText}</span>
                            </div>
                        </div>
                        <div class="cr-vs-decks-row-premium">
                            ${myDeckHtml}
                            <div class="cr-vs-center-divider">VS</div>
                            ${oppDeckHtml}
                        </div>
                    </div>
                `;
                
                const timeline = document.querySelector('.timeline-' + deckId);
                if (timeline) {
                    timeline.querySelectorAll('.cr-battle-badge').forEach((b, i) => {
                        if (i === battleIdx) {
                            b.style.boxShadow = '0 0 0 3px #4299e1';
                            b.style.transform = 'scale(1)';
                        }
                    });
                }
            } catch(e) { console.error("Error updating preview:", e); }
        }
        
        function getMiniGridJS(deckStr, sideClass, playerName, metrics) {
            if (!deckStr) return `<div class="${sideClass} cr-empty-grid">N/D</div>`;
            const cards = deckStr.replace(/ \| /g, '|').split('|');
            const playerTower = "assets/images/towers/player_tower.png";
            const oppTower = "assets/images/towers/opp_tower.png";
            const towerImg = sideClass.includes('my') ? playerTower : oppTower;
            
            const cardsHtml = cards.map(c => {
                const name = c.trim();
                const slug = name.toLowerCase().replace(/\s+/g, '-').replace(/\./g, '');
                return `<div class="cr-card-wrap-premium" title="${name}"><img src="https://royaleapi.github.io/cr-api-assets/cards/${slug}.png" class="cr-card-img" onerror="this.src='https://royaleapi.com/static/img/cards-150/${slug}.png'" loading="lazy"></div>`;
            }).join('');
            
            const avg = metrics ? metrics.avg : '--';
            const cycle = metrics ? metrics.cycle : '--';
            const leaked = metrics ? (metrics.leaked || 0) : 0;
            const tLevel = metrics ? (metrics.level || 14) : 14;
            const tHP = metrics ? (metrics.hp || '--') : '--';
            const leakedColor = leaked > 0 ? '#f56565' : '#48bb78';

            return `
                <div class="cr-deck-side ${sideClass}">
                    <div class="cr-player-header-premium">
                        <div class="cr-player-name-premium">${playerName}</div>
                        <div class="cr-clan-name-premium">Analytics Squad</div>
                    </div>
                    <div class="cr-tower-container-premium">
                        <img src="${towerImg}" class="cr-tower-img-premium" onerror="this.src='https://static.wikia.nocookie.net/character-catalogue/images/c/cf/Tower_Princess.png/revision/latest?cb=20231217222258'">
                        <div class="cr-tower-info-premium">HP ${tHP} (Lvl ${tLevel})</div>
                    </div>
                    <div class="cr-grid-4x2-premium">
                        ${cardsHtml}
                    </div>
                    <div class="cr-deck-metrics-premium">
                        <div class="cr-metric-item-p" title="Media Elixir"><span class="cr-metric-icon">💧</span> ${avg}</div>
                        <div class="cr-metric-item-p" title="Ciclo 4 Cartas"><span class="cr-metric-icon">🔄</span> ${cycle}</div>
                        <div class="cr-metric-item-p" title="Elixir Vazado" style="color: ${leakedColor}"><span class="cr-metric-icon">🚫</span> ${leaked}</div>
                    </div>
                </div>`;
        }

        function switchDeckTab(event, tabName) {
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            if (event) event.currentTarget.classList.add('active');
        }

        // Rotação diária de background
        document.addEventListener('DOMContentLoaded', () => {
            const bgs = [
                "assets/backgrounds/bg1.jpg",
                "assets/backgrounds/bg2.jpg",
                "assets/backgrounds/bg3.jpg",
                "https://images2.alphacoders.com/112/thumb-1920-1124066.jpg",
                "https://wallpapers.com/images/featured/clash-royale-v0d8p9p3f2j7j0u0.jpg",
                "https://images5.alphacoders.com/687/687588.jpg"
            ];
            const day = new Date().getDate();
            const selectedBg = bgs[day % bgs.length];
            document.body.style.backgroundImage = `url('${selectedBg}')`;
            
            // Fallback para imagem remota se a local falhar
            if (selectedBg.startsWith('assets/')) {
                const img = new Image();
                img.onerror = () => {
                    document.body.style.backgroundImage = "url('https://images2.alphacoders.com/112/thumb-1920-1124066.jpg')";
                };
                img.src = selectedBg;
            }
        });
        </script>
        """

    def generate_repeated_opponents_html(self, opponents: List[Dict]) -> str:
        """Gera HTML para oponentes repetidos no estilo Premium com Preview de Batalha e Categorização de Rivalidade."""
        if not opponents: return '<div class="cr-empty-state">Nenhum oponente repetido encontrado no histórico recente.</div>'
        
        # Correção: Obtém o nome do jogador do cache para evitar erro de variável não definida
        player_name = next((p.get('name', 'Jogador') for p in self.players_cache if p.get('player_tag') == self.player_tag), 'Jogador')
        
        html = '<div class="cr-decks-list">'
        import json
        import urllib.parse
        
        for i, opp in enumerate(opponents, 1):
            tag_clean = opp['opponent_tag'].replace('#', '')
            wins = opp['user_wins']
            losses = opp['user_losses']
            draws = opp['user_draws']
            total = opp['total_battles']
            wr = opp['user_win_rate']
            category = opp['category']
            cat_class = opp['category_class']
            
            # Cálculo de porcentagens para a barra de progresso (baseado em contagens reais)
            w_p = round((wins/total*100),1) if total > 0 else 0
            l_p = round((losses/total*100),1) if total > 0 else 0
            d_p = round((draws/total*100),1) if total > 0 else 0
            
            # Ajuste visual para que a soma não exceda 100% se houver arredondamentos, 
            # mas mantendo a proporção real de empates
            
            # Pega a batalha mais recente
            stats = opp['stats']
            last_b = stats[0] if stats else {}
            my_deck_last = last_b.get('my_deck', '')
            opp_deck_last = last_b.get('opp_deck', '')
            last_game_mode = last_b.get('game_mode', 'Batalha')
            last_score = f"{last_b.get('crowns', 0)} - {last_b.get('opponent_crowns', 0)}"
            last_trophy = last_b.get('trophy_change', 0)
            trophy_color = "#48bb78" if last_trophy > 0 else ("#f56565" if last_trophy < 0 else "#718096")
            trophy_sign = "+" if last_trophy > 0 else ""
            
            def get_deck_side_html(d_str, side_class, p_name, is_opponent=False):
                if not d_str: return f'<div class="{side_class} cr-empty-grid">N/D</div>'
                cards = [c.strip() for c in d_str.replace(' | ','|').split('|')]
                metrics = self._get_deck_metrics(d_str)
                
                # Torres locais se existirem
                tower_img = "assets/images/towers/opp_tower.png" if is_opponent else "assets/images/towers/player_tower.png"
                fallback_tower = "https://static.wikia.nocookie.net/character-catalogue/images/c/cf/Tower_Princess.png/revision/latest?cb=20231217222258"
                
                tower_html = f'<img src="{tower_img}" class="cr-tower-img-premium" onerror="this.src=\'{fallback_tower}\'">'
                
                grid_html = f'''
                    <div class="cr-grid-4x2-premium">
                        {"".join(f'<div class="cr-card-wrap-premium" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img"><div class="cr-card-level">Nível 16</div></div>' for c in cards)}
                    </div>'''
                
                metrics_html = f'''
                    <div class="cr-deck-metrics-premium">
                        <div class="cr-metric-item-p"><span class="cr-metric-icon">💧</span> {metrics["avg"]}</div>
                        <div class="cr-metric-item-p"><span class="cr-metric-icon">🔄</span> {metrics["cycle"]}</div>
                        <div class="cr-metric-item-p"><span class="cr-metric-icon">⚡</span> 1.8</div>
                    </div>'''
                
                return f'''
                <div class="cr-deck-side {side_class}">
                    <div class="cr-player-header-premium" style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 10px;">
                        {tower_html if not is_opponent else ""}
                        <div>
                            <div class="cr-player-name-premium">{p_name}</div>
                            <div class="cr-clan-name-premium">Analytics Squad</div>
                        </div>
                        {tower_html if is_opponent else ""}
                    </div>
                    {grid_html}
                    {metrics_html}
                </div>'''

            preview_html = f"""
            <div id="preview-{tag_clean}" class="cr-battle-preview">
                <div class="cr-battle-score-header-premium" style="text-align: center; margin-bottom: 25px; display: flex; flex-direction: column; align-items: center; gap: 10px;">
                    <div class="cr-game-mode-badge" style="margin-bottom: 0;">{last_game_mode}</div>
                    <div class="cr-score-display-premium" style="background: rgba(15, 23, 42, 0.8); padding: 12px 35px; border-radius: 50px; border: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; gap: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                        <div class="cr-score-val" style="font-size: 2.5em; font-weight: 900; color: #fff; letter-spacing: 5px;">{last_score}</div>
                        <div class="cr-trophy-change-vs" style="color: {trophy_color}; font-size: 1.3em; font-weight: 800;">{trophy_sign}{last_trophy if last_trophy != 0 else ''}</div>
                    </div>
                </div>
                <div class="cr-vs-row" style="align-items: flex-start; gap: 20px;">
                    {get_deck_side_html(my_deck_last, 'my-deck-side', player_name)}
                    <div class="cr-vs-divider-vertical" style="align-self: center; opacity: 0.2; font-size: 2em; font-weight: 900;">VS</div>
                    {get_deck_side_html(opp_deck_last, 'opp-deck-side', opp['opponent_name'], is_opponent=True)}
                </div>
            </div>
            """
            
            timeline = ""
            for idx, b in enumerate(stats[:15]):
                res = b['result'].lower()
                bt = b.get('battle_time', '')
                dt_obj = self._parse_dt(bt)
                if dt_obj:
                    d_f = dt_obj.strftime('%d/%m')
                    h_f = dt_obj.strftime('%H:%M')
                else:
                    d_f = '--/--'
                    h_f = '--:--'
                
                cor = '#48bb78' if res in ['vitoria','victory'] else ('#f56565' if res in ['derrota','defeat'] else '#ed8936')
                ic = 'V' if res in ['vitoria','victory'] else ('D' if res in ['derrota','defeat'] else 'E')
                
                # Dados completos para o JS
                my_metrics = self._get_deck_metrics(b['my_deck'])
                opp_metrics = self._get_deck_metrics(b['opp_deck'])
                
                b_data = urllib.parse.quote(json.dumps({
                    'my_deck': b['my_deck'],
                    'opp_deck': b['opp_deck'],
                    'player_name': player_name,
                    'opp_name': opp['opponent_name'],
                    'game_mode': b.get('game_mode', 'Batalha'),
                    'crowns': b.get('crowns', 0),
                    'opponent_crowns': b.get('opponent_crowns', 0),
                    'trophy_change': b.get('trophy_change', 0),
                    'my_metrics': my_metrics,
                    'opp_metrics': opp_metrics
                }))
                
                active_style = "box-shadow: 0 0 0 3px #4299e1; transform: scale(1.1);" if idx == 0 else ""
                
                timeline += f'''
                <div style="display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;transition:all 0.2s;" onclick="updateBattlePreview('{tag_clean}', {idx}, '{b_data}')" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
                    <span class="cr-battle-badge" style="background:{cor};{active_style}">{ic}</span>
                    <span style="font-size:0.65em;color:#718096;font-weight:700;">{d_f}</span>
                    <span style="font-size:0.55em;color:#a0aec0;">{h_f}</span>
                </div>'''

            wr_c = '#48bb78' if wr >= 60 else ('#f56565' if wr <= 40 else '#718096')
            
            html += f'''
            <div class="cr-deck-card">
                <div class="cr-deck-header">
                    <div class="cr-deck-meta">
                        <span class="cr-deck-rank">#{i}</span>
                        <span class="cr-deck-label" style="font-size:1.1em; color:#fff; font-weight:800;">{opp['opponent_name']}</span>
                        <span class="{cat_class}-badge">{category}</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:0.75em;color:#94a3b8;font-family:monospace;display:block;margin-bottom:2px;">{opp['opponent_tag']}</span>
                        <span class="cr-wr-badge" style="background:{wr_c}; color:#fff; font-size:0.9em;">{wr}% WR</span>
                    </div>
                </div>

                <div class="cr-deck-body">
                    <div class="cr-h2h-panel {cat_class}" style="background: rgba(255,255,255,0.03); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                        <div style="font-size:0.85em; font-weight:800; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">Confronto Direto:</div>
                        <div style="display:flex; gap:15px; font-size:1.1em; font-weight:900;">
                            <span style="color:#48bb78;">{wins}V</span>
                            <span style="color:#718096;">{draws}E</span>
                            <span style="color:#f56565;">{losses}D</span>
                        </div>
                        <div style="margin-left:auto; font-size:0.75em; color:#64748b; font-weight:600;">VISTO PELA ÚLTIMA VEZ EM: {opp['last_encounter'][:16].replace('T', ' ')}</div>
                    </div>
                    
                    {preview_html}
                    
                    <div class="cr-progress-bar" style="height:6px; background:rgba(0,0,0,0.2); border-radius:10px; overflow:hidden;">
                        <div class="cr-bar-wins" style="width:{w_p}%; background:#48bb78;"></div>
                        <div class="cr-bar-draws" style="width:{d_p}%; background:#718096;"></div>
                        <div class="cr-bar-losses" style="width:{l_p}%; background:#f56565;"></div>
                    </div>
                    
                    <div class="cr-stats-panel" style="width:100%; margin-top:10px;">
                        <div class="cr-battles-timeline" style="background:rgba(0,0,0,0.1); padding:15px; border-radius:16px; border:1px solid rgba(255,255,255,0.03);">
                            <div class="cr-timeline-label" style="font-size:0.7em; color:#64748b; margin-bottom:12px; font-weight:800; text-transform:uppercase; letter-spacing:1px;">Histórico Recente (Selecione para analisar o deck)</div>
                            <div class="cr-timeline-badges timeline-{tag_clean}" style="display:flex;gap:15px;padding:5px 0;overflow-x:auto;scrollbar-width: thin;">{timeline}</div>
                        </div>
                    </div>
                </div>
            </div>'''
            
        return html + "</div>"

    def generate_lethal_decks_html(self, lethal_decks: List[Dict]) -> str:
        """Gera HTML para os decks que mais causam derrotas."""
        if not lethal_decks: return '<div class="cr-empty-state">Dados insuficientes para mapear decks letais.</div>'
        
        html = '<div class="cr-decks-list">'
        for i, ld in enumerate(lethal_decks, 1):
            deck_str = ld['deck']
            losses = ld['losses_caused']
            opponents = ld['opponents_list']
            last = ld['last_encounter'][:16].replace('T', ' ')
            
            c_list = ld['cards']
            def c_h(n):
                img = self.get_card_image_path(n)
                return f'<div class="cr-card-wrap" title="{n}" style="width:50px;height:60px;"><img src="{img}" class="cr-card-img" loading="lazy"></div>'
            
            html += f'''
            <div class="cr-deck-card" style="padding:15px; border-left: 5px solid #e53e3e;">
                <div class="cr-deck-header" style="background:#fff5f5;">
                    <div class="cr-deck-meta">
                        <span class="cr-deck-rank" style="background:#e53e3e;">#{i} MAIS LETAL</span>
                        <span class="cr-deck-label" style="font-weight:700;">Causou {losses} derrotas</span>
                    </div>
                </div>
                <div class="cr-deck-body" style="align-items:center;">
                    <div class="cr-cards-grid">
                        <div class="cr-cards-row">{ "".join(c_h(c) for c in c_list[:4]) }</div>
                        <div class="cr-cards-row">{ "".join(c_h(c) for c in c_list[4:8]) }</div>
                    </div>
                    <div class="cr-stats-panel" style="margin-left:20px;">
                        <div style="font-size:0.9em; color:#4a5568; margin-bottom:8px;">
                            <strong>Usuários comuns:</strong> {opponents}
                        </div>
                        <div style="font-size:0.8em; color:#718096;">
                            <strong>Última derrota:</strong> {last}
                        </div>
                        <div style="margin-top:10px; background:#fff5f5; color:#c53030; font-size:0.75em; padding:5px 10px; border-radius:5px; font-weight:700; text-transform:uppercase;">
                            ALERTA: Deck com alta taxa de counter
                        </div>
                    </div>
                </div>
            </div>'''
            
        return html + "</div>"


    def generate_clan_member_activity_html(self, clan_members: List[Dict], deck_analytics: Dict, player_name: str) -> str:
        """Generate HTML for clan member activity section"""
        if not clan_members:
            return "<p>No clan member data available.</p>"
        
        # Create deck changes lookup
        deck_changes_lookup = {}
        if deck_analytics and 'deck_experimenters' in deck_analytics:
            for experimenter in deck_analytics['deck_experimenters']:
                deck_changes_lookup[experimenter['name']] = experimenter['deck_changes']
        
        # Generate clan member tables/cards (similar to clan_generator.py)
        clan_table_html = ""
        clan_cards_html = ""
        
        for member in clan_members[:20]:  # Show top 20 members
            is_current_player = member['name'] == player_name
            row_class = "current-player" if is_current_player else ""
            card_class = "current-player-card" if is_current_player else ""
            
            role_class = {
                'leader': 'leader',
                'coLeader': 'co-leader', 
                'elder': 'elder',
                'member': 'member'
            }.get(member['role'], 'member')
            
            role_display = member['role'].replace('coLeader', 'Co-Leader')
            
            # Create member filename and link
            member_filename = f"member_{self.safe_filename(member['name'])}.html"
            member_link = f'<a href="{member_filename}" style="color: #4299e1; text-decoration: none; font-weight: bold;">{member["name"]}</a>'
            
            # Get deck changes for this member
            deck_changes = deck_changes_lookup.get(member['name'], 0)
            
            clan_table_html += f"""
                <tr class="{row_class}">
                    <td>{member_link}</td>
                    <td><span class="role-{role_class}">{role_display}</span></td>
                    <td>{member['trophies']:,}</td>
                    <td>{member['donations']}↑ {member['donations_received']}↓</td>
                    <td>{deck_changes}</td>
                    <td>{self.format_time_ago(member['last_seen'])}</td>
                </tr>
            """
            
            clan_cards_html += f"""
                <div class="clan-member-card {card_class}">
                    <div class="member-card-header">
                        <strong class="member-name">{member_link}</strong>
                        <span class="role-{role_class} member-role">{role_display}</span>
                    </div>
                    <div class="member-card-content">
                        <div class="member-stats">
                            <span class="trophy-count">🏆 {member['trophies']:,}</span>
                            <span class="donation-stats">📦 {member['donations']}↑ {member['donations_received']}↓</span>
                            <span class="deck-changes">🔄 {deck_changes} deck changes</span>
                        </div>
                        <div class="member-activity">
                            <span class="last-seen">🕒 {self.format_time_ago(member['last_seen'])}</span>
                        </div>
                    </div>
                </div>
            """
        
        return f"""
        <div class="section">
            <h2>🏰 Clan Member Activity</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Overview of clan member statistics and activity.
            </p>
            <div class="desktop-table">
                <table id="clan-members-table">
                    <thead>
                        <tr>
                            <th class="sortable" data-column="name">Name <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="role">Role <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="trophies">Trophies <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="donations">Donations <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="deck-changes">Deck Changes <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="last-seen">Last Seen <span class="sort-indicator">↕</span></th>
                        </tr>
                    </thead>
                    <tbody>{clan_table_html}</tbody>
                </table>
            </div>
            <div class="clan-member-cards">{clan_cards_html}</div>
        </div>
        """

    def get_war_decks_from_csv(self):
        """Busca os 5 melhores jogadores (Clã e Global) do arquivo de guerra."""
        war_decks_path = os.path.join(self.base_dir, "data_csv_oficial", "war_top_decks.csv")
        players = {'clan': [], 'global': []}
        
        if not os.path.exists(war_decks_path):
            return players
            
        try:
            with open(war_decks_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    player_data = {
                        'name': row.get('player_name', 'Unknown'),
                        'tag': row.get('player_tag', ''),
                        'win_rate': float(row.get('win_rate', 0)),
                        'total_battles': int(row.get('total_battles', 0)),
                        'deck': row.get('cards', '').split(',')[:8],
                        'type': row.get('type', 'global') # 'clan' ou 'global'
                    }
                    if player_data['type'] == 'clan':
                        players['clan'].append(player_data)
                    else:
                        players['global'].append(player_data)
        except Exception as e:
            print(f"Erro ao carregar decks de guerra: {e}")
            
        return players

    def generate_war_decks_html(self, war_players):
        """Gera o HTML para a seção de Decks de Elite (Guerra)."""
        if not war_players['clan'] and not war_players['global']:
            return ""

        html = """
        <div class="section elite-spy-section">
            <div class="elite-header">
                <div class="elite-badge">TOP SECRET</div>
                <h2>🕵️ Elite Spy: Decks de Guerra</h2>
                <p>Os decks mais eficientes utilizados pelos melhores jogadores do clã e do ranking global.</p>
            </div>
            
            <div class="deck-tabs">
                <button class="tab-button active" onclick="showWarTab('clan-war')">Nossos Heróis</button>
                <button class="tab-button" onclick="showWarTab('global-war')">Meta Global</button>
            </div>

            <div id="clan-war" class="tab-content active">
                <div class="cr-decks-list">
        """

        for player in war_players['clan']:
            cards_html = "".join([f'<div class="cr-card-wrap"><img src="{self.get_card_image_path(card)}" class="cr-card-img" title="{card}"></div>' for card in player['deck']])
            html += f"""
                <div class="cr-deck-card">
                    <div class="cr-deck-header">
                        <div class="player-info">
                            <span class="cr-player-name">{player['name']}</span>
                            <span class="cr-wr-badge">{player['win_rate']:.1f}% Win Rate</span>
                        </div>
                        <span class="cr-deck-rank">#{player['total_battles']} Lutas</span>
                    </div>
                    <div class="cr-deck-body">
                        <div class="cr-grid-8x1">{cards_html}</div>
                    </div>
                </div>
            """

        html += """
                </div>
            </div>

            <div id="global-war" class="tab-content">
                <div class="cr-decks-list">
        """

        for player in war_players['global']:
            cards_html = "".join([f'<div class="cr-card-wrap"><img src="{self.get_card_image_path(card)}" class="cr-card-img" title="{card}"></div>' for card in player['deck']])
            html += f"""
                <div class="cr-deck-card">
                    <div class="cr-deck-header">
                        <div class="player-info">
                            <span class="cr-player-name">{player['name']}</span>
                            <span class="cr-wr-badge">{player['win_rate']:.1f}% Win Rate</span>
                        </div>
                        <span class="cr-deck-rank">RANK GLOBAL</span>
                    </div>
                    <div class="cr-deck-body">
                        <div class="cr-grid-8x1">{cards_html}</div>
                    </div>
                </div>
            """

        html += """
                </div>
            </div>
        </div>
        <script>
            function showWarTab(tabId) {
                document.querySelectorAll('.elite-spy-section .tab-content').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.elite-spy-section .tab-button').forEach(b => b.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');
                event.currentTarget.classList.add('active');
            }
        </script>
        """
        return html
    
    def generate_html_report(self) -> str:
        """Gera o relatório HTML completo consolidando todas as seções."""
        try:
            stats = self.get_player_stats()
            if not stats:
                return self.generate_error_page()
                
            player_tag = stats.get('player_tag')
            win_rate = (stats['wins'] / max(stats['total_battles'], 1)) * 100
            
            # Gera dados auxiliares
            battles = self.get_recent_battles(15, player_tag=player_tag)
            daily_stats = self.get_daily_battle_stats(30, player_tag=player_tag)
            clan_members = self.get_clan_members()
            deck_analytics = self.get_clan_deck_analytics()
            
            # Aba 3: Decks Letais - Oponentes que mais batem
            lethal_decks_data = self.get_lethal_opponent_decks()
            lethal_decks_html = self.generate_lethal_decks_html(lethal_decks_data)
            
            # Nova Seção: Decks de Elite (Guerra)
            war_players = self.get_war_decks_from_csv()
            war_decks_html = self.generate_war_decks_html(war_players)
            
            # Gera dados das abas de performance
            weekly_decks = self.get_weekly_decks_from_csv()
            repeated_opponents = self.get_repeated_opponents_from_csv()
            winning_decks_global = self.get_top_winning_decks_weekly()
            
            # Gera HTML das abas de decks (Meus Decks da Semana + Oponentes Repetidos + Decks Letais)
            deck_performance_html = self.generate_deck_performance_with_tabs(
                weekly_decks, repeated_opponents, winning_decks_global, [], stats, player_tag, lethal_decks_html
            )
            
            # Batalhas Recentes
            battles_table_html = ""
            battles_cards_html = ""
            for battle in battles[:10]:
                result_raw = battle.get('result') or 'UNKNOWN'
                result_class = result_raw.lower()
                result_text = result_raw.upper()
                trophy_color = "green" if (battle.get('trophy_change') or 0) >= 0 else "red"
                result_display = 'Vitória' if result_text in ['VICTORY', 'VITORIA', 'VITÓRIA'] else 'Derrota' if result_text in ['DEFEAT', 'DERROTA'] else 'Empate'
                if result_text in ['VICTORY', 'VITORIA', 'VITÓRIA'] and stats.get('name'):
                    result_display = f"Vitória - {stats['name']}"
                
                # Detalhes técnicos (Elixir e HP)
                elixir_p = battle.get('elixir_vazado_jogador', '0')
                elixir_o = battle.get('elixir_vazado_oponente', '0')
                hp_p = battle.get('vida_torre_rei_jogador', '0')
                hp_o = battle.get('vida_torre_rei_oponente', '0')
                
                battles_table_html += f"""
                    <tr class="battle-{result_class}">
                        <td>{self.format_time_ago(battle['battle_time'])}</td>
                        <td><span class="result-{result_class}">{result_display}</span></td>
                        <td>{battle['opponent_name']}</td>
                        <td>{battle['crowns']}</td>
                        <td style="color: {trophy_color}">{int(battle['trophy_change']):+d}</td>
                        <td class="tech-metric">💧 {elixir_p} | {elixir_o}</td>
                        <td class="tech-metric">🏰 {hp_p} | {hp_o}</td>
                        <td>{battle['arena_name']}</td>
                    </tr>
                """
                
                battles_cards_html += f"""
                    <div class="battle-card battle-{result_class}">
                        <div class="battle-card-header">
                            <span class="result-{result_class} battle-result">{result_display}</span>
                            <span class="battle-time">{self.format_time_ago(battle['battle_time'])}</span>
                        </div>
                        <div class="battle-card-content">
                            <div class="battle-info">
                                <strong>vs {battle['opponent_name']}</strong>
                                <span>{battle['arena_name']}</span>
                            </div>
                            <div class="battle-stats">
                                <span class="crown-count">👑 {battle['crowns']}</span>
                                <span class="trophy-change" style="color: {trophy_color}">🏆 {int(battle['trophy_change']):+d}</span>
                            </div>
                        </div>
                    </div>
                """
            
            # Histograma Diário
            daily_stats_7_days = self.get_daily_battle_stats(7, player_tag=player_tag)
            daily_histogram_desktop = self.generate_daily_histogram_html(daily_stats, "histogram-desktop", include_legend=True)
            daily_histogram_mobile = self.generate_daily_histogram_html(daily_stats_7_days, "histogram-mobile", include_legend=False)
            daily_histogram_html = daily_histogram_desktop + daily_histogram_mobile
            
            # Atividade do Clã
            clan_member_activity_html = self.generate_clan_member_activity_html(clan_members, deck_analytics, stats.get('name', ''))
            
            return self.generate_full_html(stats, win_rate, deck_performance_html, 
                                         daily_histogram_html, clan_member_activity_html,
                                         battles_table_html, battles_cards_html, lethal_decks_html, war_decks_html)
        except Exception as e:
            print(f"Erro ao gerar relatorio HTML: {str(e)}")
            return self.generate_error_page()
    
    def generate_error_page(self) -> str:
        """Generate error page when no data is available"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clash Royale Analytics - No Data</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .error-container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 40px;
            max-width: 600px;
            margin: 0 auto;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1>⚔️ Clash Royale Analytics</h1>
        <h2>No Data Available</h2>
        <p>The analytics data is being generated. Please check back in a few minutes.</p>
        <p>Data is automatically updated every hour via GitHub Actions.</p>
    </div>
</body>
</html>
        """
    
    def get_base_css_styles(self) -> str:
        """Get base CSS styles used across all pages"""
        return """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap');

        :root {
            --glass-bg: #111827;
            --glass-border: rgba(255, 255, 255, 0.1);
            --glass-blur: none;
            --primary: #4299e1;
            --primary-glow: rgba(66, 153, 225, 0.4);
            --accent: #f6ad55;
            --success: #48bb78;
            --danger: #f56565;
            --bg-dark: #0f172a;
            --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-font-smoothing: antialiased;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-dark);
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
            color: #f8fafc;
            line-height: 1.6;
            min-height: 100vh;
        }

        h1, h2, h3, h4, .clash-font {
            font-family: 'Outfit', sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
            animation: fadeIn 0.8s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .glass-panel {
            background: var(--glass-bg);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: var(--card-shadow);
        }

        .header {
            padding: 60px 40px;
            margin-bottom: 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: var(--card-shadow);
        }

        .header::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, transparent, var(--primary), transparent);
        }

        .header h1 {
            font-size: 3.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #fff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 10px 20px rgba(0,0,0,0.2);
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
        }

        .player-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1200px;
        }

        .stat-card {
            padding: 20px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .stat-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--primary);
        }

        .stat-card h3 {
            font-size: 0.75em;
            color: #94a3b8;
            margin-bottom: 8px;
            font-weight: 700;
        }

        .stat-card .value {
            font-size: 1.8em;
            font-weight: 800;
            color: #fff;
        }

        .section {
            padding: 40px;
            margin-bottom: 40px;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: var(--card-shadow);
        }

        .section h2 {
            font-size: 1.8em;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .section h2::after {
            content: '';
            flex: 1;
            height: 2px;
            background: linear-gradient(90deg, var(--primary), transparent);
            opacity: 0.2;
        }

        /* Tabs */
        .deck-tabs-container {
            margin-top: 20px;
        }

        .deck-tabs {
            display: flex;
            gap: 12px;
            margin-bottom: 30px;
            padding: 8px;
            background: rgba(0,0,0,0.3);
            border-radius: 16px;
            width: fit-content;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .tab-button {
            padding: 12px 24px;
            border-radius: 12px;
            color: #94a3b8;
            font-weight: 700;
            font-size: 0.9em;
            transition: all 0.3s;
            border: none;
            background: transparent;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .tab-button:hover {
            color: #fff;
            background: rgba(255,255,255,0.05);
        }

        .tab-button.active {
            color: #fff;
            background: var(--primary);
            box-shadow: 0 4px 15px var(--primary-glow);
        }

        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.4s ease-out; }

        /* Deck Lists */
        .cr-decks-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 25px;
            width: 100%;
            justify-content: center;
        }

        .cr-deck-card {
            border-radius: 24px;
            overflow: hidden;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--glass-border);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            width: 100%;
        }

        .cr-deck-card:hover {
            border-color: rgba(255, 255, 255, 0.2);
            background: rgba(15, 23, 42, 0.6);
            box-shadow: 0 30px 60px rgba(0,0,0,0.5);
        }

        /* Background image support for premium cards */
        .cr-deck-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: var(--card-bg-image, none);
            background-size: cover;
            background-position: center;
            opacity: 0.15;
            z-index: -1;
            pointer-events: none;
        }

        .cr-deck-header {
            padding: 20px 24px;
            background: rgba(255, 255, 255, 0.03);
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .cr-deck-rank {
            background: linear-gradient(135deg, var(--primary) 0%, #3182ce 100%);
            color: #fff;
            padding: 6px 14px;
            border-radius: 10px;
            font-weight: 800;
            font-size: 0.7em;
            box-shadow: 0 4px 10px rgba(66, 153, 225, 0.3);
        }

        .cr-wr-badge {
            font-weight: 800;
            padding: 6px 14px;
            border-radius: 10px;
            font-size: 0.85em;
            background: rgba(255,255,255,0.1);
        }

        .cr-deck-body {
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .cr-card-wrap {
            aspect-ratio: 5/6;
            background: #1e293b;
            border-radius: 14px;
            border: 2px solid rgba(255,255,255,0.05);
            position: relative;
            overflow: hidden;
            box-shadow: 0 8px 16px rgba(0,0,0,0.4);
            transition: transform 0.2s;
        }

        .cr-card-wrap:hover {
            transform: scale(1.05) translateY(-2px);
            z-index: 10;
            border-color: var(--primary);
        }

        .cr-card-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        /* Layout VS Horizontal Premium */
        .cr-battle-preview {
            display: flex;
            flex-direction: column;
            gap: 20px;
            padding: 35px;
            background: linear-gradient(145deg, rgba(30,41,59,0.4), rgba(15,23,42,0.6));
            border-radius: 30px;
            border: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 30px;
            position: relative;
            overflow: hidden;
            width: 100%;
            max-width: 2200px;
            margin-left: auto;
            margin-right: auto;
            box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        }

        .cr-battle-score-header-premium {
            z-index: 2;
            width: 100%;
        }

        .cr-vs-row {
            display: flex;
            align-items: flex-start;
            justify-content: center;
            gap: 60px;
            width: 100%;
        }

        .cr-deck-side {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
            flex: 1;
            max-width: 900px;
        }

        .cr-tower-side-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            width: 100%;
        }

        .cr-tower-img-premium {
            width: 80px;
            height: 80px;
            object-fit: contain;
            filter: drop-shadow(0 8px 12px rgba(0,0,0,0.5));
            transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .cr-tower-img-premium:hover {
            transform: translateY(-5px) scale(1.1);
        }

        .cr-player-name-vs {
            font-family: 'Outfit', sans-serif;
            font-size: 1.2em;
            font-weight: 800;
            color: #fff;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }


        .cr-trophy-change-vs {
            font-size: 0.8em;
            font-weight: 700;
            margin-top: 5px;
        }

        .cr-game-mode-badge {
            font-size: 0.7em;
            background: rgba(0,0,0,0.5);
            padding: 6px 14px;
            border-radius: 20px;
            color: #94a3b8;
            border: 1px solid rgba(255,255,255,0.1);
            text-transform: uppercase;
            letter-spacing: 1px;
            white-space: nowrap;
            margin-bottom: 10px;
        }

        .cr-grid-8x1 {
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            gap: 5px;
            background: rgba(0,0,0,0.3);
            padding: 8px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.05);
            width: 100%;
        }

        .cr-grid-4x2-premium {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px; /* Aumentado de 15px para 20px */
            padding: 20px;
            background: rgba(0,0,0,0.4);
            border-radius: 24px;
            width: 100%;
            max-width: 900px; /* Aumentado de 750px para 900px */
            margin: 0 auto;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
        }

        .cr-card-wrap-premium {
            aspect-ratio: 5/6;
            background: #1e293b;
            border-radius: 12px;
            border: 2px solid rgba(255,255,255,0.1);
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
            transition: all 0.3s;
        }

        .cr-card-wrap-premium:hover {
            transform: scale(1.1) translateY(-5px);
            z-index: 10;
            border-color: var(--primary);
            box-shadow: 0 15px 30px rgba(0,0,0,0.6);
        }

        .cr-card-level {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0,0,0,0.7);
            color: #fff;
            font-size: 0.6em;
            text-align: center;
            padding: 2px 0;
            font-weight: 800;
            text-transform: uppercase;
        }

        .cr-battle-header-premium {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 30px;
            background: rgba(0,0,0,0.3);
            border-radius: 16px 16px 0 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .cr-battle-result-label {
            color: var(--primary);
            font-weight: 800;
            font-size: 1.1em;
            letter-spacing: 1px;
        }

        .cr-battle-score-premium {
            font-size: 1.5em;
            font-weight: 900;
            color: #fff;
            letter-spacing: 4px;
        }

        .cr-battle-mode-label {
            color: #94a3b8;
            font-size: 0.8em;
            font-weight: 700;
            text-transform: uppercase;
        }

        .cr-vs-row-premium-v2 {
            display: flex;
            flex-direction: column;
            gap: 20px;
            padding: 25px;
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.4) 0%, rgba(15, 23, 42, 0.1) 100%);
            border-radius: 0 0 20px 20px;
        }

        .cr-battle-score-header-premium {
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
        }

        .cr-score-display-premium {
            background: rgba(0,0,0,0.5);
            padding: 10px 30px;
            border-radius: 50px;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .cr-score-val {
            font-size: 2.2em;
            font-weight: 900;
            color: #fff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
            letter-spacing: 5px;
        }

        .cr-vs-decks-row-premium {
            display: grid;
            grid-template-columns: 1fr 60px 1fr;
            align-items: center;
            width: 100%;
        }

        .cr-vs-center-divider {
            font-size: 1.5em;
            font-weight: 900;
            color: rgba(255,255,255,0.2);
            text-align: center;
        }

        .cr-vs-divider-vertical {
            font-family: 'Outfit', sans-serif;
            font-size: 1.2em;
            font-weight: 900;
            color: rgba(255,255,255,0.1);
            text-transform: uppercase;
            text-align: center;
        }

        .cr-player-header-premium {
            text-align: center;
            margin-bottom: 15px;
        }

        .cr-player-name-premium {
            font-size: 1.4em;
            font-weight: 900;
            color: #fff;
            margin-bottom: 2px;
        }

        .cr-clan-name-premium {
            font-size: 0.7em;
            color: #94a3b8;
            font-weight: 700;
            text-transform: uppercase;
        }


        .cr-tower-img-premium {
            height: 35px; /* Reduzido de 40px para 35px */
            width: auto;
            object-fit: contain;
            filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
        }

        .cr-tower-info-premium {
            font-size: 0.7em;
            color: #94a3b8;
            font-weight: bold;
            background: rgba(0,0,0,0.3);
            padding: 2px 8px;
            border-radius: 10px;
        }

        .cr-deck-metrics-premium {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
        }

        .cr-metric-item-p {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: 800;
            font-size: 0.9em;
            color: #f8fafc;
        }

        .cr-metric-icon {
            opacity: 0.8;
        }

        .cr-deck-metrics {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 10px;
            width: 100%;
        }

        .cr-metric-badge {
            padding: 4px 10px;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.05);
            font-size: 0.65em;
            font-weight: 700;
            color: #94a3b8;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .vs-divider-premium {
            font-family: 'Outfit', sans-serif;
            font-size: 1.5em;
            font-weight: 900;
            color: #fff;
            opacity: 0.3;
            letter-spacing: -1px;
        }

        .cr-mode-badge {
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 6px 14px;
            background: rgba(var(--primary-rgb), 0.2);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 800;
            color: #fff;
            z-index: 20;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }

        .cr-stats-panel {
            background: rgba(0,0,0,0.25);
            padding: 20px;
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.03);
        }

        .cr-stats-table { width: 100%; border-collapse: collapse; }
        .cr-stats-table th {
            color: #64748b;
            font-size: 0.7em;
            padding: 8px;
            text-align: center;
            font-weight: 700;
            text-transform: uppercase;
        }
        .cr-stats-table td {
            text-align: center;
            padding: 10px;
            font-size: 1.2em;
            font-weight: 800;
            color: #f1f5f9;
        }

        .cr-th-win, .cr-td-win { color: var(--success) !important; }
        .cr-th-loss, .cr-td-loss { color: var(--danger) !important; }

        /* Timeline */
        .cr-battles-timeline {
            margin-top: 10px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 16px;
        }

        .cr-timeline-label {
            font-size: 0.65em;
            color: #64748b;
            font-weight: 700;
            margin-bottom: 12px;
            text-transform: uppercase;
        }

        .cr-timeline-badges {
            display: flex;
            gap: 10px;
            overflow-x: auto;
            padding-bottom: 10px;
        }

        .cr-battle-badge {
            min-width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 0.9em;
            transition: transform 0.2s;
        }

        .cr-battle-badge:hover { transform: scale(1.1); }

        .battle-victory, .cr-badge-V { background: var(--success); box-shadow: 0 4px 12px rgba(72, 187, 120, 0.3); }
        .battle-defeat, .cr-badge-D { background: var(--danger); box-shadow: 0 4px 12px rgba(245, 101, 101, 0.3); }
        .battle-draw, .cr-badge-E { background: var(--accent); box-shadow: 0 4px 12px rgba(246, 173, 85, 0.3); }

        /* Tables & Lists */
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 8px;
            margin-top: -8px;
        }

        th {
            text-align: left;
            padding: 16px 24px;
            color: #94a3b8;
            font-size: 0.8em;
            font-weight: 700;
            text-transform: uppercase;
        }

        tr {
            transition: all 0.3s;
        }

        tbody tr {
            background: rgba(255,255,255,0.03);
        }

        tbody tr:hover {
            background: rgba(255,255,255,0.08);
            transform: scale(1.005);
        }

        td {
            padding: 16px 24px;
            border-top: 1px solid rgba(255,255,255,0.05);
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        td:first-child { border-left: 1px solid rgba(255,255,255,0.05); border-radius: 16px 0 0 16px; }
        td:last-child { border-right: 1px solid rgba(255,255,255,0.05); border-radius: 0 16px 16px 0; }

        /* Charts */
        .chart-container {
            padding: 30px;
            margin-top: 20px;
        }

        .stacked-histogram {
            display: flex;
            align-items: flex-end;
            gap: 12px;
            height: 250px;
            padding-bottom: 40px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        /* Elite Spy Custom Styles */
        .elite-spy-section {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
            border: 1px solid #334155 !important;
            position: relative;
            overflow: hidden;
        }

        .elite-spy-section::after {
            content: '';
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.05) 0%, transparent 70%);
            pointer-events: none;
        }

        .elite-header {
            margin-bottom: 30px;
            text-align: left;
        }

        .elite-badge {
            display: inline-block;
            background: #ef4444;
            color: #fff;
            font-size: 0.6em;
            font-weight: 900;
            padding: 4px 12px;
            border-radius: 4px;
            letter-spacing: 2px;
            margin-bottom: 10px;
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
        }

        .elite-spy-section .cr-player-name {
            font-weight: 800;
            color: #f1f5f9;
        }

        .tech-metric {
            font-family: 'Inter', monospace;
            font-size: 0.85em;
            color: #94a3b8;
            font-weight: 600;
            white-space: nowrap;
        }

        .histogram-bar {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            gap: 4px;
            position: relative;
        }

        .bar-segment {
            width: 100%;
            border-radius: 6px;
            transition: all 0.3s;
            position: relative;
        }

        .bar-segment:hover { filter: brightness(1.2); transform: scaleX(1.1); }

        .bar-wins { background: var(--success); }
        .bar-losses { background: var(--danger); }
        .bar-draws { background: var(--accent); }

        .bar-date {
            position: absolute;
            bottom: -35px;
            left: 50%;
            transform: translateX(-50%) rotate(-45deg);
            font-size: 0.7em;
            color: #64748b;
            white-space: nowrap;
        }

        .footer {
            text-align: center;
            padding: 60px 0;
            color: #64748b;
            font-size: 0.9em;
        }

        .cr-deck-layout {
            display: flex;
            flex-direction: row;
            gap: 15px;
            align-items: center;
            padding: 5px;
            background: transparent;
            flex: 1;
        }

        .cr-battle-preview {
            display: flex;
            flex-direction: row;
            align-items: center;
            justify-content: center;
            gap: 30px;
            width: 100%;
            margin-bottom: 20px;
        }

        .cr-battle-preview > div {
            flex: 1;
        }

        .cr-battle-preview .vs-divider {
            flex: 0 0 auto;
            font-size: 1.5em;
            font-weight: 900;
            color: var(--accent);
            text-shadow: 0 0 15px var(--accent);
            opacity: 0.8;
        }

        .cr-tower-slot {
            width: 130px;
            height: 130px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            flex-shrink: 0;
            z-index: 2;
            margin-right: -25px; /* Efeito de profundidade horizontal */
        }

        .cr-tower-slot img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            filter: drop-shadow(0 10px 15px rgba(0,0,0,0.5));
        }

        .cr-tower-label {
            display: none;
        }

        .cr-empty-grid {
            width: 100%;
            height: 150px;
            border: 2px dashed rgba(255,255,255,0.1);
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #64748b;
            font-size: 0.8em;
        }

        @media (max-width: 1024px) {
            .cr-decks-list { grid-template-columns: 1fr; }
        }

        @media (max-width: 640px) {
            .header h1 { font-size: 2.2em; }
            .section { padding: 24px; }
            .container { padding: 10px; }
            .desktop-table { display: none; }
            .cr-deck-layout { flex-direction: column; }
        }
        """
    
    def generate_full_html(self, stats, win_rate, deck_performance_html, 
                          daily_histogram_html, clan_member_activity_html="",
                          battles_table_html="", battles_cards_html="",
                          lethal_decks_html="", war_decks_html="") -> str:
        """Generate the complete HTML document"""
        
        # Carregar dicas da IA se existirem
        coach_html = ""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ai_tips_path = os.path.join(base_dir, "data_csv_oficial", "ai_coach_tips.json")
        
        if os.path.exists(ai_tips_path):
            try:
                with open(ai_tips_path, 'r', encoding='utf-8') as f:
                    ai_data = json.load(f)
                    tips_items = "".join([f'<div class="cr-coach-tip"><h4>Dica {i+1}</h4><p>{tip}</p></div>' for i, tip in enumerate(ai_data.get('tips', []))])
                    coach_html = f"""
                    <div class="cr-coach-card">
                        <div class="cr-coach-header">
                            <div class="cr-coach-icon">🧠</div>
                            <div class="cr-coach-title">Insights do Treinador AI</div>
                        </div>
                        <div class="cr-coach-tips">
                            {tips_items}
                        </div>
                        <div class="cr-coach-analysis">
                            {ai_data.get('deck_analysis', '')}
                        </div>
                    </div>
                    """
            except Exception as e:
                print(f"Erro ao carregar dicas da IA: {e}")

        css_styles = self.get_base_css_styles()
        
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analytics Clash Royale - {stats['name']}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/charts.css/dist/charts.min.css">
    <style>{css_styles}</style>
</head>
<body>
    <div class="container">
        {coach_html}
        <div class="header">
            <h1>⚔️ Analytics de Batalhas Clash Royale</h1>
            <div class="player-info">
                <h2>{stats['name']} ({stats['player_tag']})</h2>
                <p>Clã: {stats['clan_name'] or 'Nenhum'} | Nível: {stats['level']}</p>
                <p style="font-style: italic; color: #666; margin-top: 10px;">
                    <strong>Estatísticas do jogador desde {self.format_date(stats['first_battle'])}</strong><br>
                    As estatísticas são calculadas a partir das batalhas coletadas desde o início do rastreamento e não refletem os totais de toda a vida.
                </p>
            </div>
            <div class="player-stats">
                <div class="stat-card">
                    <h3>Trofeus Atuais</h3>
                    <div class="value">{stats['trophies']:,}</div>
                    <small>Melhor: {stats['best_trophies']:,}</small>
                </div>
                <div class="stat-card">
                    <h3>Taxa de Vitória{(' -<br>' + stats['name']) if stats.get('name') else ''}</h3>
                    <div class="value">{win_rate:.1f}%</div>
                    <small>{stats['wins']}V / {stats['losses']}D</small>
                </div>
                <div class="stat-card">
                    <h3>Total de Batalhas</h3>
                    <div class="value">{stats['total_battles']}</div>
                    <small>{stats['draws']} empates</small>
                </div>
                <div class="stat-card">
                    <h3>Mudança de Trofeus</h3>
                    <div class="value" style="color: {'green' if stats['total_trophy_change'] >= 0 else 'red'}">{int(stats['total_trophy_change']):+d}</div>
                    <small>Total das batalhas</small>
                </div>
                <div class="stat-card">
                    <h3>Doações Semanais</h3>
                    <div class="value">{stats.get('donations', 0)}</div>
                    <small>Recebidas: {stats.get('donations_received', 0)}</small>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📊 Registro de Atividade Diária de Batalhas</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Histórico de batalhas diárias dos últimos 30 dias. Verde = vitórias, vermelho = derrotas, laranja = empates, cinza = sem batalhas. Passe o mouse para detalhes.
            </p>
            {daily_histogram_html}
        </div>

        <div class="section">
            <h2>🏆 Decks com Melhor Performance</h2>
            {deck_performance_html}
        </div>

        {war_decks_html}

        <div class="section">
            <h2>⚔️ Últimas Batalhas</h2>
            <div class="desktop-table">
                <table>
                    <thead><tr><th>Horário</th><th>Resultado</th><th>Oponente</th><th>Coroas</th><th>Trofeus Δ</th><th>💧 Elixir</th><th>🏰 HP Torre</th><th>Arena</th></tr></thead>
                    <tbody>{battles_table_html}</tbody>
                </table>
            </div>
            <div class="battle-cards">{battles_cards_html}</div>
        </div>

        <!-- COMMENTED OUT - Clan Favorite Cards Section
        <div class="section">
            <h2>⭐ Clan Favorite Cards</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Most popular favorite cards among your clan members.
            </p>
            CLAN_FAVORITE_CARDS_HTML
        </div>
        -->


        <!-- COMMENTED OUT - Advanced Battle Analytics Section
        <div class="section">
            <h2>📈 Advanced Battle Analytics</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Enhanced analytics including card levels, opponent analysis, and matchmaking fairness.
            </p>
            CARD_LEVEL_ANALYTICS_HTML
        </div>
        -->

        {clan_member_activity_html}

        <div class="footer">
            <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Data last updated: {self.format_time_ago(stats['last_updated'])}</p>
            <p>Automatically updated via GitHub Actions</p>
        </div>
    </div>
    
    <script>
    // Table sorting functionality
    document.addEventListener('DOMContentLoaded', function() {{
        var table = document.getElementById('clan-members-table');
        if (!table) return; // Exit if table doesn't exist
        
        var headers = table.querySelectorAll('th.sortable');
        var currentSort = {{ column: '', direction: '' }};
        
        headers.forEach(function(header) {{
            header.addEventListener('click', function() {{
                var column = this.getAttribute('data-column');
                var direction = currentSort.column === column && currentSort.direction === 'asc' ? 'desc' : 'asc';
                
                // Remove existing sort classes
                headers.forEach(function(h) {{ h.classList.remove('sort-asc', 'sort-desc'); }});
                
                // Add sort class to current header
                this.classList.add('sort-' + direction);
                
                // Sort the table
                sortTable(column, direction);
                
                currentSort = {{ column: column, direction: direction }};
            }});
        }});
        
        function sortTable(column, direction) {{
            var tbody = table.querySelector('tbody');
            var rows = Array.from(tbody.querySelectorAll('tr'));
            
            rows.sort(function(a, b) {{
                var aVal, bVal;
                
                switch(column) {{
                    case 'name':
                        aVal = a.cells[0].textContent.trim().toLowerCase();
                        bVal = b.cells[0].textContent.trim().toLowerCase();
                        break;
                    case 'role':
                        // Custom role order: leader > co-leader > elder > member
                        var roleOrder = {{'leader': 1, 'co-leader': 2, 'elder': 3, 'member': 4}};
                        aVal = roleOrder[a.cells[1].textContent.trim().toLowerCase()] || 5;
                        bVal = roleOrder[b.cells[1].textContent.trim().toLowerCase()] || 5;
                        break;
                    case 'trophies':
                        aVal = parseInt(a.cells[2].textContent.replace(/,/g, '')) || 0;
                        bVal = parseInt(b.cells[2].textContent.replace(/,/g, '')) || 0;
                        break;
                    case 'donations':
                        // Extract total donations (sent + received)
                        var aDonations = a.cells[3].textContent.match(/(\\d+)↑\\s*(\\d+)↓/);
                        var bDonations = b.cells[3].textContent.match(/(\\d+)↑\\s*(\\d+)↓/);
                        aVal = aDonations ? parseInt(aDonations[1]) + parseInt(aDonations[2]) : 0;
                        bVal = bDonations ? parseInt(bDonations[1]) + parseInt(bDonations[2]) : 0;
                        break;
                    case 'deck-changes':
                        aVal = parseInt(a.cells[4].textContent) || 0;
                        bVal = parseInt(b.cells[4].textContent) || 0;
                        break;
                    case 'last-seen':
                        // Parse relative time strings for sorting
                        aVal = parseTimeAgo(a.cells[5].textContent.trim());
                        bVal = parseTimeAgo(b.cells[5].textContent.trim());
                        break;
                    default:
                        aVal = a.cells[0].textContent.trim();
                        bVal = b.cells[0].textContent.trim();
                }}
                
                if (direction === 'asc') {{
                    return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
                }} else {{
                    return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
                }}
            }});
            
            // Re-append sorted rows
            rows.forEach(function(row) {{ tbody.appendChild(row); }});
        }}
        
        function parseTimeAgo(timeStr) {{
            // Convert time ago strings to minutes for sorting
            if (timeStr === 'never') return 999999;
            if (timeStr.includes('hours ago')) {{
                return parseInt(timeStr) * 60;
            }} else if (timeStr.includes('days ago')) {{
                return parseInt(timeStr) * 24 * 60;
            }} else if (timeStr.includes('minutes ago')) {{
                return parseInt(timeStr);
            }} else if (timeStr.includes('hour ago')) {{
                return 60;
            }} else if (timeStr.includes('day ago')) {{
                return 24 * 60;
            }} else if (timeStr.includes('minute ago')) {{
                return 1;
            }}
            return 0; // "just now" or unrecognized format
        }}
    }});
    </script>
</body>
</html>
        """

def main():
    """Generate HTML report for GitHub Pages"""
    generator = GitHubPagesHTMLGenerator()
    html_content = generator.generate_html_report()
    
    # Ensure docs directory exists
    # O script pode ser rodado da raiz ou de dentro de src/
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(root_dir, 'docs')
    os.makedirs(docs_dir, exist_ok=True)
    
    # Save as index.html for GitHub Pages in docs directory
    index_path = os.path.join(docs_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"GitHub Pages HTML report generated: {index_path}")

if __name__ == "__main__":
    main()
