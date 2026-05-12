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
from dotenv import load_dotenv
from csv_database_manager import CSVManager

# Carrega variaveis de ambiente
load_dotenv()

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
        return master

    def _load_all_battles_from_csv(self, player_tag: str = None) -> List[Dict]:
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
                        'nivel_torre_oponente': row.get('nivel_torre_oponente') or '0',
                        'torre_jogador': row.get('torre_jogador') or '',
                        'torre_oponente': row.get('torre_oponente') or ''
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
        """Gera uma representação do deck preservando a ordem original (fingerprint)."""
        if not deck_str or deck_str == 'N/D':
            return 'N/D'
        cards = [c.strip() for c in deck_str.replace(' | ', '|').split('|')]
        return " | ".join(cards)

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

    def get_tower_image_path(self, tower_name: str) -> str:
        """Retorna o caminho local da imagem da torre"""
        if not tower_name or tower_name == 'N/D':
            return "./docs/princesa-tropa-de-torre-clash-royale.png"
        
        # Mapeamento para arquivos locais na pasta docs
        tower_mapping = {
            'Tower Princess': 'princesa-tropa-de-torre-clash-royale',
            'Cannoneer': 'canhoneiro-clash-royale-render-3d-cannonier',
            'Dagger Duchess': 'tudo-sobre-duquesa-das-adagas-clash-royale-knives-thrower',
            'Royal Chef': 'tudo-sobre-cozinheiro-real-clash-royale-royal-chef-FylAY7',
            'King Tower': 'princesa-tropa-de-torre-clash-royale'
        }
        
        slug = tower_mapping.get(tower_name)
        if not slug:
            # Tenta busca parcial caso o nome venha diferente da API
            if 'Dagger' in tower_name: slug = 'tudo-sobre-duquesa-das-adagas-clash-royale-knives-thrower'
            elif 'Cannon' in tower_name: slug = 'canhoneiro-clash-royale-render-3d-cannonier'
            elif 'Princess' in tower_name: slug = 'princesa-tropa-de-torre-clash-royale'
            elif 'Chef' in tower_name: slug = 'tudo-sobre-cozinheiro-real-clash-royale-royal-chef-FylAY7'
            else: slug = 'princesa-tropa-de-torre-clash-royale'
            
        return f"./docs/{slug}.png"

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
            leaked_raw = battle.get('elixir_vazado_oponente') or battle.get('opp_leaked') or battle.get('elixir_leaked_opponent') or battle.get('opponent_leaked', 0)
            level_raw = battle.get('nivel_torre_oponente') or battle.get('nivel_oponente') or battle.get('opponent_level') or battle.get('opp_tower_level', 14)
        else:
            leaked_raw = battle.get('elixir_vazado_jogador') or battle.get('player_leaked') or battle.get('elixir_leaked_player') or battle.get('player_leaked_elixir', 0)
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
        metrics['tower_name'] = battle.get('torre_oponente' if is_opponent else 'torre_jogador') or 'Tower Princess'
        metrics['tower_url'] = self.get_tower_image_path(metrics['tower_name'])
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
                    deck_cards = ' | '.join([card['name'] for card in player_team.get('cards', [])])
                    
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
                            ' | '.join([card['name'] for card in opponent_team.get('cards', [])]) if opponent_team else None,
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
                    <span class="legend-color legend-draws"></span>
                    <span>Draws</span>
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
                <button class="tab-button active" onclick="switchTab(event, 'repeated-opponents')">Oponentes Repetidos</button>
                <button class="tab-button" onclick="switchTab(event, 'weekly-decks')">Meus Decks da Semana</button>
                <button class="tab-button" onclick="switchTab(event, 'lethal-decks')">Decks Inimigos Letais</button>
                <button class="tab-button" onclick="switchTab(event, 'winning-decks')">Melhores Decks (Semana)</button>
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
        """Gera HTML da aba 'Meus Decks' com timeline interativa e layout Premium v2."""
        if not weekly_data: return '<div class="cr-empty-state">Nenhum dado encontrado para os últimos 7 dias.</div>'
        import json, urllib.parse
        
        player_name = self.player_name_override or next((p.get('name', 'Jogador') for p in self.players_cache if p.get('player_tag') == self.player_tag), 'Jogador')
        player_clan = next((p.get('clan_name', '') for p in self.players_cache if p.get('player_tag') == self.player_tag), '')

        html = '<div class="cr-decks-list">'
        for i, deck in enumerate(weekly_data, 1):
            total = deck['total']
            win_rate = deck['win_rate']
            wins_pct = round((deck['wins']/total*100), 1) if total > 0 else 0
            losses_pct = round((deck['losses']/total*100), 1) if total > 0 else 0
            draws_pct = round(max(0, 100 - wins_pct - losses_pct), 1)
            deck_id = f"weekly-{i}"
            
            # Primeira batalha para o preview inicial
            first_b = deck['battles'][0] if deck['battles'] else {}
            my_m_f = self._get_battle_deck_metrics(first_b['my_deck'], first_b, is_opponent=False)
            opp_m_f = self._get_battle_deck_metrics(first_b['opp_deck'], first_b, is_opponent=True)
            
            # Timeline HTML
            timeline_h = ""
            for idx, b in enumerate(deck['battles'][:15]):
                my_m = self._get_battle_deck_metrics(b['my_deck'], b, is_opponent=False)
                opp_m = self._get_battle_deck_metrics(b['opp_deck'], b, is_opponent=True)
                
                # Dados para o JS
                b_data = {
                    "crowns": b.get('coroas_jogador', 0),
                    "o_crowns": b.get('coroas_oponente', 0),
                    "mode": b.get('modo_jogo', 'Batalha'),
                    "date": b['dt_obj'].strftime('%d/%m'),
                    "time": b['dt_obj'].strftime('%H:%M'),
                    "p_metrics": self._generate_metrics_panel_html_simple(my_m),
                    "o_metrics": self._generate_metrics_panel_html_simple(opp_m),
                    "p_grid": self._generate_deck_grid_html_simple(b['my_deck']),
                    "o_grid": self._generate_deck_grid_html_simple(b['opp_deck']),
                    "p_tower_url": my_m['tower_url'],
                    "o_tower_url": opp_m['tower_url'],
                    "p_level": my_m['level'],
                    "o_level": opp_m['level'],
                    "p_hp": my_m.get('hp', '--'),
                    "o_hp": opp_m.get('hp', '--'),
                    "p_name": player_name,
                    "o_name": b.get('nome_oponente', 'Oponente'),
                    "p_clan": player_clan,
                    "o_clan": b.get('opp_clan', 'Sem Clã'),
                    "p_tag": self.player_tag,
                    "o_tag": b.get('tag_oponente', '000000'),
                    "p_deck_list": [c.strip() for c in b['my_deck'].replace(' | ', '|').split('|') if c.strip()],
                    "o_deck_list": [c.strip() for c in b['opp_deck'].replace(' | ', '|').split('|') if c.strip()]
                }
                
                data_attr = json.dumps(b_data).replace('"', '&quot;')
                res = b['resultado'].lower()
                res_char = 'V' if any(x in res for x in ['vitoria', 'victory', 'vitória']) else ('D' if any(x in res for x in ['derrota', 'defeat']) else 'E')
                res_color = '#48bb78' if res_char == 'V' else ('#f56565' if res_char == 'D' else '#718096')
                active_class = "active" if idx == 0 else ""
                
                timeline_h += f'''
                <div class="cr-history-dot {active_class}" 
                     style="border-bottom: 2px solid {res_color};"
                     data-battle="{data_attr}"
                     onclick="updateOpponentView('{deck_id}', this)"
                     title="{b["data"]} - {res_char}">
                    <span class="dot-res" style="color: {res_color}">{res_char}</span>
                    <span class="dot-time">{b['dt_obj'].strftime('%H:%M')}</span>
                </div>'''

            wr_c = '#48bb78' if win_rate >= 60 else ('#f56565' if win_rate <= 40 else '#718096')
            
            html += f'''
            <div class="cr-deck-card cr-glass-premium" style="margin-bottom: 15px; overflow: visible;">
                <div class="cr-deck-header" style="padding: 8px 15px; background: rgba(255,255,255,0.02); border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div class="cr-deck-meta" style="display: flex; align-items: center; gap: 10px; width: 100%;">
                        <span class="cr-deck-rank" style="background:#4299e1; color: #fff; padding: 2px 8px; border-radius: 5px; font-weight: 900; font-size: 0.75em;">#{i}</span>
                        <span style="color: #fff; font-size: 0.85em; font-weight: 900;">WR: {win_rate}% <span style="opacity: 0.5; font-size: 0.8em; font-weight: 400;">({deck['recent_total']} partidas na semana)</span></span>
                        <span class="cr-wr-badge" style="margin-left: auto; background:{wr_c}; font-weight: 900; font-size: 0.7em; padding: 2px 6px;">{total} TOTAL</span>
                    </div>
                </div>
                
                <div class="cr-progress-bar" style="height: 4px; background: rgba(0,0,0,0.3); display: flex;">
                    <div class="cr-bar-wins" style="width:{wins_pct}%; background: #48bb78;"></div>
                    <div class="cr-bar-draws" style="width:{draws_pct}%; background: #718096;"></div>
                    <div class="cr-bar-losses" style="width:{losses_pct}%; background: #f56565;"></div>
                </div>

                <div class="cr-deck-body" style="padding: 10px 15px; background: transparent; overflow: visible;">
                    <div class="cr-main-vs-stage" style="padding: 0; min-height: 0;">
                        <!-- Amostragem da Batalha Premium v2 -->
                        <div class="cr-battle-preview-v2" style="display: grid; grid-template-columns: 1.8fr 0.4fr 1.8fr; align-items: center; gap: 10px; padding: 10px 0 15px 0; border-bottom: 1px solid rgba(255,255,255,0.03); margin-bottom: 15px; position: relative; z-index: 2;">
                            <div style="text-align: left; overflow: hidden;">
                                <div style="font-size: 0.55em; color: rgba(255,255,255,0.25); font-weight: 800;">#{self.player_tag}</div>
                                <div id="p-name-{deck_id}" style="font-family: 'Krona One', sans-serif; font-size: 0.95em; color: #fff; font-weight: 950; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{player_name}</div>
                                <div id="p-clan-{deck_id}" style="font-size: 0.55em; color: rgba(255,255,255,0.3); font-weight: 800;">{player_clan or 'Sem Clã'}</div>
                            </div>
                            <div style="text-align: center;">
                                <div id="score-{deck_id}" style="font-size: 2.2em; font-weight: 950; color: #fff; letter-spacing: -2px;">{first_b.get('coroas_jogador', 0)} - {first_b.get('coroas_oponente', 0)}</div>
                                <div id="mode-{deck_id}" style="font-size: 0.45em; font-weight: 900; color: rgba(255,255,255,0.4); text-transform: uppercase;">{first_b.get('modo_jogo', 'Batalha')}</div>
                            </div>
                            <div style="text-align: right; overflow: hidden;">
                                <div id="o-tag-{deck_id}" style="font-size: 0.55em; color: rgba(255,255,255,0.25); font-weight: 800;">#{first_b.get('tag_oponente', '000000')}</div>
                                <div id="o-name-{deck_id}" style="font-size: 1.1em; font-weight: 950; color: #f87171; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{first_b.get('nome_oponente', 'Oponente')}</div>
                                <div id="o-clan-{deck_id}" style="font-size: 0.55em; color: rgba(255,255,255,0.3); font-weight: 800;">{first_b.get('opp_clan', 'Sem Clã')}</div>
                            </div>
                        </div>

                        <!-- Decks e Torres -->
                        <div class="cr-vs-decks-grid-v2" style="gap: 10px; margin-top: 15px;">
                            <div class="cr-side-container" style="position: relative; flex: 1; min-height: 120px; background: transparent; padding: 0;">
                                <div id="p-tower-container-{deck_id}" style="position: absolute; top: -50px; left: 50%; transform: translateX(-50%); width: 85px; height: 85px; z-index: 1;">
                                    <img id="p-tower-img-{deck_id}" src="{my_m_f['tower_url']}" class="cr-tower-img-large" style="width: 100%; height: 100%; filter: drop-shadow(0 0 15px rgba(74, 222, 128, 0.4));">
                                    <span id="p-tower-lv-{deck_id}" class="cr-tower-lv-badge" style="{ 'display: none;' if my_m_f['level'] == 'N/A' else '' }">LV {my_m_f['level']}</span>
                                    <div style="margin-top: -8px; display: flex; flex-direction: column; align-items: center;">
                                        <div class="cr-hp-bar-mini" style="width: 45px;"><div id="p-tower-bar-{deck_id}" style="width: 100%; height: 100%; background: #4ade80;"></div></div>
                                        <span id="p-tower-hp-{deck_id}" style="font-size: 7px; color: #4ade80; font-weight: 900; line-height: 1; margin-top: 2px;">{my_m_f.get('hp', '--')} HP</span>
                                    </div>
                                </div>
                                <div id="p-grid-{deck_id}" style="margin-top: 55px;">{self._generate_deck_grid_html_simple(first_b.get('my_deck', deck['deck_cards']))}</div>
                            </div>

                            <div class="cr-side-container" style="position: relative; flex: 1; min-height: 120px; background: transparent; padding: 0;">
                                <div id="o-tower-container-{deck_id}" style="position: absolute; top: -50px; left: 50%; transform: translateX(-50%); width: 85px; height: 85px; z-index: 1;">
                                    <img id="o-tower-img-{deck_id}" src="{opp_m_f['tower_url']}" class="cr-tower-img-large cr-mirror-opponent" style="width: 100%; height: 100%; filter: drop-shadow(0 0 15px rgba(248, 113, 113, 0.4));">
                                    <span id="o-tower-lv-{deck_id}" class="cr-tower-lv-badge" style="{ 'display: none;' if opp_m_f['level'] == 'N/A' else '' }">LV {opp_m_f['level']}</span>
                                    <div style="margin-top: -8px; display: flex; flex-direction: column; align-items: center;">
                                        <div class="cr-hp-bar-mini" style="width: 45px;"><div id="o-tower-bar-{deck_id}" style="width: 100%; height: 100%; background: #f87171;"></div></div>
                                        <span id="o-tower-hp-{deck_id}" style="font-size: 7px; color: #f87171; font-weight: 900; line-height: 1; margin-top: 2px;">{opp_m_f.get('hp', '--')} HP</span>
                                    </div>
                                </div>
                                <div id="o-grid-{deck_id}" style="margin-top: 55px;">{self._generate_deck_grid_html_simple(first_b.get('opp_deck', ''))}</div>
                            </div>

                        </div>

                        <!-- Footer Metrics -->
                        <div class="cr-vs-footer-v2" style="margin-top: 15px; padding: 10px; background: rgba(15, 23, 42, 0.4); border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                            <div style="display: grid; grid-template-columns: 1fr 1px 1fr; gap: 10px; align-items: center;">
                                <div id="player-metrics-{deck_id}" style="display: flex; gap: 8px; justify-content: center;">
                                    {self._generate_metrics_panel_html_simple(my_m_f)}
                                </div>
                                <div style="width: 1px; background: rgba(255,255,255,0.1); height: 15px;"></div>
                                <div id="opp-metrics-{deck_id}" style="display: flex; gap: 8px; justify-content: center;">
                                    {self._generate_metrics_panel_html_simple(opp_m_f)}
                                </div>
                            </div>
                            <!-- Botoes de Copia -->
                            <div style="margin-top: 10px; display: flex; justify-content: center; gap: 10px;">
                                <button id="p-copy-{deck_id}" onclick="copyToClipboardDeckDirect({[c.strip() for c in first_b.get('my_deck', deck['deck_cards']).replace(' | ','|').split('|') if c.strip()]})" 
                                        style="background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); color: #93c5fd; padding: 4px 10px; border-radius: 6px; font-size: 0.6em; font-weight: 900; cursor: pointer;">
                                    <i class="far fa-copy"></i> MEU DECK
                                </button>
                                <button id="o-copy-{deck_id}" onclick="copyToClipboardDeckDirect({[c.strip() for c in first_b.get('opp_deck', '').replace(' | ','|').split('|') if c.strip()]})" 
                                        style="background: rgba(248, 113, 113, 0.15); border: 1px solid rgba(248, 113, 113, 0.3); color: #fca5a5; padding: 4px 10px; border-radius: 6px; font-size: 0.6em; font-weight: 900; cursor: pointer;">
                                    <i class="far fa-copy"></i> OPONENTE
                                </button>
                            </div>
                        </div>
                        
                        <!-- Timeline -->
                        <div style="margin-top: 10px; padding: 8px 12px; background: rgba(0,0,0,0.2); border-radius: 12px; border: 1px solid rgba(255,255,255,0.03);">
                            <div style="display: flex; gap: 6px; overflow-x: auto; padding-bottom: 4px;">
                                {timeline_h}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''
        return html + "</div>"

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
                    <div class="cr-deck-meta" style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                        <span class="cr-deck-rank" style="background:{wr_c};">#{i} {source_label.upper()}</span>
                        <div class="cr-mode-badge" style="background:{wr_c}; position: static; margin: 0;">{game_mode}</div>
                        <span class="cr-deck-label">Taxa de Vitoria: {win_rate}%</span>
                    </div>
                    <span class="cr-wr-badge" style="background:#edf2f7; color:#4a5568; border:1px solid #e2e8f0;">{total} Partidas</span>
                </div>
                <div class="cr-deck-body">
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
                'player_leaked': b.get('elixir_vazado_jogador') or b.get('player_leaked', 0),
                'opp_leaked': b.get('elixir_vazado_oponente') or b.get('opp_leaked', 0),
                'torre_jogador': b.get('torre_jogador') or b.get('player_tower_name', 'Tower Princess'),
                'torre_oponente': b.get('torre_oponente') or b.get('opp_tower_name', 'Tower Princess'),
                'player_tower_level': b.get('nivel_torre_jogador') or b.get('player_tower_level', 14),
                'opp_tower_level': b.get('nivel_torre_oponente') or b.get('opp_tower_level', 14),
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

        function getMiniGridJS(deckStr, sideClass, playerName, clanName, metrics, deckLink, icons) {
            if (!deckStr) return { playerName, cardsHtml: `<div class="${sideClass} cr-empty-grid">N/D</div>`, metricsHtml: '' };
            let cards = deckStr.replace(/ \\| /g, '|').split('|').filter(Boolean).slice(0, 8);
            
            let towerUrl = "https://cdn.royaleapi.com/static/img/cards-75/tower-princess.png";
            let towerName = "Tower Princess";
            
            if (icons && icons.tower_url) {
                towerUrl = icons.tower_url;
                towerName = icons.tower_name || "Tower Skin";
            } else if (metrics && metrics.tower_url) {
                towerUrl = metrics.tower_url;
                towerName = metrics.tower_name || "Tower Skin";
            }
            
            const cardsHtml = cards.map(c => {
                const name = c.trim();
                const isEvo = name.includes('(Evolution)') || name.includes('Evolved');
                const displayName = name.replace('(Evolution)', '').replace('Evolved', '').trim();
                const cleanName = displayName.toLowerCase().replace(/\\s+/g, '-').replace(/\\./g, '').replace(/[()]/g, '');
                
                let url = CARD_MAP[name] || CARD_MAP[displayName] || CARD_MAP[cleanName];
                
                if (!url) {
                    const slug = cleanName.replace('the-log', 'log').replace('p-e-k-k-a', 'pekka');
                    url = `https://royaleapi.github.io/cr-api-assets/cards/${slug}.png`;
                }

                const evoClass = isEvo ? 'cr-card-evo-border' : '';
                return `
                    <div class="cr-card-wrap-premium ${evoClass}" title="${name}">
                        <img src="${url}" class="cr-card-img" onerror="this.src='https://royaleapi.com/static/img/cards-150/${cleanName}.png'" loading="lazy">
                        ${isEvo ? '<div class="cr-evo-icon"></div>' : ''}
                    </div>`;
            }).join('');
            
            const avg = metrics ? metrics.avg : '--';
            const cycle = metrics ? metrics.cycle : '--';
            const leaked = metrics ? (metrics.leaked || 0) : 0;
            const tLevel = metrics ? (metrics.level || 14) : 14;
            let tHP = metrics ? (metrics.hp || '--') : '--';
            if (tHP !== '--' && !isNaN(tHP)) {
                tHP = Number(tHP).toLocaleString('pt-BR');
            }

            const isLeak = leaked > 0;
            const leakClass = isLeak ? 'cr-leak-active' : '';
            
            const copyHtml = deckLink ? `<a href="${deckLink}" class="cr-copy-deck-btn" title="Copiar Deck">📋</a>` : '';
            
            return {
                playerName,
                towerUrl,
                towerName,
                tLevel,
                tHP,
                cardsHtml: `
                    <div class="cr-grid-wrapper-premium">
                        <div class="cr-grid-4x2">
                            ${cardsHtml}
                        </div>
                        ${copyHtml}
                    </div>`,
                metricsHtml: `
                    <div class="cr-metric-inline" title="HP Torre">
                        <span class="cr-icon">🏰</span> <span>${tHP}</span>
                    </div>`
            };
        }

        function updateBattlePreview(deckId, battleIdx, battleDataJson) {
            // Modal removido conforme solicitação para economizar espaço
            // A atualização agora é feita inline via updateOpponentView onde aplicável
            console.log("updateBattlePreview called, but modal is disabled");
        }

        function closeBattleModal() {
            const modal = document.getElementById('cr-battle-modal');
            if (modal) modal.classList.remove('active');
            document.body.style.overflow = '';
        }

        function updateOpponentView(oppId, element) {
            try {
                const dataRaw = element.getAttribute('data-battle');
                const data = JSON.parse(dataRaw);
                console.log(`[RoyaleAnalytics] Updating Opponent ${oppId}`, data);
                
                // Update scores and mode
                const scoreEl = document.getElementById(`score-${oppId}`);
                const modeEl = document.getElementById(`mode-${oppId}`);
                if (scoreEl) scoreEl.innerText = `${data.crowns || 0} - ${data.o_crowns || 0}`;
                if (modeEl) modeEl.innerText = data.mode || 'Batalha';
                
                // Update metrics
                const pMetricsEl = document.getElementById(`player-metrics-${oppId}`);
                const oMetricsEl = document.getElementById(`opp-metrics-${oppId}`);
                if (pMetricsEl) pMetricsEl.innerHTML = data.p_metrics;
                if (oMetricsEl) oMetricsEl.innerHTML = data.o_metrics;

                // Update towers and levels
                const pTowerImg = document.getElementById(`p-tower-img-${oppId}`);
                const oTowerImg = document.getElementById(`o-tower-img-${oppId}`);
                const pTowerLv = document.getElementById(`p-tower-lv-${oppId}`);
                const oTowerLv = document.getElementById(`o-tower-lv-${oppId}`);
                const pHpEl = document.getElementById(`p-tower-hp-${oppId}`);
                const oHpEl = document.getElementById(`o-tower-hp-${oppId}`);
                
                if (pTowerImg) {
                    pTowerImg.src = data.p_tower_url || pTowerImg.src;
                    pTowerImg.style.opacity = '0.5';
                    setTimeout(() => pTowerImg.style.opacity = '1', 50);
                }
                if (oTowerImg) {
                    oTowerImg.src = data.o_tower_url || oTowerImg.src;
                    oTowerImg.style.opacity = '0.5';
                    setTimeout(() => oTowerImg.style.opacity = '1', 50);
                }
                
                if (pTowerLv) {
                    if (data.p_level && data.p_level !== 'N/A') {
                        pTowerLv.innerText = `LV ${data.p_level}`;
                        pTowerLv.style.display = 'block';
                    } else {
                        pTowerLv.style.display = 'none';
                    }
                }
                if (oTowerLv) {
                    if (data.o_level && data.o_level !== 'N/A') {
                        oTowerLv.innerText = `LV ${data.o_level}`;
                        oTowerLv.style.display = 'block';
                    } else {
                        oTowerLv.style.display = 'none';
                    }
                }
                
                if (pHpEl) pHpEl.innerText = `${data.p_hp || '--'} HP`;
                if (oHpEl) oHpEl.innerText = `${data.o_hp || '--'} HP`;

                
                // Update grids
                const pGridEl = document.getElementById(`p-grid-${oppId}`);
                const oGridEl = document.getElementById(`o-grid-${oppId}`);
                if (pGridEl) pGridEl.innerHTML = data.p_grid;
                if (oGridEl) oGridEl.innerHTML = data.o_grid;
                
                // Update copy links
                const pCopyEl = document.getElementById(`p-copy-${oppId}`);
                const oCopyEl = document.getElementById(`o-copy-${oppId}`);
                if (pCopyEl) pCopyEl.onclick = () => copyToClipboardDeckDirect(data.p_deck_list);
                if (oCopyEl) oCopyEl.onclick = () => copyToClipboardDeckDirect(data.o_deck_list);
                
                // Update date and time
                const dateEl = document.getElementById(`date-${oppId}`);
                const timeEl = document.getElementById(`time-${oppId}`);
                if (dateEl) dateEl.innerHTML = `<i class="far fa-calendar-alt"></i> ${data.date || '--/--'}`;
                if (timeEl) timeEl.innerHTML = `<i class="far fa-clock"></i> ${data.time || '--:--'}`;
                
                // Update active dot
                const container = element.closest('.cr-history-dots-row-inline') || element.parentElement;
                if (container) {
                    container.querySelectorAll('.cr-history-dot').forEach(el => el.classList.remove('active'));
                }
                element.classList.add('active');
            } catch(e) { console.error("[RoyaleAnalytics] Error updating view:", e); }
        }


        function showCopyToast(e) {
            const toast = document.createElement('div');
            toast.textContent = 'Aguardando abertura no jogo...';
            toast.className = 'cr-toast-premium';
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 500);
            }, 3000);
        }

        function switchTab(event, tabName) {
            const container = event.currentTarget.closest('.section, .elite-spy-section, .deck-tabs-container') || document;
            container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            container.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
            
            const targetId = tabName.startsWith('tab-') ? tabName : 'tab-' + tabName;
            const targetTab = document.getElementById(targetId) || document.getElementById(tabName);
            
            if (targetTab) targetTab.classList.add('active');
            if (event) event.currentTarget.classList.add('active');
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeBattleModal();
        });

        document.addEventListener('click', (e) => {
            const modal = document.getElementById('cr-battle-modal');
            if (e.target === modal) closeBattleModal();
        });

        document.addEventListener('DOMContentLoaded', () => {
            const bgs = [
                "https://images2.alphacoders.com/112/thumb-1920-1124066.jpg",
                "https://images5.alphacoders.com/129/thumb-1920-1297235.jpg",
                "https://images.alphacoders.com/859/thumb-1920-859000.jpg",
                "https://images5.alphacoders.com/128/thumb-1920-1284525.jpg",
                "https://images2.alphacoders.com/127/thumb-1920-1270367.jpg",
                "https://images.alphacoders.com/128/thumb-1920-1284523.jpg",
                "https://images8.alphacoders.com/130/thumb-1920-1305740.jpg",
                "https://images3.alphacoders.com/859/thumb-1920-859892.jpg"
            ];
            
            let bgIndex = Math.floor(Math.random() * bgs.length);
            
            function updateBackground() {
                const selectedBg = bgs[bgIndex];
                document.body.style.backgroundImage = `linear-gradient(rgba(10, 15, 26, 0.5), rgba(10, 15, 26, 0.5)), url('${selectedBg}')`;
                document.body.style.backgroundSize = 'cover';
                document.body.style.backgroundPosition = 'center';
                document.body.style.backgroundAttachment = 'fixed';
                
                const footer = document.querySelector('.footer');
                if (footer) {
                    let bgInfo = document.getElementById('cr-bg-info');
                    if (!bgInfo) {
                        bgInfo = document.createElement('p');
                        bgInfo.id = 'cr-bg-info';
                        bgInfo.className = 'cr-bg-info-style';
                        footer.appendChild(bgInfo);
                    }
                    bgInfo.innerHTML = `Wallpaper: <a href="${selectedBg}" target="_blank">${selectedBg.split('/').pop()}</a>`;
                }
                bgIndex = (bgIndex + 1) % bgs.length;
            }

            updateBackground();
            setInterval(updateBackground, 30000);

            const mainContainer = document.querySelector('.container');
            if (mainContainer) {
                mainContainer.style.maxWidth = '1350px';
                mainContainer.style.width = '100%';
            }

            // Inserir CSS Dinâmico para correções de layout e alinhamento
            const style = document.createElement('style');
            style.textContent = `
                .cr-vs-stage-v2 { 
                    align-items: flex-start !important; 
                    gap: 10px !important;
                    padding-bottom: 5px !important;
                }
                .cr-deck-card { 
                    min-height: auto !important; 
                    margin-bottom: 10px !important;
                }
                .cr-main-vs-stage { 
                    padding: 10px 20px !important;
                }
                .cr-vs-player-info {
                    padding-top: 5px !important;
                }
                .cr-tower-card-premium {
                    margin-top: 0 !important;
                }
                .cr-history-dot {
                    transition: all 0.2s ease;
                }
                .cr-history-dot:hover {
                    transform: translateY(-2px);
                    filter: brightness(1.2);
                }
                .cr-tower-zoom {
                    transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275), filter 0.3s ease !important;
                    cursor: pointer;
                    transform-origin: center bottom;
                    will-change: transform;
                    backface-visibility: hidden;
                }
                .cr-tower-zoom:hover {
                    transform: scale(1.1) translateY(-5px) !important;
                    filter: brightness(1.15) drop-shadow(0 10px 20px rgba(0,0,0,0.4)) !important;
                }
                .cr-mirror-opponent:hover {
                    transform: scale(-1.1, 1.1) translateY(-5px) !important;
                }
                .cr-opp-card-row {
                    padding-bottom: 5px !important;
                }
            `;
            document.head.appendChild(style);
        });
        </script>
        """

    def _generate_history_dots(self, section_idx, stats_list, p_name, p_clan, o_name, o_clan, o_tag):
        """Gera os badges de navegação histórica para oponentes repetidos com dados inline."""
        import json
        dots_html = ""
        for b_idx, b in enumerate(stats_list):
            data_str = b.get('data_str', '--/-- 00:00')
            parts = data_str.split(' ')
            d = parts[0] if len(parts) > 0 else '--/--'
            t = parts[1] if len(parts) > 1 else '00:00'
            
            res = "W" if b.get('crowns',0) > b.get('opponent_crowns',0) else ("L" if b.get('crowns',0) < b.get('opponent_crowns',0) else "D")
            res_color = "#48bb78" if res == "W" else ("#f56565" if res == "L" else "#718096")
            active_class = "active" if b_idx == 0 else ""
            
            # Preparar dados para atualização inline
            my_m = self._get_battle_deck_metrics(b['my_deck'], b, is_opponent=False)
            opp_m = self._get_battle_deck_metrics(b['opp_deck'], b, is_opponent=True)
            
            battle_data = {
                "crowns": b.get('crowns', 0),
                "o_crowns": b.get('opponent_crowns', 0),
                "mode": b.get('game_mode', 'Batalha'),
                "date": d,
                "time": t,
                "p_metrics": self._generate_metrics_panel_html_simple(my_m),
                "o_metrics": self._generate_metrics_panel_html_simple(opp_m),
                "p_grid": self._generate_deck_grid_html_simple(b['my_deck']),
                "o_grid": self._generate_deck_grid_html_simple(b['opp_deck']),
                "p_tower_url": my_m['tower_url'],
                "o_tower_url": opp_m['tower_url'],
                "p_level": my_m['level'],
                "o_level": opp_m['level'],
                "p_hp": my_m.get('hp', '--'),
                "o_hp": opp_m.get('hp', '--'),
                "p_deck_list": [c.strip() for c in b.get('my_deck','').split('|') if c.strip()],
                "o_deck_list": [c.strip() for c in b.get('opp_deck','').split('|') if c.strip()]
            }
            
            data_attr = json.dumps(battle_data).replace('"', '&quot;')
            
            dots_html += f'''
            <div class="cr-history-dot {active_class}" 
                 style="border-bottom: 2px solid {res_color};"
                 data-battle="{data_attr}"
                 onclick="updateOpponentView({section_idx}, this)"
                 title="{d} {t} - {res}">
                <span class="dot-res" style="color: {res_color}">{res}</span>
                <span class="dot-time">{t}</span>
            </div>'''
        return dots_html

    def _generate_metrics_panel_html_simple(self, metrics):
        leaked = float(metrics.get('leaked', 0))
        leak_class = "cr-leak-warning" if leaked > 0.1 else ""
        t_hp = metrics.get('hp', '--')
        
        # Caminho relativo para garantir funcionamento em diferentes ambientes
        local_leak_icon = "docs/ElixirVazado.png"
        leak_icon = local_leak_icon if leaked > 0.1 else "https://cdn.royaleapi.com/static/img/ui/elixir.png"
        
        return f"""
            <div class="cr-metric-inline" title="Elixir" style="display: flex; align-items: center; gap: 4px;">
                <img src="https://cdn.royaleapi.com/static/img/ui/elixir.png" style="width: 14px; height: 14px;">
                <span style="font-weight: 800; font-size: 0.9em; color: #fff;">{metrics['avg']}</span>
            </div>
            <div class="cr-metric-inline" title="Ciclo" style="display: flex; align-items: center; gap: 4px;">
                <img src="https://cdn.royaleapi.com/static/img/ui/deck-cycle.png" style="width: 14px; height: 14px; filter: brightness(1.2);">
                <span style="font-weight: 800; font-size: 0.9em; color: #fff;">{metrics['cycle']}</span>
            </div>
            <div class="cr-metric-inline {leak_class}" title="Leak" style="display: flex; align-items: center; gap: 4px;">
                <img src="{leak_icon}" style="width: 14px; height: 14px; opacity: {0.5 if leaked <= 0.1 else 1}; filter: { 'drop-shadow(0 0 8px rgba(255,0,0,0.8))' if leaked > 0.1 else 'none' };">
                <span style="font-weight: 800; font-size: 0.9em; color: {metrics.get('leaked_color', '#fff')};">{metrics.get('leaked_label', 'N/A')}</span>
            </div>
            <div class="cr-metric-inline" title="HP Torre" style="display: flex; align-items: center; gap: 4px;">
                <img src="https://cdn.royaleapi.com/static/img/ui/king-tower.png" style="width: 14px; height: 14px;">
                <span style="font-weight: 800; font-size: 0.9em; color: #fff;">{t_hp}</span>
            </div>
        """

    def _generate_deck_grid_html_simple(self, deck_str, copy_link=None):
        if not deck_str or deck_str == 'N/D': return '<div class="cr-empty-grid">N/D</div>'
        cards = [c.strip() for c in deck_str.replace(' | ', '|').split('|') if c.strip()][:8]
        html_cards = "".join(f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(c)}" class="cr-card-img"></div>' for c in cards)
        return f'<div class="cr-grid-4x2">{html_cards}</div>'

    def generate_repeated_opponents_html(self, opponents: List[Dict]) -> str:
        """Gera HTML para oponentes repetidos com match cards inline usando layout Premium v2."""
        if not opponents: return '<div class="cr-empty-state">Nenhum oponente repetido encontrado no histórico recente.</div>'
        
        player_name = self.player_name_override or next((p.get('name', 'Jogador') for p in self.players_cache if p.get('player_tag') == self.player_tag), 'Jogador')
        player_clan = next((p.get('clan_name', '') for p in self.players_cache if p.get('player_tag') == self.player_tag), '')
        
        html = '<div class="cr-opponents-list">'
        
        for i, opp in enumerate(opponents, 1):
            wr = opp['user_win_rate']
            category, cat_class = opp['category'], opp['category_class']
            stats_list = opp['stats']
            wr_c = '#48bb78' if wr >= 60 else ('#f56565' if wr <= 40 else '#718096')
            
            # Primeira batalha (Palco VS inicial)
            first_b = stats_list[0]
            my_metrics_f = self._get_battle_deck_metrics(first_b['my_deck'], first_b, is_opponent=False)
            opp_metrics_f = self._get_battle_deck_metrics(first_b['opp_deck'], first_b, is_opponent=True)

            html += f'''
            <div class="cr-deck-card cr-opp-card-row cr-glass-premium" id="opp-section-{i}" style="height: auto !important; min-height: 0 !important; margin-bottom: 8px !important; padding-bottom: 2px !important; display: block; overflow: visible; position: relative;">
                <div class="cr-deck-header cr-opp-header-premium" style="padding: 4px 12px; background: rgba(255,255,255,0.02); border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div class="cr-opp-header-content-v2" style="display: flex; align-items: center; gap: 10px; width: 100%;">
                        <span class="cr-opp-rank" style="background: #fbbf24; color: #000; padding: 1px 5px; border-radius: 4px; font-weight: 900; font-size: 0.7em;">#{i}</span>
                        <span style="font-weight: 900; font-size: 0.95em; color: #f8fafc;"><span style="opacity: 0.5; font-size: 0.8em; margin-right: 4px;">OPONENTE:</span>{opp['opponent_name']}</span>
                        <span class="rival-badge {cat_class}-badge" style="margin-left: auto; font-size: 0.6em; padding: 2px 6px;">{category}</span>
                        <span class="cr-wr-badge" style="background:{wr_c}; font-weight: 900; font-size: 0.7em; padding: 2px 6px;">{wr}% WR</span>
                    </div>
                </div>

                <div class="cr-main-vs-stage" id="main-vs-{i}" style="padding: 0 12px 4px 12px !important; min-height: 0 !important; height: auto !important;">
                    <div class="cr-vs-stage-v2" style="height: auto !important; min-height: 0 !important;">
                        <!-- Amostragem da Batalha Premium v2 -->
                        <div class="cr-battle-preview-v2" style="display: grid; grid-template-columns: 1.8fr 0.4fr 1.8fr; align-items: center; gap: 10px; padding: 15px 0 20px 0; border-bottom: 1px solid rgba(255,255,255,0.03); margin-bottom: 15px; position: relative; z-index: 2;">
                            <!-- Lado Esquerdo: Player Style -->
                            <div style="text-align: left; display: flex; flex-direction: column; gap: 2px; overflow: hidden;">
                                <div style="font-size: 0.55em; color: rgba(255,255,255,0.25); font-weight: 800; letter-spacing: 1px;">#{self.player_tag}</div>
                                <div style="font-family: 'Krona One', sans-serif, system-ui; font-size: 1.1em; color: #fff; line-height: 1.2; font-weight: 950; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                    {player_name}
                                </div>
                                <div style="font-size: 0.55em; color: rgba(255,255,255,0.3); font-weight: 800; text-transform: uppercase;">{player_clan or 'Sem Clã'}</div>
                            </div>

                            <!-- Centro: Placar e Modo -->
                            <div style="text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;">
                                <div id="score-{i}" style="font-size: 2.8em; font-weight: 950; color: #fff; letter-spacing: -3px; line-height: 0.9; text-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                                    {first_b.get('crowns', 0)} - {first_b.get('opponent_crowns', 0)}
                                </div>
                                <div id="mode-{i}" style="background: rgba(15, 23, 42, 0.8); padding: 2px 10px; border-radius: 6px; font-size: 0.5em; font-weight: 900; color: rgba(255,255,255,0.4); border: 1px solid rgba(255,255,255,0.08); text-transform: uppercase; white-space: nowrap;">
                                    {first_b.get('modo_jogo', 'Batalha')}
                                </div>
                            </div>

                            <!-- Lado Direito: Opponent Style -->
                            <div style="text-align: right; display: flex; flex-direction: column; gap: 2px; overflow: hidden;">
                                <div style="font-size: 0.55em; color: rgba(255,255,255,0.25); font-weight: 800; letter-spacing: 1px;">#{opp['opponent_tag']}</div>
                                <div style="font-size: 1.25em; font-weight: 950; color: #f87171; text-transform: uppercase; letter-spacing: -0.5px; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                    <span style="opacity: 0.4; font-size: 0.6em; vertical-align: middle; margin-right: 2px;">OPONENTE:</span>{opp['opponent_name']}
                                </div>
                                <div style="font-size: 0.55em; color: rgba(255,255,255,0.3); font-weight: 800; text-transform: uppercase;">{opp.get('opp_clan', 'Sem Clã')}</div>
                            </div>
                        </div>

                        <!-- Decks e Torres -->
                        <div class="cr-vs-decks-grid-v2" style="gap: 10px; margin-top: 15px; height: auto !important; min-height: 0 !important;">
                            <div class="cr-side-container" style="position: relative; flex: 1; min-height: 130px !important; height: auto !important; background: transparent; padding: 0;">
                                <div id="p-tower-container-{i}" style="position: absolute; top: -45px; left: 50%; transform: translateX(-50%); width: 80px; height: 80px; z-index: 1;">
                                    <img id="p-tower-img-{i}" src="{my_metrics_f['tower_url']}" class="cr-tower-zoom" style="width: 100%; height: 100%; object-fit: contain; filter: drop-shadow(0 0 12px rgba(74, 222, 128, 0.4));">
                                    <div style="margin-top: -10px; display: flex; flex-direction: column; align-items: center;">
                                        <div class="cr-hp-bar-mini" style="width: 45px;"><div id="p-tower-bar-{i}" style="width: 100%; height: 100%; background: #4ade80;"></div></div>
                                        <div style="display: flex; flex-direction: column; align-items: center; gap: 1px;">
                                            <span id="p-tower-lv-{i}" class="cr-tower-lv-badge" style="position: static; transform: none; font-size: 8px; padding: 1px 5px; background: #000; border: 1px solid #fbbf24; color: #fff; border-radius: 4px; font-weight: 900; { 'display: none;' if my_metrics_f['level'] == 'N/A' else '' }">LV {my_metrics_f['level']}</span>
                                            <span id="p-tower-hp-{i}" style="font-size: 7px; color: #4ade80; font-weight: 900; line-height: 1;">{my_metrics_f.get('hp', '--')} HP</span>
                                        </div>
                                    </div>
                                </div>
                                <div id="p-grid-{i}" style="margin-top: 45px;">{self._generate_deck_grid_html_simple(first_b['my_deck'])}</div>
                            </div>

                            <div class="cr-side-container" style="position: relative; flex: 1; min-height: 130px !important; height: auto !important; background: transparent; padding: 0;">
                                <div id="o-tower-container-{i}" style="position: absolute; top: -45px; left: 50%; transform: translateX(-50%); width: 80px; height: 80px; z-index: 1;">
                                    <img id="o-tower-img-{i}" src="{opp_metrics_f['tower_url']}" class="cr-tower-zoom" style="width: 100%; height: 100%; object-fit: contain; transform: scaleX(-1); filter: drop-shadow(0 0 12px rgba(248, 113, 113, 0.4));">
                                    <div style="margin-top: -10px; display: flex; flex-direction: column; align-items: center;">
                                        <div class="cr-hp-bar-mini" style="width: 45px;"><div id="o-tower-bar-{i}" style="width: 100%; height: 100%; background: #f87171;"></div></div>
                                        <div style="display: flex; flex-direction: column; align-items: center; gap: 1px;">
                                            <span id="o-tower-lv-{i}" class="cr-tower-lv-badge" style="position: static; transform: none; font-size: 8px; padding: 1px 5px; background: #000; border: 1px solid #fbbf24; color: #fff; border-radius: 4px; font-weight: 900; { 'display: none;' if opp_metrics_f['level'] == 'N/A' else '' }">LV {opp_metrics_f['level']}</span>
                                            <span id="o-tower-hp-{i}" style="font-size: 7px; color: #f87171; font-weight: 900; line-height: 1;">{opp_metrics_f.get('hp', '--')} HP</span>
                                        </div>
                                    </div>
                                </div>
                                <div id="o-grid-{i}" style="margin-top: 45px;">{self._generate_deck_grid_html_simple(first_b['opp_deck'])}</div>
                            </div>
                        </div>

                        <!-- Footer Premium v2 - Estrutura de Paridade com Imagem -->
                        <div class="cr-vs-footer-v2" style="margin-top: 15px; padding: 12px; background: rgba(15, 23, 42, 0.4); border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); position: relative;">
                            <!-- Linha 1: Metricas (Dados da Luta) -->
                            <div style="display: grid; grid-template-columns: 1fr 1px 1fr; gap: 10px; align-items: center; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.03);">
                                <div id="player-metrics-{i}" style="display: flex; gap: 10px; justify-content: center;">
                                    {self._generate_metrics_panel_html_simple(my_metrics_f)}
                                </div>
                                <div style="width: 1px; background: rgba(255,255,255,0.1); height: 15px;"></div>
                                <div id="opp-metrics-{i}" style="display: flex; gap: 10px; justify-content: center;">
                                    {self._generate_metrics_panel_html_simple(opp_metrics_f)}
                                </div>
                            </div>
                            
                            <!-- Linha 2: Botoes de Acao (Copia de Decks) -->
                            <div style="margin-top: 10px; display: flex; justify-content: center; gap: 12px;">
                                <button id="p-copy-{i}" onclick="copyToClipboardDeckDirect({[c.strip() for c in first_b.get('my_deck','').split('|') if c.strip()]})" 
                                        style="background: rgba(59, 130, 246, 0.2); border: 1px solid rgba(59, 130, 246, 0.3); color: #93c5fd; padding: 5px 12px; border-radius: 6px; font-size: 0.65em; font-weight: 900; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s;">
                                    <i class="far fa-copy"></i> COPIAR MEU DECK
                                </button>
                                <button id="o-copy-{i}" onclick="copyToClipboardDeckDirect({[c.strip() for c in first_b.get('opp_deck','').split('|') if c.strip()]})" 
                                        style="background: rgba(248, 113, 113, 0.2); border: 1px solid rgba(248, 113, 113, 0.3); color: #fca5a5; padding: 5px 12px; border-radius: 6px; font-size: 0.65em; font-weight: 900; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s;">
                                    <i class="far fa-copy"></i> COPIAR OPONENTE
                                </button>
                            </div>

                            <!-- Linha 3: Data e Hora -->
                            <div style="margin-top: 8px; display: flex; justify-content: center; gap: 15px; font-size: 0.65em; color: rgba(255,255,255,0.2); font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">
                                <span id="date-{i}"><i class="far fa-calendar-alt"></i> {first_b.get('data_str','--/--').split(' ')[0]}</span>
                                <span id="time-{i}"><i class="far fa-clock"></i> {first_b.get('data_str','--/--').split(' ')[1] if ' ' in first_b.get('data_str','') else '--:--'}</span>
                            </div>
                        </div>

                        <!-- Secao de Historico (History Dots) -->
                        <div style="margin-top: 6px; padding: 8px 12px; background: rgba(0,0,0,0.25); border-radius: 12px; display: flex; align-items: center; gap: 12px; border: 1px solid rgba(255,255,255,0.03);">
                            <span style="font-size: 0.6em; font-weight: 950; color: rgba(255,255,255,0.2); text-transform: uppercase; letter-spacing: 1.5px; flex-shrink: 0;">HISTÓRICO:</span>
                            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                                {self._generate_history_dots(i, stats_list, player_name, player_clan, opp["opponent_name"], opp.get('opp_clan', ''), opp['opponent_tag'])}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''
        return html + "</div>"

    def generate_lethal_decks_html(self, lethal_decks: List[Dict]) -> str:
        """Gera HTML para os decks que mais causam derrotas com layout Premium v2."""
        if not lethal_decks: return '<div class="cr-empty-state">Dados insuficientes para mapear decks letais.</div>'
        
        html = '<div class="cr-decks-list">'
        for i, ld in enumerate(lethal_decks, 1):
            deck_str = ld['deck']
            losses = ld['losses_caused'] 
            opponents = ld['opponents_list']
            last = ld['last_encounter'][:16].replace('T', ' ')
            c_list = ld['cards']
            
            # Obter métricas para o deck letal
            metrics = self._get_deck_metrics(deck_str)
            tower_url = metrics.get('tower_url', 'https://cdn.royaleapi.com/static/img/cards-75/tower-princess.png')
            
            # Formatar lista de cartas para o botão de cópia
            cards_for_copy = [c.strip() for c in deck_str.split('|') if c.strip()]
            
            html += f'''
            <div class="cr-deck-card cr-glass-premium cr-lethal-card" style="border-left: 4px solid #f87171; min-height: auto; margin-bottom: 20px; padding-bottom: 12px; overflow: visible;">
                <div class="cr-deck-header" style="padding: 8px 15px; background: rgba(248, 113, 113, 0.08); border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div class="cr-deck-meta" style="display: flex; align-items: center; gap: 10px; width: 100%;">
                        <span class="cr-deck-rank" style="background:#f87171; color: #fff; padding: 2px 8px; border-radius: 5px; font-weight: 900; font-size: 0.75em;">#{i} LETHAL</span>
                        <span style="color: #fca5a5; font-size: 0.85em; font-weight: 900; letter-spacing: 0.5px;">{losses} DERROTAS CAUSADAS</span>
                        <span style="margin-left: auto; font-size: 0.65em; color: rgba(255,255,255,0.3); font-weight: 700;">VISTO EM: {last}</span>
                    </div>
                </div>
                <div class="cr-deck-body cr-lethal-body" style="padding: 10px 15px; background: transparent; overflow: visible;">
                    <div class="cr-lethal-layout" style="display: flex; flex-direction: column; gap: 5px; align-items: center;">
                        
                        <div class="cr-vs-decks-grid-v2" style="display: block; position: relative; width: 100%; max-width: 400px; margin: 45px auto 0 auto; overflow: visible;">
                            <div class="cr-side-container" style="position: relative; display: flex; flex-direction: column; align-items: center; background: transparent; padding: 0; min-height: auto; overflow: visible;">
                                <!-- Torre Flutuante Premium v2 -->
                                <div style="position: absolute; top: -50px; left: 50%; transform: translateX(-50%); width: 95px; height: 95px; z-index: 10;">
                                    <img src="{tower_url}" style="width: 100%; height: 100%; object-fit: contain; filter: drop-shadow(0 0 15px rgba(248, 113, 113, 0.6)); transform: scaleX(-1);">
                                    <div style="margin-top: -15px; display: flex; flex-direction: column; align-items: center; gap: 2px;">
                                        <div class="cr-hp-bar-mini" style="width: 50px; height: 3px; background: rgba(0,0,0,0.5); border-radius: 2px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1);">
                                            <div style="width: 100%; height: 100%; background: #f87171;"></div>
                                        </div>
                                        <div style="display: flex; flex-direction: column; align-items: center; gap: 1px;">
                                            <span class="cr-tower-lv-badge" style="position: static; transform: none; font-size: 8px; padding: 1px 5px; background: #000; border: 1px solid #f87171; color: #fff; border-radius: 4px; font-weight: 900; { 'display: none;' if metrics.get('level') == 'N/A' else '' }">LV {metrics.get('level')}</span>
                                            <span style="font-size: 8px; color: #f87171; font-weight: 900; line-height: 1;">{metrics.get('hp', '--')} HP</span>
                                        </div>
                                    </div>
                                </div>
                                <!-- Grid -->
                                <div class="cr-grid-wrapper-premium" style="position: relative; z-index: 2; margin-top: 50px; width: 100%;">
                                    <div class="cr-grid-4x2" style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.03);">
                                        {"".join(f'<div class="cr-card-wrap-premium" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img" loading="lazy"></div>' for c in c_list[:8])}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="cr-vs-footer-v2" style="margin-top: 15px; padding: 12px; background: rgba(15, 23, 42, 0.4); border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); position: relative; width: 100%; max-width: 400px;">
                            <div style="display: flex; justify-content: center; align-items: center; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.03);">
                                <div style="display: flex; gap: 10px; justify-content: center;">
                                    {self._generate_metrics_panel_html_simple(metrics)}
                                </div>
                            </div>
                            <div style="margin-top: 10px; display: flex; justify-content: center;">
                                <button onclick="copyToClipboardDeckDirect({cards_for_copy})" 
                                        style="background: rgba(248, 113, 113, 0.2); border: 1px solid rgba(248, 113, 113, 0.3); color: #fca5a5; padding: 6px 15px; border-radius: 8px; font-size: 0.7em; font-weight: 900; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s;">
                                    <i class="far fa-copy"></i> COPIAR DECK LETAL
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            '''
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
        """Gera o HTML para a seção de Decks de Elite (Guerra) e Meta Brasil com padrão Premium v2."""
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
                <button class="tab-button active" onclick="switchTab(event, 'clan-war')">Nossos Heróis</button>
                <button class="tab-button" onclick="switchTab(event, 'global-war')">Meta Global (Guerra)</button>
                <button class="tab-button" onclick="switchTab(event, 'meta-br')">Top 100 Brasil</button>
            </div>

            <div id="tab-clan-war" class="tab-content active">
                <div class="cr-decks-list-premium">
        """

        # Aba 1: Nossos Heróis
        for player in war_players['clan']:
            decks_html = ""
            for i, deck in enumerate(player['decks']):
                if not deck or len(deck) < 8: continue
                cards_html = "".join([f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(card)}" class="cr-card-img" title="{card}"></div>' for card in deck])
                copy_link = self.get_copy_deck_link(deck)
                
                decks_html += f"""
                <div class="deck-row-premium-v2">
                    <div class="deck-meta-header">
                        <span class="deck-index">DECK {i+1}</span>
                        <a href="{copy_link}" class="cr-copy-btn-v2">
                            <i class="fas fa-copy"></i> Copiar
                        </a>
                    </div>
                    <div class="cr-side-container">
                        <div class="cr-tower-floating left">
                            <div class="cr-tower-badge">LV 15</div>
                            <img src="./docs/princesa-tropa-de-torre-clash-royale.png" class="cr-tower-img-v2">
                            <div class="cr-hp-bar-v2"><div class="cr-hp-fill-v2" style="width: 100%;"></div></div>
                        </div>
                        <div class="cr-grid-wrapper-premium">
                            <div class="cr-grid-4x2">{cards_html}</div>
                        </div>
                    </div>
                </div>
                """

            html += f"""
            <div class="cr-glass-card-v2 war-card">
                <div class="war-card-header">
                    <div class="player-main-info">
                        <span class="player-rank">#{player['pos']}</span>
                        <span class="player-name">{player['name']}</span>
                    </div>
                    <div class="player-stats-badges">
                        <span class="stat-badge wr">{player['win_rate']:.1f}% WR</span>
                        <span class="stat-badge battles">{player['total_battles']} Lutas</span>
                    </div>
                </div>
                <div class="war-card-body">
                    {decks_html}
                </div>
            </div>
            """

        html += """
                </div>
            </div>

            <div id="tab-global-war" class="tab-content">
                <div class="cr-decks-list-premium">
        """

        # Aba 2: Meta Global (Guerra)
        for player in war_players['global']:
            decks_html = ""
            for i, deck in enumerate(player['decks']):
                if not deck or len(deck) < 8: continue
                cards_html = "".join([f'<div class="cr-card-wrap-premium"><img src="{self.get_card_image_path(card)}" class="cr-card-img" title="{card}"></div>' for card in deck])
                copy_link = self.get_copy_deck_link(deck)

                decks_html += f"""
                <div class="deck-row-premium-v2">
                    <div class="deck-meta-header">
                        <span class="deck-index">DECK {i+1}</span>
                        <a href="{copy_link}" class="cr-copy-btn-v2">
                            <i class="fas fa-copy"></i> Copiar
                        </a>
                    </div>
                    <div class="cr-side-container">
                        <div class="cr-tower-floating left">
                            <div class="cr-tower-badge">LV 15</div>
                            <img src="./docs/princesa-tropa-de-torre-clash-royale.png" class="cr-tower-img-v2">
                            <div class="cr-hp-bar-v2"><div class="cr-hp-fill-v2" style="width: 100%;"></div></div>
                        </div>
                        <div class="cr-grid-wrapper-premium">
                            <div class="cr-grid-4x2">{cards_html}</div>
                        </div>
                    </div>
                </div>
                """

            html += f"""
            <div class="cr-glass-card-v2 war-card">
                <div class="war-card-header">
                    <div class="player-main-info">
                        <span class="player-rank">GLOBAL</span>
                        <span class="player-name">{player['name']}</span>
                    </div>
                    <div class="player-stats-badges">
                        <span class="stat-badge wr">{player['win_rate']:.1f}% WR</span>
                    </div>
                </div>
                <div class="war-card-body">
                    {decks_html}
                </div>
            </div>
            """

        html += """
                </div>
            </div>

            <div id="tab-meta-br" class="tab-content">
                <div class="meta-br-grid-v2">
        """
        
        for p in meta_br[:40]: # Top 40 para grid visual
            rank = p.get('rank', '-')
            name = p.get('name', 'N/D')
            clan = p.get('clan', {}).get('name', '-')
            score = p.get('trophies') or p.get('score') or '-'
            
            html += f"""
            <div class="meta-br-item-v2">
                <div class="rank-circle">#{rank}</div>
                <div class="meta-info">
                    <span class="meta-name">{name}</span>
                    <span class="meta-clan">{clan}</span>
                </div>
                <div class="meta-score">{score} 🏆</div>
            </div>
            """
            
        html += """
                </div>
            </div>
            
            <style>
                .cr-decks-list-premium {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
                    gap: 25px;
                    padding: 10px 0;
                }
                
                .cr-glass-card-v2 {
                    background: rgba(30, 41, 59, 0.4);
                    backdrop-filter: blur(12px);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 20px;
                    overflow: hidden;
                    transition: all 0.3s ease;
                }
                
                .cr-glass-card-v2:hover {
                    transform: translateY(-5px);
                    background: rgba(30, 41, 59, 0.6);
                    border-color: rgba(255, 255, 255, 0.15);
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }
                
                .war-card-header {
                    padding: 15px 20px;
                    background: rgba(255,255,255,0.03);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }
                
                .player-rank {
                    font-size: 0.8em;
                    font-weight: 900;
                    color: #63b3ed;
                    background: rgba(99, 179, 237, 0.1);
                    padding: 2px 8px;
                    border-radius: 6px;
                    margin-right: 10px;
                }
                
                .player-name {
                    font-size: 1.1em;
                    font-weight: 700;
                    color: #f8fafc;
                }
                
                .stat-badge {
                    font-size: 0.75em;
                    font-weight: 700;
                    padding: 3px 10px;
                    border-radius: 20px;
                    margin-left: 5px;
                }
                
                .stat-badge.wr { background: rgba(72, 187, 120, 0.15); color: #68d391; }
                .stat-badge.battles { background: rgba(160, 174, 192, 0.15); color: #cbd5e0; }
                
                .war-card-body { padding: 15px; }
                
                .deck-row-premium-v2 {
                    background: rgba(15, 23, 42, 0.3);
                    border-radius: 15px;
                    padding: 12px;
                    margin-bottom: 15px;
                }
                
                .deck-meta-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                }
                
                .deck-index { font-size: 0.7em; font-weight: 800; color: #94a3b8; letter-spacing: 1px; }
                
                .cr-copy-btn-v2 {
                    font-size: 0.7em;
                    color: #f6e05e;
                    text-decoration: none;
                    background: rgba(246, 224, 94, 0.1);
                    padding: 4px 12px;
                    border-radius: 8px;
                    transition: all 0.2s;
                }
                
                .cr-copy-btn-v2:hover { background: rgba(246, 224, 94, 0.2); }
                
                /* Meta BR Grid */
                .meta-br-grid-v2 {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                    gap: 15px;
                    padding: 10px 0;
                }
                
                .meta-br-item-v2 {
                    background: rgba(30, 41, 59, 0.3);
                    border: 1px solid rgba(255,255,255,0.05);
                    border-radius: 12px;
                    padding: 12px 15px;
                    display: flex;
                    align-items: center;
                    gap: 15px;
                }
                
                .rank-circle {
                    width: 35px;
                    height: 35px;
                    background: #2d3748;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 0.8em;
                    font-weight: 900;
                    color: #f6e05e;
                    flex-shrink: 0;
                }
                
                .meta-info { flex-grow: 1; display: flex; flex-direction: column; }
                .meta-name { font-weight: 700; color: #f8fafc; font-size: 0.9em; }
                .meta-clan { font-size: 0.75em; color: #94a3b8; }
                .meta-score { font-weight: 900; color: #63b3ed; font-size: 0.9em; }

                @media (max-width: 768px) {
                    .cr-decks-list-premium { grid-template-columns: 1fr; }
                    .meta-br-grid-v2 { grid-template-columns: 1fr; }
                }
            </style>
        </div>
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
<html lang="pt-br">
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
            --glass-bg: #0f172a; /* Solid Slate */
            --glass-border: rgba(255, 255, 255, 0.08);
            --glass-blur: 0px;
            --primary: #4299e1;
            --primary-glow: rgba(66, 153, 225, 0.5);
            --accent: #f6ad55;
            --success: #48bb78;
            --danger: #f56565;
            --bg-dark: #020617;
            --card-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
            --premium-gradient: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
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
            max-width: 1350px;
            margin: 0 auto;
            padding: 40px 20px;
            animation: cr-fade-in-up 0.8s cubic-bezier(0.2, 0.8, 0.2, 1);
        }

        @keyframes cr-fade-in-up {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .glass-panel, .cr-glass-premium {
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
            background: linear-gradient(90deg, transparent, var(--primary), var(--accent), transparent);
            box-shadow: 0 0 20px var(--primary-glow);
        }

        .header h1 {
            font-size: 3.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
        }

        .player-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            width: 100%;
        }

        .stat-card {
            padding: 24px;
            background: rgba(30, 41, 59, 0.5);
            border-radius: 20px;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 1px solid rgba(255,255,255,0.05);
        }

        .stat-card:hover {
            transform: translateY(-8px);
            background: rgba(30, 41, 59, 0.8);
            border-color: var(--primary);
            box-shadow: 0 15px 35px rgba(0,0,0,0.4), 0 0 15px var(--primary-glow);
        }

        .stat-card h3 {
            font-size: 0.75em;
            color: #94a3b8;
            margin-bottom: 8px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .stat-card .value {
            font-size: 2em;
            font-weight: 900;
            color: #fff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        .section {
            padding: 40px;
            margin-bottom: 40px;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: var(--card-shadow);
        }

        .battle-cards {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-top: 20px;
        }

        .section h2 {
            font-size: 2em;
            margin-bottom: 35px;
            display: flex;
            align-items: center;
            gap: 20px;
            color: #fff;
        }

        .section h2::after {
            content: '';
            flex: 1;
            height: 2px;
            background: linear-gradient(90deg, var(--primary), transparent);
            opacity: 0.3;
        }

        .cr-opponents-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 20px;
            padding: 10px;
            width: 100%;
        }

        @media (max-width: 900px) {
            .cr-opponents-list {
                grid-template-columns: 1fr !important;
            }
        }


        .cr-deck-card {
            border-radius: 20px;
            overflow: hidden;
            background: #0f172a;
            border: 1px solid rgba(255,255,255,0.08);
            transition: all 0.5s cubic-bezier(0.2, 0.8, 0.2, 1);
            position: relative;
            box-shadow: 0 15px 45px rgba(0,0,0,0.4);
            height: auto !important;
            min-height: 0 !important;
        }

        .cr-deck-card img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }

        .cr-deck-card:hover {
            transform: scale(1.01);
            border-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 25px 60px rgba(0,0,0,0.6);
        }

        .cr-timeline-container {
            margin-top: 20px;
            padding: 20px 30px;
            background: rgba(0,0,0,0.2);
            border-top: 1px solid rgba(255,255,255,0.05);
        }

        .cr-timeline-header-text {
            font-size: 0.75em;
            color: #64748b;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 15px;
        }

        .cr-timeline-scroll {
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding: 10px 5px;
            scrollbar-width: thin;
            scrollbar-color: var(--primary) transparent;
        }

        .cr-timeline-scroll::-webkit-scrollbar { height: 6px; }
        .cr-timeline-scroll::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 10px; }

        .cr-date-selector {
            flex: 0 0 auto;
            padding: 8px 16px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .cr-date-selector:hover {
            background: rgba(30, 41, 59, 0.8);
            border-color: var(--primary);
            transform: translateY(-3px);
        }

        .cr-date-selector.active {
            background: var(--primary);
            border-color: #fff;
            box-shadow: 0 0 20px var(--primary-glow);
            transform: scale(1.05);
        }

        .cr-date-selector.active .cr-date-text-small { color: #fff; }

        .cr-result-dot {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.6em;
            font-weight: 900;
            color: #fff;
        }

        .cr-date-text-small {
            font-size: 0.8em;
            color: #94a3b8;
            font-weight: 600;
        }

        .cr-history-dots-row {
            display: flex;
            gap: 6px;
            overflow-x: auto;
            padding: 10px 0;
            justify-content: center;
            width: 100%;
            scrollbar-width: none;
        }

        .cr-history-dots-row::-webkit-scrollbar { display: none; }

        .cr-history-dot {
            width: 28px;
            height: 28px;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }

        .cr-history-dot .dot-res {
            font-size: 0.7em;
            font-weight: 900;
            color: #fff;
        }

        .cr-history-dot .dot-time {
            font-size: 0.5em;
            color: #94a3b8;
            margin-top: -2px;
        }

        .cr-history-dot:hover {
            transform: translateY(-3px);
            border-color: var(--primary);
            background: rgba(30, 41, 59, 0.8);
        }

        .cr-history-dot.active {
            background: var(--primary);
            border-color: #fff;
            box-shadow: 0 0 15px var(--primary-glow);
            transform: scale(1.1);
        }

        .cr-history-dot.active .dot-time { color: rgba(255,255,255,0.8); }

        /* Lethal Decks Premium v2 Styles */
        .cr-lethal-card {
            margin-bottom: 20px;
        }

        .cr-lethal-body {
            flex-direction: row !important;
            align-items: center;
            gap: 40px !important;
        }

        .cr-lethal-grid-wrap {
            flex: 0 0 320px;
        }

        .cr-lethal-stats {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .cr-lethal-info {
            font-size: 1em;
            color: #e2e8f0;
            line-height: 1.6;
        }

        .cr-lethal-date {
            font-size: 0.9em;
            color: #94a3b8;
        }

        .cr-lethal-warning {
            display: inline-block;
            background: rgba(245, 101, 101, 0.15);
            color: #feb2b2;
            padding: 10px 20px;
            border-radius: 12px;
            font-weight: 800;
            font-size: 0.8em;
            text-transform: uppercase;
            border: 1px solid rgba(245, 101, 101, 0.3);
            letter-spacing: 1px;
            animation: cr-pulse-red 3s infinite;
        }

        /* Utils */
        .cr-toast-premium {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--primary);
            color: #fff;
            padding: 12px 30px;
            border-radius: 50px;
            font-weight: 700;
            z-index: 10000;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            animation: cr-fade-in-up 0.3s ease;
            transition: opacity 0.5s;
        }

        .cr-bg-info-style {
            font-size: 0.8em;
            opacity: 0.6;
            margin-top: 10px;
        }

        .cr-bg-info-style a {
            color: var(--primary);
            text-decoration: none;
        }

        .cr-bg-info-style a:hover { text-decoration: underline; }

        .cr-deck-header {
            padding: 25px 35px;
            background: linear-gradient(to right, rgba(30,41,59,0.6), rgba(15,23,42,0.9));
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .cr-deck-rank {
            background: rgba(255,255,255,0.08);
            color: #94a3b8;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 800;
            font-size: 0.75em;
            text-transform: uppercase;
        }

        .cr-wr-badge {
            font-weight: 900;
            padding: 8px 18px;
            border-radius: 12px;
            font-size: 0.95em;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }

        .cr-deck-body {
            padding: 30px;
            display: flex;
            flex-direction: column;
            gap: 25px;
        }

        /* VS Stage Premium v2 - Unified Layout */
        .cr-main-vs-stage {
            padding: 10px 5px;
            background: transparent;
            position: relative;
            border-radius: 24px;
            border: none;
            overflow: visible;
        }

        .cr-vs-stage-v2 {
            display: flex;
            flex-direction: column;
            gap: 10px;
            width: 100%;
            max-width: none;
            margin: 0 auto;
        }

        .cr-vs-header-compact {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            padding: 8px 20px;
            background: transparent;
            border: none;
            border-radius: 20px 20px 0 0;
            margin-bottom: 10px;
        }

        .cr-vs-player-info {
            display: flex;
            flex-direction: column;
            gap: 2px;
            flex: 1; 
            min-width: 0;
            overflow: hidden;
        }

        .cr-vs-player-name {
            font-size: 0.85em;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            overflow: visible;
            white-space: normal;
            line-height: 1.1;
            word-break: break-word;
            max-width: 100%;
        }

        .cr-vs-player-clan {
            font-size: 0.7em;
            color: #94a3b8;
            opacity: 0.7;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .cr-vs-score-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 2px;
            flex: 0 0 90px;
        }

        .cr-vs-score-main {
            font-size: 1.2em;
            font-weight: 900;
            font-family: 'Outfit', sans-serif;
            color: #fff;
            letter-spacing: 1px;
            text-shadow: 0 0 15px rgba(255,255,255,0.2);
        }

        .cr-vs-decks-grid-v2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 0 20px;
            width: 100%;
            position: relative;
        }

        .cr-side-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            min-height: auto !important;
            justify-content: flex-end;
        }

        .cr-tower-overlap {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1;
            opacity: 0.25;
            transition: all 0.3s ease;
            pointer-events: none;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .cr-tower-img-premium {
            max-height: 150px;
            object-fit: contain;
            filter: drop-shadow(0 0 20px rgba(0,0,0,0.5));
        }

        .cr-tower-overlap .cr-card-level-badge {
            position: absolute;
            bottom: 20px;
            right: 20%;
            z-index: 2;
        }

        .cr-tower-overlap:hover {
            opacity: 0.4;
        }


        .cr-grid-wrapper-premium {
            position: relative;
            width: 100%;
            max-width: 420px;
            margin: 0 auto;
            z-index: 20; /* Increased to ensure it is above tower */
        }

        .cr-grid-4x2 {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            padding: 12px;
            background: rgba(0,0,0,0.3);
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.05);
            width: 100%;
            box-shadow: inset 0 4px 15px rgba(0,0,0,0.3);
        }

        /* Top Row: Towers & Score */
        .cr-vs-top-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            padding: 0 40px;
            margin-bottom: 10px;
        }

        /* New Modal & Static Layout Premium v2 */
        .cr-modal-top-stage, .cr-vs-top-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            padding: 20px 40px;
            background: transparent;
            border: none;
            border-radius: 24px 24px 0 0;
            margin-bottom: 20px;
        }

        .cr-tower-stage-p {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0;
            width: 200px;
            position: relative;
            z-index: 1;
        }

        .cr-tower-img-large {
            width: 155px;
            height: 155px;
            object-fit: contain;
            filter: drop-shadow(0 15px 35px rgba(0,0,0,0.7));
            transition: all 0.45s cubic-bezier(0.23, 1, 0.32, 1);
            margin-bottom: -30px;
            position: relative;
            z-index: 1;
        }


        .cr-tower-lv-badge {
            position: absolute;
            top: -8px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(180deg, #1e293b, #020617);
            color: #fbbf24;
            font-size: 0.78em;
            font-weight: 950;
            padding: 3px 10px;
            border-radius: 7px;
            border: 1.5px solid #fbbf24;
            z-index: 10;
            box-shadow: 0 4px 15px rgba(0,0,0,0.85);
            border-bottom: 3.5px solid #b45309;
            text-shadow: 0 1px 2px rgba(0,0,0,1);
            letter-spacing: 0.6px;
            pointer-events: none;
            white-space: nowrap;
        }


        .cr-tower-img-large:hover {
            transform: translateY(-8px) scale(1.06);
            filter: drop-shadow(0 20px 45px rgba(0, 0, 0, 0.8));
            z-index: 5;
        }

        .cr-mirror-opponent {
            transform: scaleX(-1);
        }
        
        .cr-mirror-opponent:hover {
            transform: translateY(-8px) scale(-1.06, 1.06);
        }

        .cr-modal-score-center {
            flex: 1;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
        }

        .cr-modal-decks-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 0 30px;
            width: 100%;
            max-width: 900px;
            margin: 0 auto;
            position: relative;
            z-index: 3;
        }

        .cr-vs-metrics-unified {
            display: flex;
            flex-direction: column;
            gap: 8px;
            background: transparent;
            border-top: 1px solid rgba(255,255,255,0.05);
            border-radius: 0 0 24px 24px;
            margin-top: 5px;
            padding: 10px 15px;
        }

        .cr-vs-footer-metrics {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 15px;
            align-items: center;
        }

        .cr-vs-divider-light {
            height: 1px;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.05), transparent);
            width: 80%;
            margin: 0 auto;
        }

        .cr-vs-date-inline-p {
            display: flex;
            justify-content: center;
            gap: 10px;
            font-size: 0.65em;
            color: rgba(255,255,255,0.5);
            font-weight: 700;
            margin-top: 5px;
        }

        .cr-side-metrics-group {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .cr-vs-row-premium-v2 {
            display: flex;
            flex-direction: column;
            gap: 30px;
            width: 100%;
        }

        .cr-vs-decks-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            padding: 0 50px;
            width: 100%;
        }

        @media (max-width: 1000px) {
            .cr-vs-decks-grid, .cr-modal-decks-grid {
                grid-template-columns: 1fr;
                gap: 30px;
                padding: 0 15px;
            }
            .cr-modal-top-stage, .cr-vs-top-row {
                flex-direction: column;
                gap: 20px;
                padding: 20px;
            }
            .cr-tower-stage-p {
                width: 100%;
            }
            .cr-vs-footer-metrics {
                grid-template-columns: 1fr;
                gap: 10px;
            }
            .cr-vs-divider-light {
                display: none;
            }
        }

        .cr-deck-side {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 25px;
            width: 100%;
        }

        .cr-tower-card-premium {
            width: 90px;
            height: 110px;
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
            border-radius: 16px;
            border: 2px solid rgba(255, 255, 255, 0.1);
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .cr-tower-card-premium:hover {
            transform: translateY(-10px) scale(1.1);
            border-color: var(--primary);
            box-shadow: 0 20px 40px rgba(0,0,0,0.6), 0 0 20px var(--primary-glow);
        }

        .cr-tower-img-premium {
            width: 80%;
            height: 80%;
            object-fit: contain;
            filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
        }

        .cr-card-level-badge {
            position: absolute;
            bottom: -8px;
            background: #1e293b;
            color: #fff;
            font-size: 0.65em;
            font-weight: 900;
            padding: 2px 8px;
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
        }

        .cr-player-header-premium {
            text-align: center;
        }

        .cr-player-name-premium {
            font-size: 1.5em;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }

        .player-color-text { color: var(--primary); }
        .opp-color-text { color: var(--danger); }

        /* Card Wrapper Premium */
        .cr-card-wrap-premium {
            aspect-ratio: 5/6;
            background: #1e293b;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            position: relative;
            overflow: hidden;
            transition: all 0.3s;
            box-shadow: 0 4px 10px rgba(0,0,0,0.4);
        }

        .cr-card-wrap-premium:hover {
            transform: scale(1.1) translateY(-5px);
            z-index: 10;
            border-color: var(--primary);
            box-shadow: 0 15px 30px rgba(0,0,0,0.6);
        }

        .cr-card-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        /* Evolution Effects */
        .cr-card-evo-border {
            border: 2px solid #ff00ff !important;
            box-shadow: 0 0 20px rgba(255, 0, 255, 0.5), inset 0 0 10px rgba(255, 0, 255, 0.3);
        }

        .cr-card-evo-border::after {
            content: 'EVO';
            position: absolute;
            top: -5px; right: -5px;
            background: #ff00ff;
            color: #fff;
            font-size: 0.55em;
            font-weight: 900;
            padding: 2px 6px;
            border-radius: 4px;
            box-shadow: 0 0 10px #ff00ff;
            z-index: 5;
        }

        /* Metrics Horizontal Premium */
        .cr-deck-metrics-horizontal {
            display: flex;
            justify-content: space-around;
            align-items: center;
            background: rgba(15, 23, 42, 0.6);
            padding: 12px 20px;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.08);
            width: 100%;
            max-width: 500px;
            margin: 0 auto;
        }

        .cr-hp-metric-border {
            border-left: 1px solid rgba(255,255,255,0.1); 
            padding-left:15px;
        }

        .cr-metrics-wrap-p {
            display: flex;
            justify-content: space-around;
            align-items: center;
            width: 100%;
            gap: 5px;
        }

        .cr-metric-inline {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 0.65em;
            font-weight: 800;
            color: #fff;
            transition: all 0.2s;
            white-space: nowrap;
        }

        .cr-metric-inline:hover {
            transform: translateY(-2px);
            color: #fff;
            filter: drop-shadow(0 0 8px var(--primary-glow));
        }

        .cr-elixir-icon-p {
            width: 12px !important;
            height: 12px !important;
            object-fit: contain;
            vertical-align: middle;
        }

        .cr-leak-icon-small {
            width: 22px !important;
            height: 22px !important;
            object-fit: contain;
            margin-right: 4px;
            vertical-align: middle;
        }

        .cr-leak-icon {
            width: 12px !important;
            height: 12px !important;
            object-fit: contain;
            filter: drop-shadow(0 0 6px rgba(245, 101, 101, 0.6));
            animation: cr-pulse-leak 2s infinite ease-in-out;
        }

        @keyframes cr-pulse-leak {
            0% { transform: scale(1); opacity: 0.8; }
            50% { transform: scale(1.15); opacity: 1; }
            100% { transform: scale(1); opacity: 0.8; }
        }

        .cr-metric-inline .cr-icon {
            font-size: 1em;
            filter: drop-shadow(0 0 5px rgba(255,255,255,0.2));
        }

        /* Elixir Leak Animations */
        .cr-leak-warning { color: #f6ad55; }
        .cr-leak-critical { 
            color: #f56565; 
            text-shadow: 0 0 10px rgba(245, 101, 101, 0.5);
            animation: cr-pulse-red 2s infinite;
        }

        @keyframes cr-pulse-red {
            0% { transform: scale(1); filter: brightness(1); }
            50% { transform: scale(1.05); filter: brightness(1.3); }
            100% { transform: scale(1); filter: brightness(1); }
        }

        .cr-battle-vs-center {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 12px;
            min-width: 160px;
            padding: 20px;
        }

        .cr-battle-result-badge {
            padding: 15px 35px;
            border-radius: 50px;
            background: #020617;
            border: 2px solid rgba(255,255,255,0.15);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            gap: 20px;
            font-family: 'Outfit', sans-serif;
            font-weight: 900;
            transform: skewX(-15deg);
        }

        .cr-score-badge-large {
            font-size: 2.2em;
            min-width: 140px;
            justify-content: center;
        }

        .cr-score-val, .cr-score-badge-large span {
            color: #fff;
            letter-spacing: 2px;
            transform: skewX(15deg);
        }

        .cr-score-divider {
            opacity: 0.3;
            transform: skewX(15deg);
        }

        .cr-mode-tag-premium {
            color: #94a3b8;
            font-size: 0.5em;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: rgba(255,255,255,0.05);
            padding: 2px 6px;
            border-radius: 4px;
        }

        .cr-score-display-premium {
            font-size: 2.5em;
            font-weight: 900;
            color: #fff;
            text-shadow: 0 4px 15px rgba(0,0,0,0.5);
            font-family: 'Outfit', sans-serif;
        }

        .cr-vs-text-bg {
            font-weight: 900;
            color: rgba(255,255,255,0.03);
            font-size: 2.5em;
            line-height: 1;
            margin-top: 10px;
            user-select: none;
        }

        .cr-battle-date-p {
            color: rgba(255,255,255,0.4);
            font-size: 0.85em;
            font-weight: 700;
        }

        .cr-swords-icon {
            font-size: 2.5em;
            margin-top: 15px;
            filter: drop-shadow(0 0 10px rgba(255,255,255,0.2));
            opacity: 0.5;
        }

        /* Timeline Selectors */
        .cr-timeline-container {
            background: #050914;
            padding: 25px 40px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        .cr-timeline-header-text {
            color:#64748b;
            font-size:0.7em;
            font-weight:900;
            text-transform:uppercase;
            letter-spacing:1.5px;
            margin-bottom:15px;
        }

        .cr-timeline-scroll {
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding-bottom: 15px;
            scrollbar-width: thin;
        }

        .cr-date-selector {
            flex: 0 0 auto;
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 18px;
            background: rgba(30, 41, 59, 0.4);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 16px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .cr-date-selector:hover {
            background: rgba(30, 41, 59, 0.8);
            border-color: var(--primary);
            transform: translateY(-3px);
        }

        .cr-date-selector.active {
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 10px 20px var(--primary-glow);
        }

        .cr-result-dot {
            width: 18px;
            height: 18px;
            font-size: 0.55em;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 5px;
            font-weight: 900;
            color: #fff;
        }

        .cr-date-text-small {
            color: #94a3b8;
            font-size: 0.65em;
            font-weight: 700;
        }

        .cr-date-selector.active .cr-date-text-small {
            color: #fff;
        }

        .cr-copy-deck-btn {
            position: absolute;
            bottom: 4px;
            right: 4px;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px;
            color: #fff;
            text-decoration: none;
            transition: all 0.2s;
            z-index: 10;
            font-size: 10px;
        }

        .cr-copy-deck-btn span {
            display: inline-block;
            transition: transform 0.2s;
        }

        .cr-copy-deck-btn:hover span {
            transform: scale(1.2);
        }

        .cr-copy-deck-btn:hover {
            background: rgba(15, 23, 42, 0.8);
            border-color: var(--primary);
            color: var(--primary);
        }

        .cr-vs-actions-row {
            display: none; /* Removed large buttons */
        }

        /* Opponents List Row Premium */
        .cr-opponents-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
        }

        @media (max-width: 1200px) {
            .cr-opponents-list {
                grid-template-columns: 1fr;
            }
        }

        .cr-opp-card-row {
            width: 100%;
            max-width: none;
            margin-bottom: 0;
        }

        .cr-opp-header-premium {
            padding: 25px 40px;
            background: linear-gradient(to right, rgba(30,41,59,0.5), rgba(15,23,42,0.8));
        }

        .cr-opp-header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            flex-wrap: wrap;
            gap: 10px;
        }

        .cr-opp-rank-badge {
            background: rgba(255,255,255,0.1);
            color: #94a3b8;
            font-size: 0.8em;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            margin-right: 15px;
        }

        .cr-opp-name-main {
            font-size: 1.1em;
            color: #fff;
            font-weight: 900;
            letter-spacing: -0.5px;
            white-space: normal;
            word-break: break-word;
            max-width: 250px;
        }

        .cr-opp-stats-summary {
            text-align: right;
        }

        .cr-opp-tag-small {
            font-size: 0.8em;
            color: #64748b;
            font-family: monospace;
            display: block;
            margin-bottom: 4px;
        }

        /* Modal Glassmorphism v2 */
        .cr-modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(2, 6, 23, 0.7);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.4s ease;
        }

        .cr-modal-overlay.active {
            display: flex;
            opacity: 1;
        }

        .cr-modal-container {
            width: 95%;
            max-width: 1450px;
            max-height: 92vh;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 30px;
            box-shadow: 0 25px 100px rgba(0,0,0,0.8), inset 0 0 0 1px rgba(255,255,255,0.05);
            position: relative;
            padding: 15px; /* Reduzido de 20px */
            overflow-y: auto;
            transform: scale(0.95);
            transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            display: flex;
            flex-direction: column;
        }

        .cr-modal-overlay.active .cr-modal-container {
            transform: scale(1);
        }

        .cr-modal-close {
            position: absolute;
            top: 25px;
            right: 30px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.3s;
            z-index: 10;
        }

        .cr-modal-close:hover {
            background: var(--primary);
            transform: rotate(90deg);
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

        /* Histogram Premium v2 (Glassmorphism) */
        .chart-container {
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 30px 25px 60px 25px;
            margin: 25px 0;
            position: relative;
            box-shadow: 0 15px 35px rgba(0,0,0,0.4);
            overflow: visible;
        }

        .chart-container.histogram-desktop { display: block; }
        .chart-container.histogram-mobile { display: none; }

        .stacked-histogram {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            height: 200px;
            gap: 10px;
            padding: 0 5px;
        }

        .histogram-bar {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            gap: 6px;
            position: relative;
            height: 100%;
        }

        .bar-stack {
            width: 100%;
            display: flex;
            flex-direction: column-reverse;
            gap: 2px;
            border-radius: 8px;
            overflow: hidden;
            background: rgba(255,255,255,0.02);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .bar-stack:hover {
            transform: scaleY(1.05);
            box-shadow: 0 0 20px rgba(255,255,255,0.1);
        }

        /* MEDIA QUERIES PARA MOBILE (TASK 3) */
        @media (max-width: 1024px) {
            .cr-vs-row { gap: 30px; }
            .cr-tower-img-premium { width: 90px; height: 90px; }
            .cr-tower-card-premium { width: 110px; height: 140px; }
        }

        @media (max-width: 768px) {
            .container {
                width: 95% !important;
                max-width: 100% !important;
                padding: 15px 10px !important;
                margin: 10px auto !important;
            }
            
            .cr-modal-container {
                width: 95% !important;
                max-width: 95% !important;
                padding: 20px 15px !important;
                border-radius: 16px !important;
            }

            .header h1 { font-size: 1.6em; }
            
            /* Palco VS Mobile */
            .cr-main-vs-stage > div:first-child {
                flex-direction: column !important;
                gap: 25px !important;
            }

            /* Placar no topo */
            .cr-main-vs-stage div[style*="flex:0 0 200px"], 
            .cr-main-vs-stage div[id^="mode-"] {
                order: -1 !important;
                width: 100% !important;
                flex: none !important;
                margin-bottom: 10px;
            }

            .cr-vs-row, .cr-vs-decks-row-premium {
                flex-direction: column !important;
                grid-template-columns: 1fr !important;
                align-items: center !important;
                gap: 30px !important;
            }

            /* Esconder o VS no meio para poupar espaço no mobile */
            .cr-vs-decks-row-premium > div:nth-child(2) {
                display: none !important;
            }

            .cr-deck-side {
                width: 100% !important;
                max-width: 100% !important;
            }

            .cr-tower-img-premium {
                width: 90px !important;
                height: 90px !important;
            }

            .cr-tower-card-premium {
                width: 100px !important;
                height: 125px !important;
                margin-bottom: 5px !important;
            }

            .cr-grid-4x2 {
                grid-template-columns: repeat(4, 1fr) !important;
                gap: 8px !important;
                padding: 4px !important;
            }

            .cr-player-name-vs, .cr-player-name-premium {
                font-size: 1.35em !important;
            }

            .cr-vs-center-divider, .cr-vs-divider-vertical {
                padding: 15px 0;
                font-size: 2em !important;
                opacity: 0.8 !important;
            }

            .cr-battle-preview {
                padding: 15px 10px !important;
            }

            .cr-copy-deck-btn {
                width: 100% !important;
                justify-content: center !important;
                padding: 12px !important;
            }

            /* Histogram Mobile Adjustments */
            .chart-container.histogram-desktop { display: none; }
            .chart-container.histogram-mobile { display: block; }
            
            .chart-container {
                padding: 20px 10px 50px 10px !important;
                margin: 15px 0 !important;
            }

            .stacked-histogram {
                height: 160px !important;
                gap: 6px !important;
            }

            .bar-date {
                bottom: -35px !important;
                font-size: 0.65em !important;
            }

            .histogram-legend {
                gap: 15px !important;
                margin-top: 40px !important;
            }
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
            bottom: -40px;
            left: 50%;
            transform: translateX(-50%) rotate(-45deg);
            font-size: 0.75em;
            color: #94a3b8;
            white-space: nowrap;
            font-weight: 700;
            font-family: 'Inter', sans-serif;
        }

        /* Histogram Legend Premium */
        .histogram-legend {
            display: flex;
            justify-content: center;
            gap: 25px;
            margin-top: 50px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.05);
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.85em;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .legend-color {
            width: 14px;
            height: 14px;
            border-radius: 4px;
            box-shadow: 0 0 10px rgba(0,0,0,0.3);
        }

        .legend-wins { background: var(--success); }
        .legend-losses { background: var(--danger); }
        .legend-draws { background: var(--accent); }

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

        @media (max-width: 1100px) {
            .cr-opponents-list, .battle-cards {
                grid-template-columns: 1fr;
            }
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
            width: 1450px !important;
            max-width: 98% !important;
            background: #0f172a; /* Fundo sólido para legibilidade máxima */
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 24px;
            box-shadow: 0 0 100px rgba(0, 0, 0, 0.9), 0 25px 50px -12px rgba(0, 0, 0, 0.6);
            padding: 20px;
            position: relative;
            transform: scale(0.9);
            transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            overflow-y: auto;
            max-height: 92vh;
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

        /* Tabs System Premium v2 */
        .deck-tabs-container { margin-top: 20px; }
        .deck-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
            padding: 8px;
            background: rgba(15, 23, 42, 0.4);
            border-radius: 16px;
            border: 1px solid var(--glass-border);
            overflow-x: auto;
            scrollbar-width: none;
        }
        .deck-tabs::-webkit-scrollbar { display: none; }

        .tab-button {
            padding: 12px 24px;
            background: transparent;
            border: 1px solid transparent;
            border-radius: 12px;
            color: #94a3b8;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 0.9em;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            white-space: nowrap;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .tab-button:hover {
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
        }

        .tab-button.active {
            background: var(--primary);
            color: #fff;
            border-color: rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 20px var(--primary-glow);
            transform: translateY(-2px);
        }

        .tab-content {
            display: none;
            animation: cr-fade-in 0.5s ease;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes cr-fade-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
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
<html lang="pt-br">
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
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    {self.generate_dashboard_scripts()}
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
