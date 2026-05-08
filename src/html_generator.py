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
import csv
import glob
import logging
import json
from datetime import datetime, timezone, timedelta
try:
    from datetime import UTC
except ImportError:
    # Python < 3.11 compatibility
    UTC = timezone.utc
from typing import List, Dict, Optional
from csv_database_manager import CSVManager

logger = logging.getLogger(__name__)

class GitHubPagesHTMLGenerator:
    def __init__(self, db_path: str = None):
        self.src_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.src_dir)
        self.data_csv_dir = os.path.join(self.src_dir, "data_csv_oficial")

        # Inicializa o gerenciador de CSV (Sem SQL)
        self.csv_manager = CSVManager()
        
        logger.info(f"Dashboard configurado em modo 100% CSV")
        self.base_url = "https://proxy.royaleapi.dev/v1"
        self.api_token = os.getenv("CR_API_TOKEN")
        self.headers = None
        if self.api_token:
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        
        self.player_tag = os.getenv('CR_PLAYER_TAG', '#2QR292P')
        self.player_name_override = os.getenv('CR_PLAYER_NAME')
        self.failed_tags = set()
        # Caches carregados diretamente do CSV (ignora SQL)
        self.battles_cache = self._load_all_battles_from_csv(self.player_tag)
        self.clan_members_cache = self._load_clan_members_csv()
        self.rankings_history_cache = [] # Arquivo removido por redundancia
        self.clan_decks_cache = []       # Arquivo removido por redundancia
        self.players_cache = self._load_csv_as_list('players.csv')
        self.card_name_mapping = self._get_card_name_mapping()
        self.cards_master = self._load_cards_master_csv()
        self.upcoming_chests = self._load_upcoming_chests_json()
        
    def get_copy_deck_link(self, deck_list: List[str]) -> str:
        """Gera um link para copiar o deck para o jogo usando os IDs das cartas."""
        ids = []
        for card_name in deck_list:
            card_info = self.cards_master.get(card_name)
            if card_info and card_info.get('card_id'):
                ids.append(card_info['card_id'])
        
        if len(ids) < 8:
            return "#"
            
        return f"clashroyale://copyDeck?deck={';'.join(ids)}"

    def _load_upcoming_chests_json(self) -> List[Dict]:
        """Carrega o ciclo de baús do JSON oficial"""
        path = os.path.join(self.data_csv_dir, 'upcoming_chests.json')
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('items', [])
        except Exception as e:
            logger.error(f"Erro ao ler upcoming_chests.json: {e}")
            return []

    def _load_csv_as_list(self, filename: str) -> List[Dict]:
        """Auxiliar para carregar qualquer CSV da pasta oficial como lista de dicts"""
        path = os.path.join(self.data_csv_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Aviso: {path} não encontrado")
            return []
        try:
            with open(path, mode='r', encoding='utf-8') as f:
                return list(csv.DictReader(f, delimiter=';'))
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
        return master    def _load_all_battles_from_csv(self, player_tag: str = None) -> List[Dict]:
        """Loads all battles from the consolidated CSV files with robust detection."""
        if not player_tag:
            player_tag = self.player_tag
        
        battles_dict = {}
        official_file = os.path.join(self.data_csv_dir, 'oponentes_ano_2026.csv')
        
        files = []
        if os.path.exists(official_file): 
            files.append(official_file)
        
        if not files:
            logger.error(f"Nenhum arquivo de dados encontrado em {self.data_csv_dir}")
            return []

        logger.info(f"Lendo fonte de dados: {[os.path.basename(f) for f in files]}...")
        
        for file_path in files:
            file_battles_count = 0
            try:
                # Tenta encodings em ordem de probabilidade
                data = []
                for encoding in ['utf-8-sig', 'utf-8', 'latin1', 'utf-16']:
                    try:
                        with open(file_path, mode='r', encoding=encoding) as f:
                            first_line = f.readline()
                            f.seek(0)
                            if not first_line: continue
                            
                            # Detecta delimitador
                            delimiter = ';' if ';' in first_line else ','
                            reader = csv.DictReader(f, delimiter=delimiter)
                            data = list(reader)
                            
                        if data and len(data[0]) > 1: # Garante que leu mais de uma coluna
                            logger.info(f"Arquivo {os.path.basename(file_path)} lido com sucesso ({encoding}, '{delimiter}').")
                            break
                    except Exception as e:
                        continue
                
                if not data:
                    logger.warning(f"Aviso: {file_path} est vazio ou ilegvel.")
                    continue

                for row in data:
                    if not row: continue
                    
                    # Filtro de player_tag (resiliente a nomes de colunas e espaos)
                    row_tag = (row.get('player_tag') or row.get('tag_jogador') or '').strip()
                    if player_tag and row_tag and row_tag != player_tag:
                        continue
                            
                    # Normaliza data e hora
                    raw_battle_time = row.get('data') or row.get('battle_time') or ''
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
                    
                    # Tenta inferir pelas coroas se unknown
                    try:
                        cp = int(row.get('coroas_jogador') or row.get('coroa_jogador') or row.get('crowns') or 0)
                        co = int(row.get('coroas_oponente') or row.get('coroa_oponente') or row.get('opponent_crowns') or 0)
                        if norm_res == 'unknown':
                            if cp > co: norm_res = 'victory'
                            elif cp < co: norm_res = 'defeat'
                            else: norm_res = 'draw'
                    except:
                        cp, co = 0, 0

                    opp_tag = str(row.get('tag_oponente') or row.get('oponente_tag') or row.get('opponent_tag') or '').strip().upper()
                    opp_name = row.get('nome_oponente') or row.get('oponente_nome') or row.get('oponente') or 'Oponente'
                    
                    # Evita oponentes fantasmas
                    if not opp_tag and (not opp_name or opp_name == 'Oponente'):
                        continue
                    
                    # Chave de deduplicao
                    opp_id = opp_tag if opp_tag else str(opp_name)
                    dedup_key = (b_time, opp_id)
                    
                    if dedup_key in battles_dict:
                        continue
                    
                    # Extrai dados premium
                    battle_obj = {
                        'battle_time': b_time_str,
                        '_dt': b_time,
                        'result': norm_res,
                        'player_tag': player_tag,
                        'opponent_name': opp_name,
                        'opponent_tag': opp_tag,
                        'crowns': cp,
                        'opponent_crowns': co,
                        'arena_name': row.get('arena') or row.get('arena_name') or 'Arena',
                        'deck_cards': row.get('deck_jogador') or row.get('meu_deck') or row.get('deck_cards') or '',
                        'opponent_deck_cards': row.get('deck_oponente') or row.get('opponent_deck_cards') or '',
                        'player_level': self._safe_int(row.get('player_level') or row.get('nivel_jogador'), 0),
                        'opponent_level': self._safe_int(row.get('opponent_level') or row.get('nivel_oponente'), 0),
                        'opponent_clan_name': row.get('clan_oponente') or row.get('oponente_cla') or row.get('opponent_clan_name') or '',
                        'opponent_trophies': self._safe_int(row.get('trofes_oponente') or row.get('opponent_trophies'), 0),
                        'trophy_change': self._safe_int(row.get('mudanca_trofes') or row.get('trophy_change'), 0),
                        'game_mode': row.get('modo_jogo') or row.get('game_mode') or 'Desconhecido',
                        # Premium fields
                        'elixir_vazado_jogador': row.get('elixir_vazado_jogador') or '0',
                        'elixir_vazado_oponente': row.get('elixir_vazado_oponente') or '0',
                        'vida_torre_rei_jogador': row.get('vida_torre_rei_jogador') or '0',
                        'vida_torre_rei_oponente': row.get('vida_torre_rei_oponente') or '0',
                        'vida_torres_princesa_jogador': row.get('vida_torres_princesa_jogador') or '0',
                        'vida_torres_princesa_oponente': row.get('vida_torres_princesa_oponente') or '0',
                        'trofes_iniciais_jogador': row.get('trofes_iniciais_jogador') or '0',
                        'trofes_finais_jogador': row.get('trofes_finais_jogador') or '0',
                        'posicao_global_jogador': row.get('posicao_global_jogador') or 'N/A',
                        'posicao_global_oponente': row.get('posicao_global_oponente') or 'N/A',
                        'nivel_torre_oponente': row.get('nivel_torre_oponente') or '0'
                    }
                    
                    # SANITIZAÇÃO DE DADOS (RESET/CORRUPÇÃO)
                    # Se trofes_iniciais_jogador contiver '#', é um ID vazado por corrupção do CSV
                    if '#' in str(battle_obj['trofes_iniciais_jogador']):
                        battle_obj['trofes_iniciais_jogador'] = '0'
                    if '#' in str(battle_obj['trofes_finais_jogador']):
                        battle_obj['trofes_finais_jogador'] = '0'
                    
                    battles_dict[dedup_key] = battle_obj
                    file_battles_count += 1
                
                logger.info(f"Arquivo {os.path.basename(file_path)}: {file_battles_count} batalhas carregadas.")
                
            except Exception as e:
                logger.error(f"Erro fatal ao processar {file_path}: {e}")
        
        final_battles = list(battles_dict.values())
        final_battles.sort(key=lambda x: x.get('_dt', datetime.min), reverse=True)
        
        logger.info(f"Total FINAL de batalhas carregadas: {len(final_battles)}")
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

        is_evolution = "Evolution" in card_name or "Evolved" in card_name
        clean_name = card_name.replace(" (Evolution)", "").replace("Evolved ", "").strip()
        
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
            'Goblin Curse': 2, 'Goblin Demolisher': 4, 'Goblin Machine': 5, 'Suspicious Bush': 2, 'Spirit Empress': 3,
            'Tower Princess': 0, 'Cannoneer': 0, 'Dagger Duchess': 0, 'Royal Chef': 0
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

    def _get_deck_metrics(self, deck_str: str, leaked: float = 0, tower_level: int = 14) -> Dict:
        """Calcula media de elixir, ciclo de 4 cartas, nivel da torre e elixir vazado.
        
        Args:
            deck_str: String de cartas no formato 'Carta1 | Carta2 | ...' ou 'Carta1|Carta2|...'
            leaked: Elixir vazado pelo lado (jogador ou oponente) nessa batalha.
            tower_level: Nivel da torre do rei para calculo de HP.
        Returns:
            Dict com avg, cycle, leaked, level e hp da torre.
        """
        if not deck_str or deck_str == 'N/D':
            return {'avg': 0, 'cycle': 0, 'leaked': leaked, 'level': tower_level, 'hp': self._get_tower_hp(tower_level)}
        
        cards = [c.strip() for c in deck_str.replace(' | ', '|').split('|')]
        costs = []
        for c in cards:
            # Tenta encontrar o custo no mapeamento; fallback para 3.5 (media global do jogo)
            cost = self.card_elixir_costs.get(c, 3.5)
            costs.append(cost)
        
        if not costs:
            return {'avg': 0, 'cycle': 0, 'leaked': leaked, 'level': tower_level, 'hp': self._get_tower_hp(tower_level)}
            
        avg = round(sum(costs) / len(costs), 1)
        # Ciclo de 4 cartas: soma das 4 cartas mais baratas do deck
        cycle = sum(sorted(costs)[:4])
        # Garante nivel valido para evitar KeyError no HP map
        safe_level = max(1, min(15, int(tower_level) if str(tower_level).isdigit() else 14))
        
        return {
            'avg': avg,
            'cycle': cycle,
            'leaked': float(leaked) if str(leaked).replace('.','').isdigit() else 0.0,
            'level': safe_level,
            'hp': self._get_tower_hp(safe_level)
        }

    def _get_battle_deck_metrics(self, deck_str: str, battle: Dict, is_opponent: bool = False) -> Dict:
        """Monta metricas completas de um lado da batalha (jogador ou oponente).
        
        Centraliza a logica que antes era construida manualmente.
        
        Args:
            deck_str: String de cartas do lado.
            battle: Dicionario da batalha com os campos de nivel e elixir.
            is_opponent: Se True, usa campos do oponente; senao usa campos do jogador.
        Returns:
            Dict completo com avg, cycle, leaked, level e hp.
        """
        if is_opponent:
            leaked_raw = battle.get('elixir_vazado_oponente') or battle.get('opp_leaked', 0)
            level_raw = battle.get('nivel_torre_oponente') or battle.get('nivel_oponente') or battle.get('opponent_level') or battle.get('opp_tower_level', 14)
        else:
            leaked_raw = battle.get('elixir_vazado_jogador') or battle.get('player_leaked', 0)
            level_raw = battle.get('nivel_torre_jogador') or battle.get('player_level') or battle.get('player_tower_level', 14)
        
        # Sanitizacao: converte para tipos corretos, protege contra string vazia ou None
        try:
            leaked = float(leaked_raw) if leaked_raw and str(leaked_raw).strip() not in ('0', '', 'N/A') else 0.0
        except (ValueError, TypeError):
            leaked = 0.0
        try:
            # Garante que level_raw seja tratado como string para isdigit, mas converte para int
            s_level = str(level_raw).strip()
            tower_level = int(s_level) if s_level.isdigit() and int(s_level) > 0 else 14
        except (ValueError, TypeError):
            tower_level = 14

        metrics = self._get_deck_metrics(deck_str, leaked=leaked, tower_level=tower_level)
        metrics['leaked_color'] = '#f56565' if float(leaked) > 0 else '#48bb78'
        metrics['leaked_label'] = f"{leaked:.1f}" if float(leaked) > 0 else 'N/A'
        return metrics
    
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
            'name': self.player_name_override if self.player_name_override else player_row.get('name', 'Unknown'),
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
            # Ignora Batalhas de Barco (Boat Battle) - Não são PvP reais
            game_mode = (b.get('game_mode') or b.get('modo_jogo') or '').lower()
            if 'boatbattle' in game_mode or 'barco' in game_mode:
                continue

            o_tag = (b.get('opponent_tag') or b.get('tag_oponente') or '').strip().upper()
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

        # Aba 2: Oponentes Repetidos - usa estatisticas consolidadas do cache CSV com deduplicacao
        csv_repeated = self.get_repeated_opponents_from_csv()
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
            # Mantém todos os campos originais para não perder dados (como coroas, modo de jogo, etc)
            row = b.copy()
            
            # Normalização de campos para compatibilidade entre diferentes partes do código
            battle_time = b.get('battle_time', '')
            dt = b.get('_dt') or self._parse_dt(battle_time)
            result = (b.get('result') or '').strip().lower()
            opponent_tag = b.get('opponent_tag', '')
            player_deck = b.get('deck_cards', '')
            opponent_deck = b.get('opponent_deck_cards', '')

            row.update({
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
                'nome_oponente': b.get('opponent_name', 'Oponente'),
                # Prioriza os nomes das colunas conforme o CSV oficial para evitar placar 0x0
                'coroas_jogador': b.get('coroas_jogador') if b.get('coroas_jogador') is not None else b.get('crowns', 0),
                'coroas_oponente': b.get('coroas_oponente') if b.get('coroas_oponente') is not None else b.get('opponent_crowns', 0),
                'modo_jogo': b.get('modo_jogo') or b.get('game_mode', 'Desconhecido'),
                'mudanca_trofes': b.get('mudanca_trofes') if b.get('mudanca_trofes') is not None else b.get('trophy_change', 0)
            })
            all_data.append(row)
            
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
                    'opp_deck': row.get('deck_oponente', ''),
                    # Dados extras para o preview VS (estilo RoyaleAPI)
                    'opp_name': row.get('opponent_name') or row.get('nome_oponente', 'Oponente'),
                    'opp_clan': row.get('opponent_clan_name', ''),
                    'opp_tag':  row.get('opponent_tag') or row.get('tag_oponente', ''),
                    'nivel_torre_oponente':  row.get('nivel_torre_oponente', '0'),
                    'nivel_torre_jogador':   row.get('nivel_torre_jogador', '14'),
                    'coroas_jogador':        row.get('coroas_jogador', '0'),
                    'coroas_oponente':       row.get('coroas_oponente', '0'),
                    'elixir_vazado_jogador': row.get('elixir_vazado_jogador', '0'),
                    'elixir_vazado_oponente':row.get('elixir_vazado_oponente', '0'),
                    'vida_torre_rei_jogador':row.get('vida_torre_rei_jogador', '0'),
                    'vida_torre_rei_oponente':row.get('vida_torre_rei_oponente', '0'),
                    'game_mode': row.get('game_mode') or row.get('type', 'Batalha'),
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
                # Calcula metricas completas para cada lado via metodo centralizado
                my_m = self._get_battle_deck_metrics(b['my_deck'], b, is_opponent=False)
                opp_m = self._get_battle_deck_metrics(b['opp_deck'], b, is_opponent=True)
                
                b_json = urllib.parse.quote(json.dumps({
                    'my_deck': b['my_deck'], 
                    'opp_deck': b['opp_deck'],
                    'my_icons': [self.get_card_image_path(c) for c in b['my_deck'].replace(' | ', '|').split('|') if c.strip()],
                    'opp_icons': [self.get_card_image_path(c) for c in b['opp_deck'].replace(' | ', '|').split('|') if c.strip()],
                    'player_name': self.players_cache[0].get('name', 'Jogador') if self.players_cache else 'Jogador',
                    'opp_name': b.get('nome_oponente', 'Oponente'),
                    'my_metrics': my_m,
                    'opp_metrics': opp_m,
                    'game_mode': b.get('modo_jogo', 'Batalha'),
                    'crowns': b.get('coroas_jogador', 0),
                    'opponent_crowns': b.get('coroas_oponente', 0),
                    'trophy_change': b.get('trofeus', 0),
                    'date': b['data'],
                    'player_clan': b.get('player_clan', ''),
                    'opp_clan': b.get('opp_clan', '')
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
            
            def get_preview_grid(d_str, side_class, p_name="Jogador", is_opponent=False, battle_ctx=None):
                if not d_str: return f'<div class="{side_class} cr-empty-grid">N/D</div>'
                cards = [c.strip() for c in d_str.replace(' | ','|').split('|') if c.strip()][:8]

                # Usa _get_battle_deck_metrics quando disponivel (traz level e leaked corretos)
                # Caso nao haja contexto de batalha, usa _get_deck_metrics com fallbacks
                if battle_ctx:
                    metrics = self._get_battle_deck_metrics(d_str, battle_ctx, is_opponent=is_opponent)
                else:
                    metrics = self._get_deck_metrics(d_str)

                # Torres locais
                tower_img = "assets/images/towers/opp_tower.png" if is_opponent else "assets/images/towers/player_tower.png"
                fallback_tower = "https://static.wikia.nocookie.net/character-catalogue/images/c/cf/Tower_Princess.png/revision/latest?cb=20231217222258"

                # Metricas extraidas centralizadamente
                leaked  = metrics.get('leaked', 0)
                t_level = metrics.get('level', 14)
                t_hp    = metrics.get('hp', self._get_tower_hp(t_level))

                # Cor do elixir vazado: verde = 0, vermelho = teve vazamento
                leaked_color = '#f56565' if float(leaked) > 0 else '#48bb78'
                leaked_label = f"{leaked:.1f}" if float(leaked) > 0 else 'N/A'

                # Badge de nivel por carta (nivel da torre do respectivo lado)
                card_level = str(t_level) if t_level else '14'
                cards_with_badge = "".join(
                    f'<div class="cr-card-wrap-premium" title="{c}" style="position:relative;">'
                    f'<img src="{self.get_card_image_path(c)}" class="cr-card-img">'
                    f'<span class="cr-card-level-badge">Nivel {card_level}</span>'
                    f'</div>'
                    for c in cards
                )
                grid_html = f'''
                    <div class="cr-grid-4x2">
                        {cards_with_badge}
                    </div>'''

                footer_html = f'''
                    <div class="cr-deck-footer">
                        <div class="cr-footer-metric" title="Media de Elixir">
                            <span class="cr-footer-icon">💧</span>
                            <span class="cr-footer-val">{metrics["avg"]}</span>
                            <span class="cr-footer-label">Elixir</span>
                        </div>
                        <div class="cr-footer-metric" title="Ciclo de 4 Cartas">
                            <span class="cr-footer-icon">🔄</span>
                            <span class="cr-footer-val">{metrics["cycle"]}</span>
                            <span class="cr-footer-label">Ciclo</span>
                        </div>
                        <div class="cr-footer-metric" title="Elixir Vazado" style="color:{leaked_color}">
                            <span class="cr-footer-icon">🚫</span>
                            <span class="cr-footer-val">{leaked_label}</span>
                            <span class="cr-footer-label">Vazado</span>
                        </div>
                        <div class="cr-footer-metric" title="Nivel da Torre do Rei">
                            <span class="cr-footer-icon">🏰</span>
                            <span class="cr-footer-val">Lv {t_level}</span>
                            <span class="cr-footer-label">Torre</span>
                        </div>
                    </div>'''

                # Extrai info do cla do contexto de batalha para exibir abaixo do nome
                p_clan = ''
                if battle_ctx:
                    p_clan = battle_ctx.get('opp_clan', '') if is_opponent else ''
                clan_line = f'<div class="cr-player-clan">{p_clan}</div>' if p_clan else ''
                hp_display = f'{t_hp:,}' if isinstance(t_hp, int) else str(t_hp)

                return f'''
                    <div class="{side_class} cr-deck-side">
                        <div class="cr-player-header-premium">
                            <div class="cr-player-name-premium">{p_name}</div>
                            {clan_line}
                            <div class="cr-tower-info-premium">🏰 {hp_display} Pontos de vida</div>
                        </div>
                        <div class="cr-tower-container-premium">
                            <img src="{tower_img}" class="cr-tower-img-premium" onerror="this.src='{fallback_tower}'">
                        </div>
                        {grid_html}
                        {footer_html}
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
                        <div class="cr-modal-trigger-msg" style="text-align:center; padding:15px; background:rgba(66,153,225,0.1); border-radius:12px; margin-bottom:10px; border:1px dashed rgba(66,153,225,0.3);">
                            <span style="font-size:0.8em; color:#4299e1; font-weight:700;">💡 Clique nos badges abaixo para abrir o replay VS</span>
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
                    {"".join(f'<div class="cr-card-wrap-premium" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img" loading="lazy"></div>' for c in cards_list)}
                </div>
                <div class="cr-deck-metrics-premium" style="margin-top:15px; justify-content:center; background: rgba(0,0,0,0.5); border-radius:15px; padding:10px; border:1px solid rgba(255,255,255,0.05);">
                    <div class="cr-metric-item-p" style="color:#fff;"><span class="cr-metric-icon">💧</span> {metrics["avg"]}</div>
                    <div class="cr-metric-item-p" style="color:#fff;"><span class="cr-metric-icon">🔄</span> {metrics["cycle"]}</div>
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
        """Agrupa oponentes repetidos com deduplicação rigorosa e sincronização de chaves para o HTML."""
        all_rows = self.load_all_data_rows()
        if not all_rows: return []
            
        opp_stats = {}
        processed_battle_ids = set() # Para evitar duplicidade de registros
        
        for b in all_rows:
            # 1. Deduplicação de Batalha (Evita o erro de duplicidade relatado)
            # Tenta compor um ID único mais estável
            t_tag = (b.get('tag_oponente') or b.get('opponent_tag') or '').strip().upper()
            if not t_tag.startswith('#'): t_tag = '#' + t_tag
            
            b_dt = b.get('dt') or b.get('battle_time')
            battle_id = b.get('id') or f"{b_dt}_{t_tag}_{b.get('deck_jogador')}"
            if battle_id in processed_battle_ids:
                continue
            processed_battle_ids.add(battle_id)

            tag = t_tag
            if not tag or tag == '#': continue

            # Ignora Batalhas de Barco (Boat Battle) - Não são PvP reais
            game_mode = (b.get('modo_jogo') or b.get('game_mode') or '').lower()
            if 'boatbattle' in game_mode or 'barco' in game_mode:
                continue
            
            if tag not in opp_stats:
                opp_stats[tag] = {
                    'opponent_tag': tag, 
                    'opponent_name': b.get('nome_oponente') or b.get('opponent_name', 'Oponente'), 
                    'total_battles': 0, 
                    'user_wins': 0, 
                    'user_losses': 0, 
                    'user_draws': 0,
                    'stats': [], # Renomeado de 'battles' para 'stats' conforme esperado pelo HTML
                    'last_deck': b.get('deck_oponente') or b.get('opponent_deck_cards', '')
                }
            
            # 2. Priorização de Nome Real (Resolve o problema de nomes vazios)
            current_name = b.get('nome_oponente') or b.get('opponent_name', 'Oponente')
            if opp_stats[tag]['opponent_name'] == 'Oponente' and current_name != 'Oponente':
                opp_stats[tag]['opponent_name'] = current_name
            
            opp_stats[tag]['total_battles'] += 1
            res = (b.get('resultado') or b.get('result') or '').strip().lower()
            if res in ['vitoria', 'victory']: opp_stats[tag]['user_wins'] += 1
            elif res in ['derrota', 'defeat']: opp_stats[tag]['user_losses'] += 1
            else: opp_stats[tag]['user_draws'] += 1
            
            dt = b.get('dt') or self._parse_dt(b.get('battle_time', ''))
            if not dt: continue
            d_display = dt.strftime('%d/%m %H:%M')
                
            opp_stats[tag]['stats'].append({
                'resultado': res, 
                'result': res, # Compatibilidade
                'data_str': d_display,
                'battle_time': d_display, # Compatibilidade
                'data': d_display, # Compatibilidade
                'my_deck': " | ".join((b.get('deck_jogador') or b.get('deck_cards', '')).split(" | ")[:8]),
                'deck_cards': " | ".join((b.get('deck_jogador') or b.get('deck_cards', '')).split(" | ")[:8]), # Compatibilidade
                'opp_deck': " | ".join((b.get('deck_oponente') or b.get('opponent_deck_cards', '')).split(" | ")[:8]),
                'opponent_deck_cards': " | ".join((b.get('deck_oponente') or b.get('opponent_deck_cards', '')).split(" | ")[:8]), # Compatibilidade
                'crowns': b.get('coroas_jogador') or b.get('crowns', 0),
                'opponent_crowns': b.get('coroas_oponente') or b.get('opponent_crowns', 0),
                'trophy_change': b.get('trofes_ganhos') or b.get('trophy_change', 0),
                'game_mode': b.get('modo_jogo') or b.get('arena_name', 'Batalha'),
                'player_clan': b.get('player_clan', ''),
                'opp_clan': b.get('opp_clan', ''),
                'player_leaked': b.get('player_leaked', 0),
                'opp_leaked': b.get('opp_leaked', 0),
                'player_tower_level': b.get('player_tower_level', 14),
                'opp_tower_level': b.get('opp_tower_level', 14),
                'dt_obj': dt 
            })
            
            if b.get('deck_oponente') or b.get('opponent_deck_cards'):
                opp_stats[tag]['last_deck'] = b.get('deck_oponente') or b.get('opponent_deck_cards')

        # 3. Categorização e Ordenação
        repeated = []
        for o in opp_stats.values():
            if o['total_battles'] > 1:
                # Calcula Win Rate
                o['user_win_rate'] = round((o['user_wins'] / o['total_battles']) * 100, 1)
                
                # Define Categoria de Rivalidade
                wr = o['user_win_rate']
                if wr >= 80: o['category'], o['category_class'] = "Freguês de Carteirinha", "fregues"
                elif wr >= 60: o['category'], o['category_class'] = "Vantagem Sua", "vantagem"
                elif wr <= 20: o['category'], o['category_class'] = "Seu Carrasco", "carrasco"
                elif wr <= 40: o['category'], o['category_class'] = "Oponente Difícil", "dificil"
                else: o['category'], o['category_class'] = "Equilibrado", "equilibrado"

                # Ordena as batalhas por data (mais recente primeiro)
                o['stats'].sort(key=lambda x: x['dt_obj'], reverse=True)
                o['last_battle_dt'] = o['stats'][0]['dt_obj']
                repeated.append(o)

        repeated.sort(key=lambda x: x['last_battle_dt'], reverse=True)
        return repeated[:20]


    def generate_dashboard_scripts(self) -> str:
        """Gera os scripts globais necessários para a interatividade do dashboard."""
        import json
        card_urls = {}
        for name, data in self.cards_master.items():
            url = data.get('url_icon')
            if url and url != 'N/A':
                card_urls[name] = url
                # Adicionar aliases comuns para maior robustez
                card_urls[name.replace(' ', '')] = url
                card_urls[name.replace('.', '')] = url
                if 'Musketeer' in name: card_urls['Musk'] = url
                if 'P.E.K.K.A' in name: card_urls['Pekka'] = url
                if 'Wall Breakers' in name: card_urls['WallBreakers'] = url
                if 'Skeleton' in name and 'Barrel' in name: card_urls['SkellyBarrel'] = url

            if data.get('url_evolution') and data['url_evolution'] != 'N/A':
                evo_url = data['url_evolution']
                card_urls[f"{name} (Evolution)"] = evo_url
                card_urls[f"Evolved {name}"] = evo_url
                card_urls[name.replace(' ', '') + 'Evolution'] = evo_url
            if data.get('url_hero') and data['url_hero'] != 'N/A':
                card_urls[name] = data['url_hero']
                card_urls[name.replace(' ', '').replace('.', '')] = data['url_hero']
            
            # Alias de slug para compatibilidade com logs de batalha
            slug = name.lower().replace(' ', '-').replace('.', '').replace('(', '').replace(')', '')
            card_urls[slug] = url
            if 'p-e-k-k-a' in slug: card_urls['pekka'] = url
            if 'mini-p-e-k-k-a' in slug: card_urls['minipekka'] = url
            if 'the-log' in slug: card_urls['log'] = url

        
        card_map_json = json.dumps(card_urls)

        return """
        <script>
        const CARD_MAP = """ + card_map_json + """;
        function updateBattlePreview(deckId, battleIdx, battleDataJson) {
            try {
                const data = JSON.parse(decodeURIComponent(battleDataJson));
                const modal = document.getElementById('cr-battle-modal');
                const content = document.getElementById('battle-modal-content');
                if (!modal || !content) return;
                
                const myDeckHtml = getMiniGridJS(data.my_deck, 'my-deck-side', data.player_name, data.player_clan || '', data.my_metrics, data.my_deck_link, data.my_icons);
                const oppDeckHtml = getMiniGridJS(data.opp_deck, 'opp-deck-side', data.opp_name, data.opp_clan || '', data.opp_metrics, data.opp_deck_link, data.opp_icons);
                
                const score = `${data.crowns || 0} - ${data.opponent_crowns || 0}`;
                const tropChange = data.trophy_change || 0;
                const tropColor = tropChange > 0 ? '#48bb78' : (tropChange < 0 ? '#f56565' : '#718096');
                const tropSign = tropChange > 0 ? '+' : '';
                const tropText = tropChange !== 0 ? tropSign + tropChange : '';

                content.innerHTML = `
                    <div class="cr-vs-row-premium-v2">
                        <div class="cr-battle-score-header-premium">
                            <div style="display:flex; flex-direction:column; align-items:center; gap:5px;">
                                <div class="cr-mode-tag-premium">${data.game_mode || 'Batalha'}</div>
                                <div style="font-size:0.75em; color:#94a3b8; font-weight:700; letter-spacing:1px; text-transform:uppercase;">${data.date || ''}</div>
                            </div>
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
                
                // Show modal
                modal.classList.add('active');
                document.body.style.overflow = 'hidden'; // Prevent scroll
                
                // Highlight badge in timeline
                const timeline = document.querySelector('.timeline-' + deckId);
                if (timeline) {
                    timeline.querySelectorAll('.cr-battle-badge').forEach((b, i) => {
                        if (i === battleIdx) {
                            b.style.boxShadow = '0 0 0 3px #4299e1';
                        } else {
                            b.style.boxShadow = 'none';
                        }
                    });
                }
            } catch(e) { console.error("Error updating preview:", e); }
        }

        function closeBattleModal() {
            const modal = document.getElementById('cr-battle-modal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = ''; // Restore scroll
            }
        }

        // Close on ESC and click outside
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeBattleModal();
        });

        document.addEventListener('click', (e) => {
            const modal = document.getElementById('cr-battle-modal');
            if (e.target === modal) closeBattleModal();
        });

        function updateOpponentView(oppId, element) {
            try {
                // Lê o JSON do data-attribute de forma segura
                const data = JSON.parse(element.getAttribute('data-battle'));
                
                // Atualiza Placar e Modo
                const pScoreEl = document.getElementById(`p-score-${oppId}`);
                const oScoreEl = document.getElementById(`o-score-${oppId}`);
                if (pScoreEl) pScoreEl.innerText = data.p_score;
                if (oScoreEl) oScoreEl.innerText = data.o_score;
                
                // Atualiza Metadados (Data e Modo)
                const dateEl = document.getElementById(`date-main-${oppId}`);
                const modeEl = document.getElementById(`mode-${oppId}`);
                if (dateEl) dateEl.innerText = '📅 ' + data.date;
                if (modeEl) modeEl.innerText = data.mode;
                
                // Atualiza Métricas (Vazamento, Nível, etc)
                const pMetricsEl = document.getElementById(`player-metrics-${oppId}`);
                const oMetricsEl = document.getElementById(`opp-metrics-${oppId}`);
                if (pMetricsEl) pMetricsEl.innerHTML = data.p_metrics;
                if (oMetricsEl) oMetricsEl.innerHTML = data.o_metrics;
                
                // Atualiza Grids de Decks
                const pGridEl = document.getElementById(`p-grid-${oppId}`);
                const oGridEl = document.getElementById(`o-grid-${oppId}`);
                if (pGridEl) pGridEl.innerHTML = data.p_grid;
                if (oGridEl) oGridEl.innerHTML = data.o_grid;
                
                // Atualiza Links de Cópia
                const pCopyEl = document.getElementById(`p-copy-${oppId}`);
                const oCopyEl = document.getElementById(`o-copy-${oppId}`);
                if (pCopyEl) pCopyEl.href = data.p_copy;
                if (oCopyEl) oCopyEl.href = data.o_copy;
                
                // Efeito visual de seleção na timeline
                const container = element.parentElement;
                container.querySelectorAll('.cr-date-selector').forEach(el => {
                    el.style.borderColor = '#1e293b';
                    el.style.background = '#020617';
                });
                element.style.borderColor = '#4299e1';
                element.style.background = '#1e293b'; // Fundo sólido destacado ao selecionar
                
            } catch(e) {
                console.error("Erro ao atualizar visualizacao do oponente:", e);
            }
        }
        
        function getMiniGridJS(deckStr, sideClass, playerName, clanName, metrics, deckLink, icons) {
            if (!deckStr) return `<div class="${sideClass} cr-empty-grid">N/D</div>`;
            let cards = deckStr.replace(/ \| /g, '|').split('|').filter(Boolean).slice(0, 8);
            const playerTower = "assets/images/towers/player_tower.png";
            const oppTower = "assets/images/towers/opp_tower.png";
            const towerImg = sideClass.includes('my') ? playerTower : oppTower;
            
            const cardsHtml = cards.map(c => {
                const name = c.trim();
                const cleanName = name.toLowerCase().replace(/\s+/g, '-').replace(/\./g, '').replace(/[()]/g, '');
                const url = CARD_MAP[name] || CARD_MAP[cleanName] || CARD_MAP[name.replace(/\s+/g, '')];
                
                if (url) {
                    return `<div class="cr-card-wrap-premium" title="${name}"><img src="${url}" class="cr-card-img" loading="lazy"></div>`;
                }
                
                // Fallback robusto usando CDN direta do RoyaleAPI
                const slug = cleanName.replace('the-log', 'log').replace('p-e-k-k-a', 'pekka');
                return `<div class="cr-card-wrap-premium" title="${name}"><img src="https://royaleapi.github.io/cr-api-assets/cards/${slug}.png" class="cr-card-img" onerror="this.src='https://royaleapi.com/static/img/cards-150/${slug}.png'" loading="lazy"></div>`;
            }).join('');
            
            const avg = metrics ? metrics.avg : '--';
            const cycle = metrics ? metrics.cycle : '--';
            const leaked = metrics ? (metrics.leaked || 0) : 0;
            const tLevel = metrics ? (metrics.level || 14) : 14;
            let tHP = metrics ? (metrics.hp || '--') : '--';
            if (tHP !== '--' && !isNaN(tHP)) {
                tHP = Number(tHP).toLocaleString('pt-BR');
            }
            const leakedColor = leaked > 0 ? '#f56565' : '#48bb78';

            const clanHtml = clanName ? `<div class="cr-clan-name-premium">${clanName}</div>` : '';
            
            const copyBtnHtml = (deckLink && deckLink !== '#') ?
                `<a href="${deckLink}" class="cr-copy-deck-btn" title="Copiar Deck para o Jogo" onclick="showCopyToast(event)">
                    <span style="font-size:1.2em;">📋</span> Copiar Deck
                </a>` : '';

            return `
                <div class="cr-deck-side ${sideClass}">
                    <div class="cr-player-header-premium">
                        <div class="cr-player-name-premium">${playerName}</div>
                        ${clanHtml}
                    </div>
                    <div class="cr-tower-container-premium">
                        <img src="${towerImg}" class="cr-tower-img-premium" onerror="this.src='https://static.wikia.nocookie.net/character-catalogue/images/c/cf/Tower_Princess.png/revision/latest?cb=20231217222258'">
                        <div class="cr-tower-info-premium">HP ${tHP} (Lvl ${tLevel})</div>
                    </div>
                    <div class="cr-grid-4x2">
                        ${cardsHtml}
                    </div>
                    <div style="margin-top:15px; margin-bottom:10px; width:100%; display:flex; justify-content:center;">
                        ${copyBtnHtml}
                    </div>
                    <div class="cr-deck-metrics-premium" style="background: #020617; border-radius:15px; padding:10px; border:1px solid #1e293b;">
                        <div class="cr-metric-item-p" title="Media Elixir" style="color:#fff; font-weight:700;"><span class="cr-metric-icon">💧</span> ${avg}</div>
                        <div class="cr-metric-item-p" title="Ciclo 4 Cartas" style="color:#fff;"><span class="cr-metric-icon">🔄</span> ${cycle}</div>
                        <div class="cr-metric-item-p" title="Elixir Vazado" style="color: ${leakedColor}; font-weight:800;"><span class="cr-metric-icon">🚫</span> ${leaked}</div>
                    </div>
                </div>`;
        }

        function showCopyToast(e) {
            const toast = document.createElement('div');
            toast.textContent = 'Aguardando abertura no jogo...';
            toast.style.position = 'fixed';
            toast.style.bottom = '20px';
            toast.style.left = '50%';
            toast.style.transform = 'translateX(-50%)';
            toast.style.background = 'rgba(72, 187, 120, 0.95)';
            toast.style.color = '#fff';
            toast.style.padding = '12px 24px';
            toast.style.borderRadius = '50px';
            toast.style.fontWeight = 'bold';
            toast.style.zIndex = '9999';
            toast.style.boxShadow = '0 5px 15px rgba(0,0,0,0.4)';
            toast.style.backdropFilter = 'blur(10px)';
            toast.style.fontFamily = "'Outfit', sans-serif";
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.5s ease';
                setTimeout(() => toast.remove(), 500);
            }, 3000);
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
        """Gera HTML para oponentes repetidos com match cards inline."""
        if not opponents: return '<div class="cr-empty-state">Nenhum oponente repetido encontrado no histórico recente.</div>'
        
        player_name = self.player_name_override or next((p.get('name', 'Jogador') for p in self.players_cache if p.get('player_tag') == self.player_tag), 'Jogador')
        
        html = '<div class="cr-opponents-list" style="display:flex; flex-direction:column; gap:40px;">'
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
            
            w_p = round((wins/total*100),1) if total > 0 else 0
            l_p = round((losses/total*100),1) if total > 0 else 0
            d_p = round((draws/total*100),1) if total > 0 else 0
            
            stats_list = opp['stats']
            wr_c = '#48bb78' if wr >= 60 else ('#f56565' if wr <= 40 else '#718096')
            
            # Única área de visualização principal (Palco VS)
            first_b = stats_list[0]
            my_crowns_f = first_b.get('crowns', 0)
            opp_crowns_f = first_b.get('opponent_crowns', 0)
            my_metrics_f = self._get_battle_deck_metrics(first_b['my_deck'], first_b, is_opponent=False)
            opp_metrics_f = self._get_battle_deck_metrics(first_b['opp_deck'], first_b, is_opponent=True)
            my_deck_list_f = [c.strip() for c in first_b.get('my_deck', '').replace(' | ', '|').split('|') if c.strip()][:8]
            opp_deck_list_f = [c.strip() for c in first_b.get('opp_deck', '').replace(' | ', '|').split('|') if c.strip()][:8]
            
            html += f'''
            <div class="cr-deck-card" id="opp-section-{i}" style="width:100%; max-width:none; background: #0f172a; border-radius: 24px; border: 1px solid rgba(255,255,255,0.05); overflow:hidden;">
                <div class="cr-deck-header" style="padding: 20px 30px; background: rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
                        <div class="cr-deck-meta">
                            <span class="cr-deck-rank">#{i}</span>
                            <span class="cr-deck-label" style="font-size:1.4em; color:#fff; font-weight:800;">{opp['opponent_name']}</span>
                            <span class="rival-badge {cat_class}-badge">{category}</span>
                        </div>
                        <div style="text-align:right;">
                            <span style="font-size:0.8em;color:#94a3b8;font-family:monospace;display:block;">{opp['opponent_tag']}</span>
                            <span class="cr-wr-badge" style="background:{wr_c}; color:#fff; font-size:0.9em; margin-top:5px;">{wr}% WR ({wins}V - {draws}E - {losses}D)</span>
                        </div>
                    </div>
                </div>

                <!-- ÁREA PRINCIPAL DINÂMICA (PALCO VS) -->
                <div class="cr-main-vs-stage" id="main-vs-{i}" style="padding: 30px; background: #0f172a; border-top: 1px solid rgba(255,255,255,0.05);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 25px;">
                        <!-- Player Header -->
                        <div style="flex:1; text-align:center;">
                            <div style="color:#4299e1; font-weight:900; font-size:1.3em; margin-bottom:5px;">{player_name}</div>
                            <div style="font-size:0.8em; color:#94a3b8;" id="player-metrics-{i}">
                                Torre Lv {first_b.get('player_tower_level', 14)} | Vazado: <span style="color:{my_metrics_f['leaked_color']};">{my_metrics_f['leaked_label']}</span><br>
                                Custo: <b>{my_metrics_f['avg']}</b> | Ciclo: <b>{my_metrics_f['cycle']}</b>
                            </div>
                        </div>
                        
                        <!-- Score Center -->
                        <div style="flex:0 0 200px; text-align:center;">
                            <div style="color:#94a3b8; font-size:0.7em; font-weight:800; text-transform:uppercase; letter-spacing:2px; margin-bottom:10px;" id="mode-{i}">{first_b.get('game_mode', 'Batalha')}</div>
                            <div style="display:flex; align-items:center; justify-content:center; gap:15px; background:#050914; padding:10px 20px; border-radius:50px; border:1px solid rgba(255,255,255,0.15);">
                                <span style="font-size:2.2em; font-weight:900; color:#4299e1;" id="p-score-{i}">{my_crowns_f}</span>
                                <span style="color:rgba(255,255,255,0.3); font-weight:900; font-size:1.5em;">-</span>
                                <span style="font-size:2.2em; font-weight:900; color:#f56565;" id="o-score-{i}">{opp_crowns_f}</span>
                            </div>
                            <div style="color:#a0aec0; font-size:0.8em; font-weight:700; margin-top:10px;" id="date-main-{i}">📅 {first_b.get('data_str', '--/--')}</div>
                        </div>

                        <!-- Opponent Header -->
                        <div style="flex:1; text-align:center;">
                            <div style="color:#f56565; font-weight:900; font-size:1.3em; margin-bottom:5px;">{opp['opponent_name']}</div>
                            <div style="font-size:0.8em; color:#94a3b8;" id="opp-metrics-{i}">
                                Torre Lv {first_b.get('opp_tower_level', 14)} | Vazado: <span style="color:{opp_metrics_f['leaked_color']};">{opp_metrics_f['leaked_label']}</span><br>
                                Custo: <b>{opp_metrics_f['avg']}</b> | Ciclo: <b>{opp_metrics_f['cycle']}</b>
                            </div>
                        </div>
                    </div>

                    <div class="cr-vs-decks-row-premium" style="display:grid; grid-template-columns: 1fr 40px 1fr; align-items:center; gap:20px;">
                        <div class="cr-grid-4x2" id="p-grid-{i}">
                            {"".join(f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(c)}" class="cr-card-img"><div class="cr-card-level">L 15</div></div>' for c in my_deck_list_f)}
                        </div>
                        <div style="text-align:center; font-weight:900; color:rgba(255,255,255,0.05); font-size:2em;">VS</div>
                        <div class="cr-grid-4x2" id="o-grid-{i}">
                            {"".join(f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(c)}" class="cr-card-img"><div class="cr-card-level">L 15</div></div>' for c in opp_deck_list_f)}
                        </div>
                    </div>

                    <div style="display:flex; justify-content:space-between; margin-top:25px; padding: 0 40px;">
                        <a href="{self.get_copy_deck_link(my_deck_list_f)}" id="p-copy-{i}" target="_blank" class="cr-copy-deck-btn"><span>📋</span> COPIAR DECK</a>
                        <a href="{self.get_copy_deck_link(opp_deck_list_f)}" id="o-copy-{i}" target="_blank" class="cr-copy-deck-btn" style="background:linear-gradient(135deg, rgba(245, 101, 101, 0.2) 0%, rgba(229, 62, 62, 0.4) 100%); border-color:rgba(245, 101, 101, 0.4);"><span>📋</span> COPIAR DECK</a>
                    </div>
                </div>

                <!-- LISTA DE SELEÇÃO DE DATA (TIMELINE) -->
                <div style="background: #050914; padding: 15px 30px; border-top: 1px solid rgba(255,255,255,0.15);">
                    <div style="color:#94a3b8; font-size:0.7em; font-weight:800; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px;">Histórico de Confrontos (Clique na data para alternar)</div>
                    <div style="display:flex; gap:10px; overflow-x:auto; padding-bottom:10px; scrollbar-width: thin;">
            '''

            for idx, b in enumerate(stats_list[:30]): # Aumentado para 30 partidas
                res = b['resultado'].lower()
                d_str = b.get('data_str', '--/--')
                cor = '#48bb78' if res in ['vitoria','victory'] else ('#f56565' if res in ['derrota','defeat'] else '#ed8936')
                ic = 'V' if res in ['vitoria','victory'] else ('D' if res in ['derrota','defeat'] else 'E')
                
                # Dados para o JS de troca
                m_metrics = self._get_battle_deck_metrics(b['my_deck'], b, is_opponent=False)
                o_metrics = self._get_battle_deck_metrics(b['opp_deck'], b, is_opponent=True)
                
                b_json = json.dumps({
                    'p_score': b.get('crowns', 0),
                    'o_score': b.get('opponent_crowns', 0),
                    'p_metrics': f"Torre Lv {b.get('player_tower_level', 14)} | Vazado: <span style='color:{m_metrics['leaked_color']};'>{m_metrics['leaked_label']}</span><br>Custo: <b>{m_metrics['avg']}</b> | Ciclo: <b>{m_metrics['cycle']}</b>",
                    'o_metrics': f"Torre Lv {b.get('opp_tower_level', 14)} | Vazado: <span style='color:{o_metrics['leaked_color']};'>{o_metrics['leaked_label']}</span><br>Custo: <b>{o_metrics['avg']}</b> | Ciclo: <b>{o_metrics['cycle']}</b>",
                    'p_grid': "".join(f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(c)}" class="cr-card-img"><div class="cr-card-level">L 15</div></div>' for c in [cx.strip() for cx in b['my_deck'].replace(' | ', '|').split('|') if cx.strip()][:8]),
                    'o_grid': "".join(f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(c)}" class="cr-card-img"><div class="cr-card-level">L 15</div></div>' for c in [cx.strip() for cx in b['opp_deck'].replace(' | ', '|').split('|') if cx.strip()][:8]),
                    'p_copy': self.get_copy_deck_link([cx.strip() for cx in b['my_deck'].replace(' | ', '|').split('|') if cx.strip()][:8]),
                    'o_copy': self.get_copy_deck_link([cx.strip() for cx in b['opp_deck'].replace(' | ', '|').split('|') if cx.strip()][:8]),
                    'date': d_str,
                    'mode': b.get('game_mode', 'Batalha')
                }).replace("'", "&apos;")

                html += f'''
                        <div class="cr-date-selector" onclick="updateOpponentView({i}, this)" data-battle='{b_json}' style="flex:0 0 auto; display:flex; align-items:center; gap:8px; padding: 8px 12px; background:#1e293b; border:1px solid #475569; border-radius:10px; cursor:pointer; transition:all 0.2s;">
                            <span style="background:{cor}; width:18px; height:18px; font-size:0.6em; display:flex; align-items:center; justify-content:center; border-radius:4px; font-weight:900; color:#fff;">{ic}</span>
                            <span style="color:#94a3b8; font-size:0.75em; font-weight:700;">📅 {d_str}</span>
                        </div>'''

            html += f'''
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
            <div class="cr-deck-card" style="padding:20px; border-left: 5px solid #e53e3e; background: #0f172a;">
                <div class="cr-deck-header" style="background: rgba(229, 62, 62, 0.1); border-bottom: 1px solid rgba(229, 62, 62, 0.2);">
                    <div class="cr-deck-meta">
                        <span class="cr-deck-rank" style="background:#e53e3e;">#{i} MAIS LETAL</span>
                        <span class="cr-deck-label" style="font-weight:800; color:#fff;">Causou {losses} derrotas</span>
                    </div>
                </div>
                <div class="cr-deck-body" style="display: flex; flex-direction: row; gap: 25px; align-items: flex-start; padding-top:20px;">
                    <div style="flex: 0 0 280px;">
                        <div class="cr-grid-4x2">
                            {"".join(f'<div class="cr-card-wrap-premium" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img" loading="lazy"></div>' for c in c_list[:8])}
                        </div>
                    </div>
                    <div class="cr-stats-panel" style="flex:1;">
                        <div style="font-size:0.95em; color:#e2e8f0; margin-bottom:12px; line-height:1.5;">
                            <strong style="color:#f56565;">Usuários comuns:</strong><br>{opponents}
                        </div>
                        <div style="font-size:0.85em; color:#94a3b8; margin-bottom:15px;">
                            <strong>Última derrota:</strong> {last}
                        </div>
                        <div style="background: rgba(229, 62, 62, 0.2); color:#feb2b2; font-size:0.75em; padding:8px 12px; border-radius:8px; font-weight:800; text-transform:uppercase; border: 1px solid rgba(229, 62, 62, 0.3); letter-spacing:0.5px;">
                            ⚠️ ALERTA: Counter de Alta Periculosidade
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
        """Busca os melhores jogadores (Clã e Global) do arquivo de guerra, exibindo todos os decks."""
        war_decks_path = os.path.join(self.src_dir, "data_csv_oficial", "war_decks_top_players.csv")
        players = {'clan': [], 'global': []}
        
        if not os.path.exists(war_decks_path):
            return players
            
        try:
            temp_players = []
            with open(war_decks_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                all_rows = list(reader)
                
                if not all_rows: return players
                
                # Encontra a data mais recente
                dates = [row['data_coleta'] for row in all_rows if row.get('data_coleta')]
                if not dates: return players
                max_date = max(dates, key=lambda d: datetime.strptime(d, "%d/%m/%Y"))
                
                for row in all_rows:
                    if row.get('data_coleta') != max_date:
                        continue
                        
                    # Pega os 4 decks
                    player_decks = []
                    for i in range(1, 5):
                        deck_str = row.get(f'deck_{i}', '')
                        if deck_str and deck_str != "N/A":
                            cards = [c.strip() for c in deck_str.split('|')]
                            if len(cards) == 8:
                                player_decks.append(cards)
                    
                    if not player_decks: continue
                    
                    # Tenta extrair win rate do campo resultado_dia (ex: "3V 1D")
                    res = row.get('resultado_dia', '0V 0D')
                    v = 0
                    d = 0
                    wr = 0.0
                    try:
                        res_parts = res.split(' ')
                        v_str = res_parts[0].replace('V', '').strip()
                        v = int(v_str) if v_str.isdigit() else 0
                        if len(res_parts) > 1:
                            d_str = res_parts[1].replace('D', '').strip()
                            d = int(d_str) if d_str.isdigit() else 0
                        
                        if (v + d) > 0:
                            wr = (v / (v + d)) * 100
                    except: pass

                    player_data = {
                        'name': row.get('nome_jogador', 'Unknown'),
                        'tag': row.get('tag_jogador', ''),
                        'win_rate': wr,
                        'total_battles': v + d,
                        'decks': player_decks,
                        'type': 'clan' if 'Cla' in row.get('categoria_top', '') else 'global',
                        'pos': int(row.get('posicao_no_top', 99))
                    }
                    temp_players.append(player_data)
            
            # Ordena por posição
            temp_players.sort(key=lambda x: x['pos'])
            
            for p in temp_players:
                if p['type'] == 'clan':
                    players['clan'].append(p)
                else:
                    players['global'].append(p)
                    
        except Exception as e:
            print(f"Erro ao carregar decks de guerra: {e}")
            
        # Aumenta o limite para mostrar mais jogadores do clã
        players['clan'] = players['clan'][:15]
        players['global'] = players['global'][:10]
        return players

    def get_meta_brasil_data(self):
        """Lê os dados do ranking Top 100 Brasil do JSON com filtro de reset."""
        file_path = os.path.join(self.src_dir, "data_csv_oficial", "meta_brasil_top100.json")
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                items = data.get('items', [])
                collected_at_str = data.get('collected_at', '')
                
                # Regra de Reset de Temporada:
                # Se hoje é a 1ª segunda do mês (dia <= 7) e coletado antes das 12h BRT, ignorar
                if collected_at_str:
                    try:
                        coll_dt = datetime.strptime(collected_at_str, '%Y-%m-%dT%H:%M:%S')
                        # Se collected_at for antes das 12h no dia do reset, retornamos vazio
                        # para evitar exibir ranking instável
                        if coll_dt.weekday() == 0 and coll_dt.day <= 7 and coll_dt.hour < 12:
                            logger.info(f"Dados do Meta Brasil de {collected_at_str} ignorados por estarem antes do reset (12h).")
                            return []
                    except: pass
                
                return items
        except Exception as e:
            print(f"Erro ao ler meta_brasil_top100.json: {e}")
            return []

    def get_war_intelligence_data(self):
        """Coleta dados de inteligência de guerra (Dia 4)."""
        data = {
            'boats': [],
            'rivals': {},
            'difficulty': 'Indeterminada',
            'summary': '',
            'my_clan': 'Desconhecido'
        }
        
        # 1. Busca status dos barcos (mais recente)
        import glob
        boat_files = glob.glob(os.path.join(self.src_dir, "data_clan", "status_barcos_*.csv"))
        if boat_files:
            latest_boat = max(boat_files)
            try:
                with open(latest_boat, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    data['boats'] = list(reader)
            except: pass
            
        # 2. Busca inteligência de oponentes
        intel_files = glob.glob(os.path.join(self.src_dir, "data_clan", "inteligencia_guerra_*.csv"))
        if intel_files:
            latest_intel = max(intel_files)
            try:
                with open(latest_intel, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        cla = row.get('Cla', 'Unknown')
                        if cla not in data['rivals']:
                            data['rivals'][cla] = []
                        if len(data['rivals'][cla]) < 3: # Top 3 jogadores por clã
                            data['rivals'][cla].append(row)
            except: pass
            
        # 3. Identifica clã do jogador via players.csv
        my_clan = "Tropa Do Bruxo" # Default seguro
        try:
            players_file = os.path.join(self.src_dir, "data_csv_oficial", "players.csv")
            if os.path.exists(players_file):
                with open(players_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        if row.get('player_tag'): # Pega o primeiro jogador válido (o dono do dashboard)
                            my_clan = row.get('clan_name', my_clan)
                            break
        except: pass

        # 4. Cálculo de Dificuldade
        my_fame = 0
        leader_fame = 0
        for boat in data['boats']:
            fame_val = boat.get('Fama_Atual', '0')
            try:
                # Remove separadores de milhar se houver
                fame = int(fame_val.replace(',', '').replace('.', '')) if fame_val else 0
            except:
                fame = 0
                
            if boat.get('Nome_Cla') == my_clan:
                my_fame = fame
            if fame > leader_fame:
                leader_fame = fame
        
        data['my_clan'] = my_clan
        diff = leader_fame - my_fame
        if diff > 20000: data['difficulty'] = 'Extrema 🔴'
        elif diff > 10000: data['difficulty'] = 'Alta 🟠'
        elif diff > 5000: data['difficulty'] = 'Moderada 🟡'
        else: data['difficulty'] = 'Baixa 🟢'
        
        data['summary'] = f"O clã <strong>{my_clan}</strong> está a {diff:,} pontos de fama do 1º lugar. Foco total em ataques de alto valor."
        return data

    def generate_war_intelligence_html(self, data):
        """Gera o HTML para a seção de Inteligência de Guerra."""
        if not data['boats']:
            return ""
            
        # Meta de fama (ex: 50.000 para terminar a corrida)
        FAME_GOAL = 50000
        
        # Cálculo de vantagem estratégica para alertas táticos
        my_fame = 0
        for b in data['boats']:
            if b.get('Nome_Cla') == data.get('my_clan', 'Desconhecido'):
                try:
                    my_fame = int(b.get('Fama_Atual', '0').replace(',', '').replace('.', ''))
                except: pass
                break
        
        # Detecção de Reset da Temporada (Primeira segunda-feira do mês)
        is_reset_day = False
        today_dt = datetime.now()
        if today_dt.weekday() == 0 and today_dt.day <= 7:
            is_reset_day = True

        intel_alerts = ""
        if is_reset_day:
            intel_alerts += f"<div class='intel-alert' style='background: #fef3c7; border-left: 4px solid #d97706; color: #92400e;'><strong>📅 DIA DE RESET:</strong> Temporada nova iniciada! Foco em subir troféus e garantir as primeiras vitórias na guerra.</div>"

        for b in data['boats']:
            if b.get('Nome_Cla') != data.get('my_clan', 'Desconhecido'):
                try:
                    rival_fame = int(b.get('Fama_Atual', '0').replace(',', '').replace('.', ''))
                    diff_val = my_fame - rival_fame
                    if diff_val > 0:
                        intel_alerts += f"<div class='intel-alert positive'>Vantagem de <strong>{diff_val:,}</strong> sobre {b.get('Nome_Cla')}</div>"
                    else:
                        intel_alerts += f"<div class='intel-alert negative'>Atrás de {b.get('Nome_Cla')} por <strong>{abs(diff_val):,}</strong></div>"
                except: pass

        boat_rows = ""
        for b in data['boats']:
            is_me = "highlight-row" if b.get('Nome_Cla') == data.get('my_clan', 'Desconhecido') else ""
            try:
                fame_val = int(b.get('Fama_Atual', '0').replace(',', '').replace('.', ''))
            except:
                fame_val = 0
            
            # Progresso visual
            percent = min(100, (fame_val / FAME_GOAL) * 100)
            status_color = "#48bb78" if b.get('Finalizado') == 'Sim' else "#3b82f6"
            
            # Posicao amigável (evita Noneº)
            pos_val = b.get('Posicao')
            pos_display = f"{pos_val}º" if pos_val and str(pos_val).isdigit() else "-"
            
            boat_rows += f"""
                <tr class="{is_me}">
                    <td style="width: 50px;">{pos_display}</td>
                    <td>
                        <div class="clan-fame-info">
                            <strong>{b.get('Nome_Cla')}</strong>
                            <div class="fame-progress-bar">
                                <div class="fame-progress-fill" style="width: {percent}%; background: {status_color};"></div>
                            </div>
                        </div>
                    </td>
                    <td style="text-align: right; font-family: monospace;">{fame_val:,}</td>
                    <td style="text-align: center;">{"✅" if b.get('Finalizado') == 'Sim' else "⚓"}</td>
                </tr>
            """
            
        rival_cards = ""
        for cla, players in data['rivals'].items():
            if cla == data.get('my_clan', 'Desconhecido'): continue
            
            player_list = "".join([f"<li><span class='rival-name'>{p['Jogador']}</span> <span class='rival-fame'>+{p['Fama_Hoje']}</span></li>" for p in players])
            rival_cards += f"""
                <div class="rival-mini-card">
                    <h4>{cla}</h4>
                    <ul>{player_list}</ul>
                </div>
            """
            
        # Título dinâmico baseado no dia da semana (Guerra: Qui=3 a Dom=6 + Seg=0 para Reset)
        weekday = datetime.now().weekday()
        war_day_map = {0: "Reset", 3: "1", 4: "2", 5: "3", 6: "4"}
        day_suffix = f": Dia {war_day_map[weekday]}" if weekday in war_day_map else ""

        return f"""
        <div class="section war-intel-section">
            <div class="elite-header">
                <div class="elite-badge" style="background: #ef4444;">RADAR DE GUERRA</div>
                <h2>📡 Inteligência de Guerra{day_suffix}</h2>
                <p>Status da corrida fluvial e monitoramento de ameaças dos clãs rivais.</p>
            </div>
            
            <div class="war-grid">
                <div class="war-status-container">
                    <h3>🏆 Corrida Fluvial</h3>
                    <table class="war-intel-table">
                        <thead>
                            <tr><th>Pos</th><th>Clã / Progresso</th><th style="text-align: right;">Fama</th><th>Status</th></tr>
                        </thead>
                        <tbody>{boat_rows}</tbody>
                    </table>
                </div>
                
                <div class="war-analysis">
                    <div class="intel-summary-cards">
                        <div class="intel-card diff-card">
                            <span class="label">Nível de Ameaça</span>
                            <span class="value">{data['difficulty']}</span>
                        </div>
                        <div class="intel-card info-card">
                            <span class="label">Análise Tática</span>
                            <div class="intel-alerts-box">{intel_alerts}</div>
                        </div>
                    </div>
                    
                    <div class="rivals-container">
                        <h3>☢️ Maiores Ameaças Inimigas</h3>
                        <div class="rival-cards-grid">
                            {rival_cards}
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
                .war-intel-section {{ border-left: 5px solid #ef4444 !important; background: rgba(30, 20, 20, 0.9) !important; }}
                .war-grid {{ display: grid; grid-template-columns: 1.2fr 1fr; gap: 30px; margin-top: 20px; }}
                
                .war-intel-table {{ width: 100%; border-collapse: collapse; }}
                .war-intel-table th {{ text-align: left; padding: 12px; color: #94a3b8; font-size: 0.8em; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.1); }}
                .war-intel-table td {{ padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); vertical-align: middle; }}
                
                .clan-fame-info {{ display: flex; flex-direction: column; gap: 5px; }}
                .fame-progress-bar {{ height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; width: 100%; max-width: 200px; }}
                .fame-progress-fill {{ height: 100%; transition: width 1s ease-out; }}
                
                .intel-summary-cards {{ display: grid; grid-template-columns: 1fr; gap: 15px; margin-bottom: 25px; }}
                .intel-card {{ background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); }}
                .intel-card .label {{ display: block; font-size: 0.75em; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-bottom: 5px; }}
                .intel-card .value {{ font-size: 1.3em; font-weight: 800; }}
                
                .intel-alerts-box {{ display: flex; flex-direction: column; gap: 8px; }}
                .intel-alert {{ font-size: 0.85em; padding: 8px 12px; border-radius: 6px; border-left: 3px solid transparent; }}
                .intel-alert.positive {{ background: rgba(72, 187, 120, 0.1); color: #48bb78; border-left-color: #48bb78; }}
                .intel-alert.negative {{ background: rgba(248, 113, 113, 0.1); color: #f87171; border-left-color: #f87171; }}
                
                /* Estilos Copiador de Decks */
                .deck-label-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
                .copy-deck-btn {{ 
                    background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
                    color: white;
                    text-decoration: none;
                    font-size: 0.7em;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-weight: bold;
                    transition: all 0.2s;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }}
                .copy-deck-btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.3); opacity: 0.9; }}
                
                .highlight-row {{ background: rgba(59, 130, 246, 0.1) !important; }}
                .highlight-row strong {{ color: #60a5fa; }}
                
                .rival-cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }}
                .rival-mini-card {{ background: rgba(0,0,0,0.2); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05); }}
                .rival-mini-card h4 {{ font-size: 0.85em; color: #f87171; margin-bottom: 8px; border-bottom: 1px solid rgba(248, 113, 113, 0.2); padding-bottom: 4px; }}
                .rival-mini-card ul {{ list-style: none; padding: 0; margin: 0; }}
                .rival-mini-card li {{ font-size: 0.8em; margin-bottom: 5px; display: flex; justify-content: space-between; }}
                .rival-name {{ color: #e2e8f0; }}
                .rival-fame {{ color: #48bb78; font-weight: bold; font-family: monospace; }}
                
                @media (max-width: 1000px) {{ .war-grid {{ grid-template-columns: 1fr; }} }}
            </style>
        </div>
        """

    def generate_war_decks_html(self, war_players):
        """Gera o HTML para a seção de Decks de Elite (Guerra) e Meta Brasil."""
        meta_br = self.get_meta_brasil_data()
        
        if not war_players['clan'] and not war_players['global'] and not meta_br:
            return ""

        html = """
        <div class="section elite-spy-section">
            <div class="elite-header">
                <div class="elite-badge">TOP SECRET</div>
                <h2>🕵️ Elite Spy: Guerra & Meta Brasil</h2>
                <p>Inteligência competitiva: os melhores decks do clã, do ranking global de guerra e o Top 100 Brasil.</p>
            </div>
            
            <div class="deck-tabs">
                <button class="tab-button active" onclick="showWarTab('clan-war')">Nossos Heróis</button>
                <button class="tab-button" onclick="showWarTab('global-war')">Meta Global (Guerra)</button>
                <button class="tab-button" onclick="showWarTab('meta-br')">Top 100 Brasil</button>
            </div>

            <div id="clan-war" class="tab-content active">
                <div class="cr-decks-list">
        """

        # Aba 1: Nossos Heróis
        for player in war_players['clan']:
            decks_html = ""
            for i, deck in enumerate(player['decks']):
                if not deck or len(deck) < 8: continue
                cards_html = "".join([f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(card)}" class="cr-card-img" title="{card}"></div>' for card in deck])
                copy_link = self.get_copy_deck_link(deck)
                
                decks_html += f"""
                    <div class="deck-row" style="margin-bottom: 20px;">
                        <div class="deck-label-row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <span class="deck-label" style="color:#94a3b8; font-weight:800; font-size:0.8em; text-transform:uppercase;">Deck {i+1}</span>
                            <a href="{copy_link}" class="cr-copy-deck-btn" style="padding: 4px 12px; font-size:0.75em;">Copiar</a>
                        </div>
                        <div class="cr-grid-4x2" style="margin:0; padding:10px; gap:8px;">{cards_html}</div>
                    </div>
                """

            html += f"""
                <div class="cr-deck-card war-player-card">
                    <div class="cr-deck-header">
                        <div class="player-info">
                            <span class="cr-player-name">{player['name']}</span>
                            <span class="cr-wr-badge">{player['win_rate']:.1f}% WR</span>
                        </div>
                        <span class="cr-deck-rank">Pos #{player['pos']} | {player['total_battles']} Lutas</span>
                    </div>
                    <div class="cr-deck-body">
                        {decks_html}
                    </div>
                </div>
            """

        html += """
                </div>
            </div>

            <div id="global-war" class="tab-content">
                <div class="cr-decks-list">
        """

        # Aba 2: Meta Global (Guerra)
        for player in war_players['global']:
            decks_html = ""
            for i, deck in enumerate(player['decks']):
                if not deck or len(deck) < 8: continue
                cards_html = "".join([f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(card)}" class="cr-card-img" title="{card}"></div>' for card in deck])
                copy_link = self.get_copy_deck_link(deck)

                decks_html += f"""
                    <div class="deck-row" style="margin-bottom: 20px;">
                        <div class="deck-label-row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <span class="deck-label" style="color:#94a3b8; font-weight:800; font-size:0.8em; text-transform:uppercase;">Deck {i+1}</span>
                            <a href="{copy_link}" class="cr-copy-deck-btn" style="padding: 4px 12px; font-size:0.75em;">Copiar</a>
                        </div>
                        <div class="cr-grid-4x2" style="margin:0; padding:10px; gap:8px;">{cards_html}</div>
                    </div>
                """

            html += f"""
                <div class="cr-deck-card war-player-card">
                    <div class="cr-deck-header">
                        <div class="player-info">
                            <span class="cr-player-name">{player['name']}</span>
                            <span class="cr-wr-badge">{player['win_rate']:.1f}% WR</span>
                        </div>
                        <span class="cr-deck-rank">RANK GLOBAL</span>
                    </div>
                    <div class="cr-deck-body">
                        {decks_html}
                    </div>
                </div>
            """

        html += """
                </div>
            </div>

            <div id="meta-br" class="tab-content">
                <div class="meta-br-container">
                    <table class="meta-br-table">
                        <thead>
                            <tr>
                                <th>Pos</th>
                                <th>Jogador</th>
                                <th>Clã</th>
                                <th>Troféus/Medalhas</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        for p in meta_br[:50]: # Mostra top 50 para não ficar muito longo
            rank = p.get('rank', '-')
            name = p.get('name', 'N/D')
            clan = p.get('clan', {}).get('name', '-')
            score = p.get('trophies') or p.get('score') or '-'
            
            html += f"""
                <tr>
                    <td><strong>#{rank}</strong></td>
                    <td><span class="player-name-cell">{name}</span></td>
                    <td><span class="clan-name-cell">{clan}</span></td>
                    <td><span class="score-cell">{score} 🏆</span></td>
                </tr>
            """
            
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
            
            <style>
                .war-player-card { width: 100% !important; }
                .deck-row { margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 10px; }
                .deck-row:last-child { border-bottom: none; margin-bottom: 0; }
                .deck-label { font-size: 0.7em; color: #94a3b8; text-transform: uppercase; margin-bottom: 5px; font-weight: bold; }
                .cr-decks-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; }
                
                /* Estilo Meta BR */
                .meta-br-container { background: #0f172a; border-radius: 15px; padding: 20px; margin-top: 10px; border: 1px solid #1e293b; }
                .meta-br-table { width: 100%; border-collapse: collapse; color: #e2e8f0; }
                .meta-br-table th { text-align: left; padding: 12px; border-bottom: 2px solid #1e293b; color: #94a3b8; }
                .meta-br-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }
                .player-name-cell { color: #f6e05e; font-weight: bold; }
                .score-cell { color: #63b3ed; font-weight: 800; }
                
                @media (max-width: 600px) {
                    .cr-decks-list { grid-template-columns: 1fr; }
                    .war-player-card { max-width: 100%; }
                }
            </style>
        </div>
        <script>
            function showWarTab(tabId) {
                const section = document.querySelector('.elite-spy-section');
                section.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                section.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
                section.querySelector('#' + tabId).classList.add('active');
                event.currentTarget.classList.add('active');
            }
        </script>
        """
        return html

    
    def generate_chests_html(self) -> str:
        """Gera o HTML para a seção de próximos baús."""
        if not self.upcoming_chests:
            return ""
        
        chests_items = ""
        # Mapeamento de icones para baus
        chest_icons = {
            'Silver Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-silver.png',
            'Gold Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-gold.png',
            'Magical Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-magical.png',
            'Giant Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-giant.png',
            'Mega Lightning Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-megalightning.png',
            'Epic Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-epic.png',
            'Legendary Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-legendary.png',
            'Lightning Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-lightning.png',
            'Fortune Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-fortune.png',
            'Wild Chest': 'https://royaleapi.github.io/cr-api-assets/chests/chest-wild.png',
            'Gold Crate': 'https://royaleapi.github.io/cr-api-assets/chests/chest-goldcrate.png',
            'Overflowing Gold Crate': 'https://royaleapi.github.io/cr-api-assets/chests/chest-goldcrate-overflowing.png',
            'Plentiful Gold Crate': 'https://royaleapi.github.io/cr-api-assets/chests/chest-goldcrate-plentiful.png'
        }

        for chest in self.upcoming_chests[:12]:
            name = chest.get('name', 'Unknown')
            index = chest.get('index', 0)
            icon = chest_icons.get(name, 'https://royaleapi.github.io/cr-api-assets/chests/chest-silver.png')
            
            # Formatação do texto da posição
            pos_text = f"+{index}" if index > 0 else "Próximo"
            
            chests_items += f"""
                <div class="chest-card">
                    <img src="{icon}" alt="{name}" onerror="this.src='https://royaleapi.github.io/cr-api-assets/chests/chest-silver.png'">
                    <div class="chest-name">{name.replace('Chest', '').replace('Crate', '').strip()}</div>
                    <div class="chest-index">{pos_text}</div>
                </div>
            """
            
        return f"""
        <div class="section">
            <h2>🎁 Próximos Baús</h2>
            <div class="chests-container">
                {chests_items}
            </div>
        </div>
        <style>
            .chests-container {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}
            .chest-card {{
                background: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 15px;
                text-align: center;
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: transform 0.2s;
            }}
            .chest-card:hover {{ transform: translateY(-5px); background: rgba(255, 255, 255, 0.1); }}
            .chest-card img {{ width: 60px; height: 60px; object-fit: contain; margin-bottom: 8px; }}
            .chest-name {{ font-size: 0.8em; color: #94a3b8; margin-bottom: 4px; }}
            .chest-index {{ font-weight: bold; color: #fff; }}
        </style>
        """

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
            
            # Nova Seção: Inteligência de Guerra (Dia 4)
            war_intel_data = self.get_war_intelligence_data()
            war_intel_html = self.generate_war_intelligence_html(war_intel_data)
            
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
                hp_pri_p = battle.get('vida_torres_princesa_jogador', '0')
                hp_pri_o = battle.get('vida_torres_princesa_oponente', '0')
                
                # Troféus e Posição
                t_ini = battle.get('trofes_iniciais_jogador', '0')
                t_fin = battle.get('trofes_finais_jogador', '0')
                rank_p = battle.get('posicao_global_jogador', 'N/A')
                rank_o = battle.get('posicao_global_oponente', 'N/A')
                
                # Nível do Oponente (Torre)
                opp_tower_lv = battle.get('nivel_torre_oponente', '0')
                opp_display = f"{battle['opponent_name']} <small>(Nv {opp_tower_lv})</small>"
                
                battles_table_html += f"""
                    <tr class="battle-{result_class}">
                        <td>{self.format_time_ago(battle['battle_time'])}</td>
                        <td><span class="result-{result_class}">{result_display}</span></td>
                        <td>{opp_display}</td>
                        <td>{battle['crowns']}</td>
                        <td style="color: {trophy_color}">
                            <strong>{int(battle['trophy_change']):+d}</strong><br>
                            <small style="color: #94a3b8">{t_ini} → {t_fin}</small>
                        </td>
                        <td class="tech-metric">💧 {elixir_p} | {elixir_o}</td>
                        <td class="tech-metric">
                            🏰 {hp_p} | {hp_o}<br>
                            <small>👸 {hp_pri_p} | {hp_pri_o}</small>
                        </td>
                        <td style="display: none;">
                            👤 #{rank_p}<br>
                            <small>🎯 #{rank_o}</small>
                        </td>
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
            
            # Próximos Baús (Fase 1)
            chests_html = self.generate_chests_html()
            
            return self.generate_full_html(stats, win_rate, deck_performance_html, 
                                         daily_histogram_html, clan_member_activity_html,
                                         battles_table_html, battles_cards_html, lethal_decks_html, war_decks_html,
                                         chests_html, war_intel_html)
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
            --glass-bg: #0f172a;
            --glass-border: #1e293b;
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
            background: #1e293b;
            border-radius: 16px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid #334155;
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
            background: rgba(15, 23, 42, 0.95);
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

        .cr-grid-4x2, .cr-grid-4x2-premium {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            padding: 15px;
            background: rgba(0,0,0,0.4);
            border-radius: 20px;
            width: 100%;
            max-width: 500px;
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

        .cr-copy-deck-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: linear-gradient(135deg, rgba(66, 153, 225, 0.2) 0%, rgba(49, 130, 206, 0.4) 100%);
            border: 1px solid rgba(66, 153, 225, 0.4);
            color: #fff;
            padding: 8px 20px;
            border-radius: 20px;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 0.85em;
            text-decoration: none;
            text-transform: uppercase;
            letter-spacing: 1px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }

        .cr-copy-deck-btn:hover {
            background: linear-gradient(135deg, rgba(66, 153, 225, 0.4) 0%, rgba(49, 130, 206, 0.6) 100%);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(66, 153, 225, 0.4);
            border-color: rgba(66, 153, 225, 0.8);
        }

        .cr-copy-deck-btn:active {
            transform: translateY(1px);
            box-shadow: 0 2px 10px rgba(66, 153, 225, 0.2);
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
            background: #0f172a;
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
            background: #050914;
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
            margin-top: 12px;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(0,0,0,0.5);
        }

        /* Rodape de metricas premium (Task 2) */
        .cr-deck-footer {
            display: flex;
            justify-content: space-around;
            align-items: center;
            margin-top: 14px;
            padding: 10px 8px;
            background: linear-gradient(135deg, rgba(15,23,42,0.8), rgba(30,41,59,0.7));
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 14px;
            backdrop-filter: blur(6px);
            gap: 4px;
        }

        .cr-footer-metric {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            min-width: 44px;
            padding: 4px 6px;
            border-radius: 10px;
            transition: background 0.2s;
        }

        .cr-footer-metric:hover {
            background: rgba(255,255,255,0.06);
        }

        .cr-footer-icon {
            font-size: 0.95em;
            line-height: 1;
        }

        .cr-footer-val {
            font-size: 0.85em;
            font-weight: 800;
            color: #f1f5f9;
            line-height: 1.2;
        }

        .cr-footer-label {
            font-size: 0.55em;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
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

        .rival-badge {
            font-size: 0.65em;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-left: 10px;
        }
        .fregues-badge { background: rgba(72, 187, 120, 0.2); color: #48bb78; border: 1px solid rgba(72, 187, 120, 0.3); }
        .vantagem-badge { background: rgba(66, 153, 225, 0.2); color: #4299e1; border: 1px solid rgba(66, 153, 225, 0.3); }
        .equilibrado-badge { background: rgba(113, 128, 150, 0.2); color: #718096; border: 1px solid rgba(113, 128, 150, 0.3); }
        .dificil-badge { background: rgba(237, 137, 54, 0.2); color: #ed8936; border: 1px solid rgba(237, 137, 54, 0.3); }
        .carrasco-badge { background: rgba(245, 101, 101, 0.2); color: #f56565; border: 1px solid rgba(245, 101, 101, 0.3); box-shadow: 0 0 15px rgba(245, 101, 101, 0.2); }

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

        /* ===== BADGE DE NIVEL NAS CARTAS (estilo RoyaleAPI) ===== */
        .cr-card-wrap-premium {
            position: relative;
            display: inline-block;
        }
        .cr-card-level-badge {
            position: absolute;
            bottom: 2px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.75);
            color: #fff;
            font-size: 0.52em;
            font-weight: 700;
            padding: 1px 4px;
            border-radius: 3px;
            white-space: nowrap;
            pointer-events: none;
            line-height: 1.3;
            letter-spacing: 0.3px;
            border: 1px solid rgba(255,255,255,0.15);
        }

        /* ===== NOME DO CLA DO OPONENTE ===== */
        .cr-player-clan {
            font-size: 0.72em;
            color: #94a3b8;
            margin-top: -2px;
            margin-bottom: 2px;
            font-style: italic;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 140px;
        }

        @media (max-width: 1024px) {
            .cr-decks-list { grid-template-columns: 1fr; }
            /* Preview VS empilha verticalmente em tablets */
            .cr-vs-row-premium {
                flex-direction: column !important;
                gap: 16px !important;
            }
            .cr-vs-divider-vertical {
                transform: rotate(0deg);
                padding: 4px 0;
            }
        }

        @media (max-width: 768px) {
            /* Grid de cartas adaptado para mobile - manter 4 colunas mas cards menores */
            .cr-grid-4x2-premium {
                grid-template-columns: repeat(4, 1fr) !important;
                gap: 3px !important;
            }
            .cr-card-img {
                width: 100% !important;
                max-width: 48px !important;
            }
            /* Badge de nivel menor em mobile */
            .cr-card-level-badge {
                font-size: 0.44em;
                padding: 1px 2px;
            }
            /* Rodape de metricas em linha unica com scroll se necessario */
            .cr-deck-footer {
                gap: 2px;
                padding: 8px 4px;
                overflow-x: auto;
                flex-wrap: nowrap;
            }
            .cr-footer-metric { min-width: 36px; }
            .cr-footer-label { display: none; } /* esconde label em telas muito pequenas */
            /* Deck body empilhado */
            .cr-deck-body {
                flex-direction: column !important;
            }
            /* VS layout: empilha jogador/oponente em mobile */
            .cr-vs-row-premium {
                flex-direction: column !important;
                gap: 10px !important;
            }
            .cr-vs-divider-vertical {
                transform: rotate(0deg);
                padding: 2px 20px;
                border-top: 1px solid rgba(255,255,255,0.1);
                border-left: none !important;
            }
            /* Player header fica compacto */
            .cr-player-name-premium { font-size: 0.95em; }
            .cr-tower-info-premium  { font-size: 0.7em; }
            .cr-player-clan         { display: none; }
        }

        @media (max-width: 640px) {
            .header h1 { font-size: 2.2em; }
            .section { padding: 24px; }
            .container { padding: 10px; }
            .desktop-table { display: none; }
            .cr-deck-layout { flex-direction: column; }
            /* Player name menor em mobile */
            .cr-player-name-premium { font-size: 1em; }
        }

        /* Modal Glassmorphism */
        .cr-modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: #050914;
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .cr-modal-overlay.active {
            display: flex;
            opacity: 1;
        }

        .cr-modal-container {
            width: 95%;
            max-width: 1200px;
            background: #0f172a; /* Fundo sólido para legibilidade máxima */
            border: 2px solid rgba(255, 255, 255, 0.15);
            border-radius: 32px;
            box-shadow: 0 0 100px rgba(0, 0, 0, 0.8), 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            padding: 40px;
            position: relative;
            transform: scale(0.9);
            transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            overflow-y: auto;
            max-height: 90vh;
        }

        .cr-modal-overlay.active .cr-modal-container {
            transform: scale(1);
        }

        .cr-modal-close {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: #fff;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            z-index: 10;
        }

        .cr-modal-close:hover {
            background: var(--danger);
            transform: rotate(90deg);
        }

        #battle-modal-content {
            width: 100%;
        }

        /* Ajuste para o VS no Modal */
        .cr-modal-container .cr-vs-row-premium-v2 {
            background: transparent;
            padding: 0;
        }
        """
    
    def generate_full_html(self, stats, win_rate, deck_performance_html, 
                          daily_histogram_html, clan_member_activity_html="",
                          battles_table_html="", battles_cards_html="",
                          lethal_decks_html="", war_decks_html="",
                          chests_html="", war_intel_html="") -> str:
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
    <!-- Global Battle Modal Overlay -->
    <div id="cr-battle-modal" class="cr-modal-overlay">
        <div class="cr-modal-container">
            <button class="cr-modal-close" onclick="closeBattleModal()">×</button>
            <div id="battle-modal-content">
                <!-- Content injected dynamically by JS -->
                <div style="text-align: center; padding: 40px; color: #94a3b8;">
                    <p>Carregando visualização de batalha...</p>
                </div>
            </div>
        </div>
    </div>

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
                    <h3>Taxa de Vitória</h3>
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

        {chests_html}

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

        {war_intel_html}

        <div class="section">
            <h2>⚔️ Últimas Batalhas</h2>
            <div class="desktop-table">
                <table>
                    <thead><tr><th>Horário</th><th>Resultado</th><th>Oponente</th><th>Coroas</th><th>Troféus Δ</th><th>💧 Elixir</th><th>🏰 HP Torre</th><th style="display: none;">👤 Rank</th><th>Arena</th></tr></thead>
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
    
    # Save as index.html for GitHub Pages in root directory
    index_path = os.path.join(root_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"GitHub Pages HTML report generated: {index_path}")

if __name__ == "__main__":
    main()
