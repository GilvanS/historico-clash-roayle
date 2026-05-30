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
from war_prediction_engine import WarPredictionEngine

# Carrega variáveis de ambiente
load_dotenv()


logger = logging.getLogger(__name__)

# Horarios de virada de dia por conta (hora em que o "dia" comeca/termina)
# Conta Principal: 00:00 (meia-noite)
# Conta Secundaria: 21:00 (9h da noite do dia anterior)
# Guerra de Clã: 07:00 (7h da manha)
DAY_ROLLOVER_HOURS = {
    'primary': 0,    # Conta Principal vira a 00:00
    'secondary': 21, # Conta Secundaria vira a 21:00
    'war': 7,        # Guerra vira a 07:00
}

def _get_brt_now() -> datetime:
    """Retorna datetime local do Brasil (BRT = UTC-3) naive."""
    return (datetime.now(timezone.utc) - timedelta(hours=3)).replace(tzinfo=None)

def _get_battle_date(battle_time_str: str, rollover_hour: int = 0) -> str:
    """
    Calcula a data correta de uma batalha baseada no horario de virada do dia.
    
    Conta Secundaria (rollover=21h):
      - Batalha 20/05 20:41 (hour 20 < 21) -> dia 20/05
      - Batalha 20/05 21:35 (hour 21 >= 21) -> dia 21/05
    
    Conta Principal (rollover=0h):
      - Batalha 20/05 23:59 -> dia 20/05
      - Batalha 21/05 00:00 -> dia 21/05
    
    Args:
        battle_time_str: Data/hora da batalha no formato ISO ou similar
        rollover_hour: Hora em que o dia vira (0=meia-noite, 21=21h, 7=7h)
    
    Returns:
        String da data no formato YYYY-MM-DD considerando o rollover
    """
    if not battle_time_str:
        return ''
    
    try:
        # Parse da data/hora
        b_time_str = battle_time_str.replace('Z', '')
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M']:
            try:
                dt = datetime.strptime(b_time_str, fmt)
                break
            except ValueError:
                continue
        else:
            return battle_time_str.split('T')[0] if 'T' in battle_time_str else battle_time_str.split(' ')[0]
        
        # Se rollover for 0 (meia-noite), usa a data do calendario normalmente
        if rollover_hour == 0:
            return dt.strftime('%Y-%m-%d')
        
        # Se a hora da batalha for >= rollover, pertence ao "dia seguinte" do jogo
        # Ex: rollover=21, batalha 20/05 21:35 -> dia do jogo e 21/05
        if dt.hour >= rollover_hour:
            from datetime import timedelta
            return (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            return dt.strftime('%Y-%m-%d')
    except:
        return battle_time_str.split('T')[0] if 'T' in battle_time_str else battle_time_str.split(' ')[0]

def safe_int(val, default=0):
    try:
        if val is None:
            return default
        val_str = str(val).strip()
        if not val_str:
            return default
        return int(float(val_str))
    except (ValueError, TypeError):
        return default

class GitHubPagesHTMLGenerator:
    def __init__(self, db_path: str = None):
        self.src_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(os.path.dirname(self.src_dir))
        self.data_csv_dir = os.path.join(self.project_root, 'data', 'csv')

        # Inicializa o gerenciador de CSV (Sem SQL)
        self.csv_manager = CSVManager()
        self.prediction_engine = WarPredictionEngine()
        
        logger.info(f"Dashboard configurado em modo 100% CSV")
        self.base_url = "https://proxy.royaleapi.dev/v1"
        self.api_token = os.getenv("CR_API_TOKEN")
        self.headers = None
        if self.api_token:
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        
        player_tag_raw = os.getenv('CR_PLAYER_TAG', '#2QR292P').strip()
        self.player_tag = player_tag_raw if player_tag_raw.startswith('#') else f"#{player_tag_raw}"
        
        player_tag_sec_raw = os.getenv('CR_PLAYER_TAG_SEC', '').strip()
        if player_tag_sec_raw and player_tag_sec_raw.upper() != 'NONE':
            self.player_tag_sec = player_tag_sec_raw if player_tag_sec_raw.startswith('#') else f"#{player_tag_sec_raw}"
        else:
            self.player_tag_sec = None
            
        self.tracked_tags = [self.player_tag]
        if self.player_tag_sec:
            self.tracked_tags.append(self.player_tag_sec)
        
        logger.info(f"HTML Generator inicializado. Tags rastreadas: {self.tracked_tags}")
        if not self.player_tag_sec:
            logger.warning("AVISO: Tag secundaria (CR_PLAYER_TAG_SEC) nao detectada pelo gerador.")
            
        self.player_name_override = os.getenv('CR_PLAYER_NAME') or ''

        self.failed_tags = set()
        
        # Phase 2 Performance Optimization: Centralized Memory Cache
        logger.info("Starting performance-optimized data initialization")
        
        # Load all available battle data once from disk
        self.all_battles_cache = self._load_all_battles_from_csv(None)
        logger.info(f"Loaded {len(self.all_battles_cache)} records into master cache")

        # Organize battles by tag for fast lookup
        self.battles_by_tag = self._organize_battles_by_tag()
        
        # Battles cache now contains ALL tracked tags battles
        self.battles_cache = []
        for tag in self.tracked_tags:
            self.battles_cache.extend(self.battles_by_tag.get(tag, []))
            
        # FIX: Ensure global sorting across multiple tags so recent battles from any tag appear first
        self.battles_cache.sort(key=lambda x: x.get('_dt', datetime.min), reverse=True)
        
        self.clan_members_cache = self._load_clan_members_csv()
        self.players_cache = self._load_csv_as_list('players.csv')
        self.clan_decks_cache = self._load_csv_as_list('clan_decks.csv')
        self.rankings_history_cache = self._load_csv_as_list('rankings_history.csv')
        self.card_name_mapping = self._get_card_name_mapping()
        self.cards_master = self._load_cards_master_csv()
        self.upcoming_chests = self._load_upcoming_chests_json()
        logger.info("Data initialization completed successfully")
        
    def get_copy_deck_link(self, deck_list: List[str]) -> str:
        """Gera um link para copiar o deck para o jogo usando os IDs das cartas."""
        if not deck_list:
            return "#"
            
        ids = []
        for card_name in deck_list:
            card_name = card_name.strip()
            card_info = self.cards_master.get(card_name)
            if card_info and card_info.get('card_id'):
                ids.append(card_info['card_id'])
        
        if len(ids) < 8:
            return "#"
            
        return f"https://link.clashroyale.com/pt/?clashroyale://copyDeck?deck={';'.join(ids)}&l=Royals&tt=159000000"

    def _load_upcoming_chests_json(self, player_tag: str = None) -> List[Dict]:
        """Carrega o ciclo de baús do JSON oficial, tentando buscar por tag específica."""
        filename = 'upcoming_chests.json'
        if player_tag:
            clean_tag = player_tag.replace('#', '')
            tag_filename = f'upcoming_chests_{clean_tag}.json'
            if os.path.exists(os.path.join(self.data_csv_dir, tag_filename)):
                filename = tag_filename
                
        path = os.path.join(self.data_csv_dir, filename)
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('items', [])
        except Exception as e:
            logger.error(f"Erro ao ler {filename}: {e}")
            return []

    def _load_csv_as_list(self, filename: str) -> List[Dict]:
        """Auxiliar para carregar qualquer CSV da pasta oficial como lista de dicts"""
        path = os.path.join(self.data_csv_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Aviso: {path} não encontrado")
            return []
        try:
            with open(path, mode='r', encoding='utf-8-sig') as f:
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
            logger.info(f"Loaded {len(master)} card icons successfully.")
        except Exception as e:
            logger.error(f"Error reading cards_master_icons.csv: {e}")
        return master

    def _organize_battles_by_tag(self) -> Dict[str, List[Dict]]:
        """Organizes the master cache into a dictionary indexed by player tag."""
        organized = {}
        for b in self.all_battles_cache:
            tag = b.get('player_tag')
            if tag not in organized:
                organized[tag] = []
            organized[tag].append(b)
        
        # Sort each list by descending time
        for tag in organized:
            organized[tag].sort(key=lambda x: x.get('_dt', datetime.min), reverse=True)
            
        return organized

    def _load_all_battles_from_csv(self, player_tag: str = None) -> List[Dict]:
        """Loads all battles from the consolidated CSV files with robust detection."""
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
                # Tenta encodings em ordem de probabilidade (inclui UTF-16-LE sem BOM)
                data = []
                for encoding in ['utf-8-sig', 'utf-8', 'utf-16-le', 'latin1', 'cp1252']:
                    try:
                        with open(file_path, mode='r', encoding=encoding) as f:
                            first_line = f.readline()
                            f.seek(0)
                            if not first_line:
                                continue
                            
                            # Verifica se parece UTF-16 (caracteres nulos indicam UTF-16-LE sem BOM)
                            if '\x00' in first_line[:50] and encoding not in ['utf-16-le', 'utf-16']:
                                continue  # Skip this encoding, let UTF-16 handle it
                            
                            # Detecta delimitador
                            delimiter = ';' if ';' in first_line else ','
                            reader = csv.DictReader(f, delimiter=delimiter)
                            data = list(reader)
                            
                            # Valida: verifica se colunas não são gibberish (caracteres nulos)
                            if data and len(data[0]) > 1:
                                first_key = list(data[0].keys())[0] if data[0] else ''
                                first_key_len = len(first_key) if first_key else 0
                                if '\x00' in first_key or first_key_len > 50:
                                    data = []  # Invalid encoding, try next
                                    continue
                                logger.info(f"Arquivo {os.path.basename(file_path)} lido com sucesso ({encoding}, '{delimiter}').")
                                break
                    except Exception:
                        continue
                
                if not data:
                    logger.warning(f"Aviso: {file_path} está vazio ou ilegível.")
                    continue

                for row in data:
                    if not row:
                        continue
                    
                    # Filtro de player_tag (resiliente a nomes de colunas e espaços)
                    row_tag = (row.get('player_tag') or row.get('tag_jogador') or '').strip()
                    
                    # Normaliza data e hora
                            
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
                        'player_tag': row_tag,
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
            row_tag = (row.get('player_tag') or '').strip()
            if row_tag == player_tag:
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
            return "./torreDoRei.png"
        
        # Mapeamento para arquivos locais na pasta docs
        tower_mapping = {
            'Tower Princess': 'princesa-tropa-de-torre-clash-royale',
            'Cannoneer': 'canhoneiro-clash-royale-render-3d-cannonier',
            'Dagger Duchess': 'tudo-sobre-duquesa-das-adagas-clash-royale-knives-thrower',
            'Royal Chef': 'tudo-sobre-cozinheiro-real-clash-royale-royal-chef-FylAY7',
            'King Tower': 'torreDoRei',
            'King': 'torreDoRei'
        }
        
        slug = tower_mapping.get(tower_name)
        if not slug:
            # Tenta busca parcial caso o nome venha diferente da API
            t_name_lower = tower_name.lower()
            if 'dagger' in t_name_lower: slug = 'tudo-sobre-duquesa-das-adagas-clash-royale-knives-thrower'
            elif 'cannon' in t_name_lower: slug = 'canhoneiro-clash-royale-render-3d-cannonier'
            elif 'princess' in t_name_lower: slug = 'princesa-tropa-de-torre-clash-royale'
            elif 'chef' in t_name_lower: slug = 'tudo-sobre-cozinheiro-real-clash-royale-royal-chef-FylAY7'
            elif 'king' in t_name_lower: slug = 'torreDoRei'
            else: slug = 'torreDoRei'
            
        return f"./{slug}.png"

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

    def _get_deck_metrics(self, deck_str: str, leaked: float = 0, tower_level: int = 14, tower_name: str = 'Tower Princess') -> Dict:
        """Calcula media de elixir, ciclo de 4 cartas, nivel da torre e elixir vazado.
        
        Args:
            deck_str: String de cartas no formato 'Carta1 | Carta2 | ...' ou 'Carta1|Carta2|...'
            leaked: Elixir vazado pelo lado (jogador ou oponente) nessa batalha.
            tower_level: Nivel da torre do rei para calculo de HP.
            tower_name: Nome da tropa de torre.
        Returns:
            Dict com avg, cycle, leaked, level, hp, tower_name e tower_url.
        """
        if not deck_str or deck_str == 'N/D':
            return {
                'avg': 0, 'cycle': 0, 'leaked': leaked, 'level': tower_level, 
                'hp': self._get_tower_hp(tower_level), 'tower_name': tower_name,
                'tower_url': self.get_tower_image_path(tower_name)
            }
        
        cards = [c.strip() for c in deck_str.replace(' | ', '|').split('|')]
        costs = []
        for c in cards:
            # Tenta encontrar o custo no mapeamento; fallback para 3.5 (media global do jogo)
            cost = self.card_elixir_costs.get(c, 3.5)
            costs.append(cost)
        
        if not costs:
            return {
                'avg': 0, 'cycle': 0, 'leaked': leaked, 'level': tower_level, 
                'hp': self._get_tower_hp(tower_level), 'tower_name': tower_name,
                'tower_url': self.get_tower_image_path(tower_name)
            }
            
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
            'hp': self._get_tower_hp(safe_level),
            'tower_name': tower_name,
            'tower_url': self.get_tower_image_path(tower_name)
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
            level_raw = battle.get('nivel_torre_oponente') or battle.get('nivel_oponente') or battle.get('opponent_level') or battle.get('opp_tower_level', 0)
        else:
            leaked_raw = battle.get('elixir_vazado_jogador') or battle.get('player_leaked') or battle.get('elixir_leaked_player') or battle.get('player_leaked_elixir', 0)
            level_raw = battle.get('nivel_torre_jogador') or battle.get('player_level') or battle.get('player_tower_level', 0)
        
        # Sanitizacao: converte para tipos corretos, protege contra string vazia ou None
        try:
            leaked = float(leaked_raw) if leaked_raw and str(leaked_raw).strip() not in ('0', '', 'N/A') else 0.0
        except (ValueError, TypeError):
            leaked = 0.0
        try:
            # Garante que level_raw seja tratado como string para isdigit, mas converte para int
            s_level = str(level_raw).strip()
            tower_level = int(s_level) if s_level.isdigit() and int(s_level) > 0 and int(s_level) < 16 else 0
        except (ValueError, TypeError):
            tower_level = 0

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
            logger.warning(f"Skipping invalid player tag: {opponent_tag}")
            self.failed_tags.add(opponent_tag)
            return None

        clean_tag = opponent_tag.replace('#', '')
        url = f"{self.base_url}/players/%23{clean_tag}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 404:
                logger.warning(f"Player not found (404): {opponent_tag}")
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
            logger.error(f"Error fetching opponent data for {opponent_tag}: {e}")
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
                        logger.error(f"Error inserting battle: {e}")
                        continue
                
                conn.commit()
                conn.close()
            
            # Rate limiting
            time.sleep(1)
            
            return battles
        except requests.RequestException as e:
            logger.error(f"Error fetching opponent battles for {opponent_tag}: {e}")
            return None
    
    
    def safe_filename(self, name: str) -> str:
        """Convert member name to safe filename"""
        # Remove special characters and spaces
        safe_name = re.sub(r'[^\w\s-]', '', name)
        safe_name = re.sub(r'\s+', '_', safe_name)
        return safe_name.lower()
    
    
    def get_player_stats(self, player_tag: str = None) -> Optional[Dict]:
        """Get player statistics from CSV files com fallback para conta secundaria"""
        if not player_tag:
            player_tag = self.player_tag
            
        player_row = self._load_players_csv(player_tag)
        
        # Fallback: se nao encontrar em players.csv mas tiver batalhas, cria stats minimo
        battles = self.battles_by_tag.get(player_tag, [])
        if not player_row and battles:
            logger.warning(f"Jogador {player_tag} nao em players.csv, usando fallback com {len(battles)} batalhas")
            player_row = {
                'player_tag': player_tag,
                'name': f'Conta {player_tag}',
                'trophies': '0',
                'best_trophies': '0',
                'level': '0',
                'clan_tag': '',
                'clan_name': '',
                'last_updated': datetime.now(UTC).isoformat()
            }
        
        if not player_row:
            logger.warning(f"Jogador {player_tag} nao encontrado em players.csv e sem batalhas")
            return None
        
        player_tag = player_row.get('player_tag')
        
        # Get battle stats from CSV cache organized by tag
        battles = self.battles_by_tag.get(player_tag, [])
        
        total_battles = len(battles)
        wins = sum(1 for b in battles if b['result'] == 'victory')
        losses = sum(1 for b in battles if b['result'] == 'defeat')
        draws = sum(1 for b in battles if b['result'] == 'draw')
        total_trophy_change = sum(b.get('trophy_change', 0) for b in battles)
        last_battle = battles[0]['battle_time'] if battles else None
        first_battle = battles[-1]['battle_time'] if battles else None
        
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
        battles = self.battles_cache
        if player_tag:
            battles = self.battles_by_tag.get(player_tag, [])
            
        if not battles:
            return []
            
        deck_stats = {}
        for b in battles:
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

    def get_lethal_opponent_decks(self, limit: int = 10, player_tag: str = None) -> List[Dict]:
        """Analisa quais decks de oponentes causam mais derrotas ao usuario usando agrupamento canonico."""
        battles = self.battles_cache
        if player_tag:
            battles = self.battles_by_tag.get(player_tag, [])
        
        # Fallback para all_battles_cache filtrado por tag, se battles_by_tag estiver vazio
        if not battles and player_tag:
            battles = [b for b in self.all_battles_cache if b.get('player_tag') == player_tag]
            
        if not battles: return []
        
        lethal_decks = {}
        for b in battles:
            if b.get('result') != 'defeat': continue
            
            # Suporta tanto 'opp_deck' (legado) quanto 'opponent_deck_cards' (CSV atual)
            opp_deck_raw = b.get('opponent_deck_cards') or b.get('opp_deck')
            if not opp_deck_raw or str(opp_deck_raw).strip() in ('N/D', 'N/A', '', 'nan'): continue
            
            # Usa chave canonica para agrupar decks identicos em ordens diferentes
            deck_key = self._get_canonical_deck(opp_deck_raw)
            
            if deck_key not in lethal_decks:
                lethal_decks[deck_key] = {
                    'deck': deck_key,
                    'losses_caused': 0,
                    'opponents': set(),
                    'last_encounter': b.get('battle_time', ''),
                    'cards': [c.strip() for c in deck_key.split('|')]
                }
            
            lethal_decks[deck_key]['losses_caused'] += 1
            lethal_decks[deck_key]['opponents'].add(b.get('opponent_name', 'Desconhecido'))
            bt = b.get('battle_time', '')
            if bt and bt > lethal_decks[deck_key]['last_encounter']:
                lethal_decks[deck_key]['last_encounter'] = bt
                
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
        if player_tag:
            return self.battles_by_tag.get(player_tag, [])[:limit]
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
        """Get daily wins/losses aggregation from CSV files com virada de dia correta por conta"""
        if not player_tag:
            player_tag = self.player_tag
        
        # Determina o horario de virada baseado na conta
        rollover_hour = DAY_ROLLOVER_HOURS['primary']  # Padrao: 00:00
        if player_tag == self.player_tag_sec:
            rollover_hour = DAY_ROLLOVER_HOURS['secondary']  # Secundaria: 21:00
            
        # Use cached battles organized by tag
        battles = self.battles_by_tag.get(player_tag, [])
        
        # Aggregate by date
        from datetime import datetime, timedelta
        end_date = _get_brt_now()
        
        # Correcao de virada de dia para o Histograma (Secundaria vira as 21h00)
        if rollover_hour > 0 and end_date.hour >= rollover_hour:
            end_date = end_date + timedelta(days=1)
            
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
            
            # Usa a funcao auxiliar para calcular a data correta com base no rollover
            b_date = _get_battle_date(b_time, rollover_hour)
            
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
    
    def generate_daily_histogram_html(self, daily_stats: List[Dict], css_class: str = "", include_legend: bool = True, player_tag: str = "") -> str:
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
                win_height = max((wins / total) * scale_factor, 16 if wins > 0 else 0)
                loss_height = max((losses / total) * scale_factor, 16 if losses > 0 else 0)
                draw_height = max((draws / total) * scale_factor, 16 if draws > 0 else 0)
            
            # Create tooltip
            tooltip = f"{date}: {wins}W/{losses}L/{draws}D" if total > 0 else f"{date}: No battles"
            
            histogram_html += f'''
                <div class="histogram-bar" title="{tooltip}" onclick="showDayDetailModal('{player_tag}', '{date}')" style="cursor: pointer;">
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

        # Aba 1: Meus Decks da Semana - le CSVs diarios com filtro por conta
        weekly_data = self.get_weekly_decks_from_csv(player_tag=player_tag)
        weekly_decks_html = self.generate_weekly_decks_html(weekly_data)

        # Aba 2: Oponentes Repetidos - usa estatisticas consolidadas do cache CSV com deduplicacao
        csv_repeated = self.get_repeated_opponents_from_csv(player_tag=player_tag)
        repeated_opponents_html = self.generate_repeated_opponents_html(csv_repeated)
        
        # Aba 4: Decks Mais Vencedores (Global/Clã)
        winning_data = self.get_top_winning_decks_weekly()
        winning_decks_html = self.generate_winning_decks_html(winning_data)

        # Prefixo único por conta para evitar conflitos de IDs no DOM entre Conta Principal e Secundária
        p_prefix = f"acc-{player_tag.replace('#', '')}" if player_tag else "acc-main"

        # Inteligência de tab ativa: se não houver oponentes repetidos reais (> 1 batalha) no VS Stage,
        # ativamos "Meus Decks" por padrão para deixar a experiência mais compacta e rica na conta secundária
        has_real_repeated = any(o.get('total_battles', 0) > 1 for o in csv_repeated)
        default_tab = "weekly-decks" if not has_real_repeated and weekly_data else "repeated-opponents"
        
        active_rep = "active" if default_tab == "repeated-opponents" else ""
        active_dec = "active" if default_tab == "weekly-decks" else ""

        return f"""
        <div class="cr-inner-tabs-container">
            <div class="cr-account-tabs" style="margin-bottom: 20px; background: rgba(255,255,255,0.02);">
                <button class="cr-tab {active_rep}" onclick="switchInnerTab(event, '{p_prefix}-repeated-opponents')">VS Stage</button>
                <button class="cr-tab {active_dec}" onclick="switchInnerTab(event, '{p_prefix}-weekly-decks')">Meus Decks</button>
                <button class="cr-tab" onclick="switchInnerTab(event, '{p_prefix}-lethal-decks')">Decks Letais</button>
                <button class="cr-tab" onclick="switchInnerTab(event, '{p_prefix}-winning-decks')">Top Global</button>
            </div>

            <div id="{p_prefix}-repeated-opponents" class="cr-tab-content {active_rep}">
                {repeated_opponents_html if repeated_opponents_html else '<p style="padding: 40px; text-align: center; color: #64748b;">Nenhum oponente repetido encontrado para esta conta.</p>'}
            </div>

            <div id="{p_prefix}-weekly-decks" class="cr-tab-content {active_dec}">
                {weekly_decks_html}
            </div>
            
            <div id="{p_prefix}-lethal-decks" class="cr-tab-content">
                {lethal_decks_html if lethal_decks_html else '<p style="padding: 40px; text-align: center; color: #64748b;">Dados insuficientes para análise de decks letais.</p>'}
            </div>
            
            <div id="{p_prefix}-winning-decks" class="cr-tab-content">
                {winning_decks_html}
            </div>
        </div>
        """

    def load_all_data_rows(self, player_tag: str = None) -> List[Dict]:
        """Processes and unifies data from memory cache. Fast, no disk I/O."""
        # Use filtered cache if tag is provided, else use master cache
        target_list = self.battles_by_tag.get(player_tag, []) if player_tag else self.all_battles_cache
        
        if not target_list:
            return []

        all_data = []
        for b in target_list:
            # Maintain all original fields
            row = b.copy()
            
            # Normalization of fields for cross-compatibility
            battle_time = b.get('battle_time', '')
            dt = b.get('_dt') or self._parse_dt(battle_time)
            result = (b.get('result') or '').strip().lower()
            opponent_tag = b.get('opponent_tag', '')
            player_deck = b.get('deck_cards', '')
            opponent_deck = b.get('opponent_deck_cards', '')

            row.update({
                'battle_time': battle_time,
                'dt': dt,
                'opponent_name': b.get('opponent_name', 'Opponent'),
                'opponent_tag': opponent_tag,
                'tag_oponente': opponent_tag,
                'result': result,
                'resultado': result,
                'deck_cards': player_deck,
                'deck_jogador': player_deck,
                'opponent_deck_cards': opponent_deck,
                'deck_oponente': opponent_deck,
                'opponent_clan_name': b.get('opponent_clan_name', ''),
                'nome_oponente': b.get('opponent_name', 'Opponent'),
                'coroas_jogador': b.get('coroas_jogador') if b.get('coroas_jogador') is not None else b.get('crowns', 0),
                'coroas_oponente': b.get('coroas_oponente') if b.get('coroas_oponente') is not None else b.get('opponent_crowns', 0),
                'modo_jogo': b.get('modo_jogo') or b.get('game_mode', 'Unknown'),
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

    def get_weekly_decks_from_csv(self, player_tag: str = None) -> List[Dict]:
        """Consolida os 10 melhores decks dos últimos 7 dias usando todas as fontes."""
        from datetime import datetime, timedelta
        
        # Filtragem por player_tag se fornecida
        if player_tag:
            all_rows = self.battles_by_tag.get(player_tag, [])
        else:
            all_rows = self.load_all_data_rows()
            
        if not all_rows: return []
            
        today = _get_brt_now()
        seven_days_ago = today - timedelta(days=7)
        deck_stats = {}

        for row in all_rows:
            # Sincronização de campos para diferentes fontes
            battle_time = row.get('battle_time') or row.get('dt_batalha') or ''
            dt = row.get('dt') or self._parse_dt(battle_time)
            
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

        # Fallback inteligente: se houver poucos decks recentes (menos de 4), permitimos exibir
        # decks históricos adicionais do CSV para preencher o grid de forma compacta e premium
        recent_decks_count = sum(1 for d in deck_stats.values() if d['recent_total'] > 0)
        use_fallback = (recent_decks_count < 4)
        
        final_list = []
        for d in deck_stats.values():
            if not use_fallback and d['recent_total'] == 0:
                continue
            
            # Ordenar batalhas do deck por data
            d['battles'].sort(key=lambda x: x['dt_obj'], reverse=True)
            d['win_rate'] = round((d['wins'] / d['total'] * 100), 1) if d['total'] > 0 else 0
            final_list.append(d)
            
        # ORDENAÇÃO: Decks usados RECENTEMENTE e com maior volume de batalhas no topo
        final_list.sort(key=lambda x: (x['recent_total'], x['total'], x['win_rate']), reverse=True)
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
            
        today = _get_brt_now()
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
                d['battles'].sort(key=lambda x: self._parse_dt(x['battle_time']) or datetime.min, reverse=True)
                final_list.append(d)
        final_list.sort(key=lambda x: (x['win_rate'], x['total']), reverse=True)
        return final_list[:10]

    def generate_weekly_decks_html(self, weekly_data: List[Dict]) -> str:
        """Gera HTML da aba 'Meus Decks' com timeline interativa e layout Premium v2 Compact."""
        if not weekly_data: return '<div class="cr-empty-state">Nenhum dado encontrado para os últimos 7 dias.</div>'
        import json
        
        player_name = self.player_name_override or next((p.get('name', 'Jogador') for p in self.players_cache if p.get('player_tag') == self.player_tag), 'Jogador')
        player_clan = next((p.get('clan_name', '') for p in self.players_cache if p.get('player_tag') == self.player_tag), '')

        # Limitar a largura do container principal dos decks para que fiquem alinhados e mais compactos
        html = '<div class="cr-decks-list" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px;">'
        for i, deck in enumerate(weekly_data, 1):
            total = deck['total']
            win_rate = deck['win_rate']
            wins_pct = round((deck['wins']/total*100), 1) if total > 0 else 0
            losses_pct = round((deck['losses']/total*100), 1) if total > 0 else 0
            draws_pct = round(max(0, 100 - wins_pct - losses_pct), 1)
            
            # Primeira batalha para o preview inicial e métricas do deck
            first_b = deck['battles'][0] if deck['battles'] else {}
            my_m_f = self._get_battle_deck_metrics(deck['deck_cards'], first_b, is_opponent=False)
            
            # Timeline HTML (Bolinhas do Histórico com popover interativo)
            timeline_h = '<div style="margin-top: 12px; padding: 10px; background: rgba(15,23,42,0.3); border-radius: 10px; border: 1px solid rgba(255,255,255,0.03);">'
            timeline_h += '<div style="display: flex; gap: 6px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin;">'
            
            for idx, b in enumerate(deck['battles'][:12]):
                res = b['resultado'].lower() if b.get('resultado') else 'unknown'
                res_char = 'V' if any(x in res for x in ['vitoria', 'victory', 'vitória']) else ('D' if any(x in res for x in ['derrota', 'defeat']) else 'E')
                res_color = '#48bb78' if res_char == 'V' else ('#f56565' if res_char == 'D' else '#718096')
                
                # Formata data e hora
                dt_obj = b.get('dt_obj')
                dt_str = dt_obj.strftime('%d/%m') if dt_obj else '--/--'
                time_str = dt_obj.strftime('%H:%M') if dt_obj else '--:--'
                
                opp_name = b.get('nome_oponente', 'Oponente')
                p_crowns = b.get('coroas_jogador', 0)
                o_crowns = b.get('coroas_oponente', 0)
                modo_jogo = b.get('modo_jogo', 'Batalha')
                
                # Mini deck do oponente
                opp_deck_str = b.get('opponent_deck_cards') or b.get('deck_oponente') or ''
                mini_cards_html = ""
                if opp_deck_str and opp_deck_str != 'N/D':
                    opp_cards = [c.split('|')[0].strip() for c in opp_deck_str.replace(' | ', '|').split('|') if c.strip()][:8]
                    for card_name in opp_cards:
                        card_url = self.get_card_image_path(card_name)
                        mini_cards_html += f'<img src="{card_url}" style="width: 20px; height: 24px; object-fit: contain; border-radius: 4px;" title="{card_name}">'
                else:
                    mini_cards_html = '<span style="font-size: 0.8em; color: #64748b;">Deck N/D</span>'

                timeline_h += f'''
                <div class="cr-history-dot-wrap" style="position: relative; display: inline-block;">
                    <div style="flex-shrink: 0; padding: 4px 6px; background: rgba(0,0,0,0.3); border-radius: 6px; border: 1px solid {res_color}40; text-align: center; cursor: pointer; min-width: 32px;">
                        <div style="font-size: 0.7em; font-weight: 900; color: {res_color};">{res_char}</div>
                        <div style="font-size: 0.5em; color: rgba(255,255,255,0.4);">{time_str}</div>
                    </div>
                    
                    <!-- Popover flutuante premium -->
                    <div class="cr-dot-popover" style="display: none; position: absolute; bottom: 125%; left: 50%; transform: translateX(-50%); background: #0f172a; border: 1px solid rgba(255,255,255,0.15); border-radius: 12px; padding: 10px; z-index: 1000; width: 190px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); pointer-events: none; text-align: left;">
                        <div style="font-size: 0.75em; font-weight: 900; color: #fff; margin-bottom: 4px; display: flex; justify-content: space-between;">
                            <span>{opp_name[:12]}</span>
                            <span style="color: {res_color}; font-weight: 950;">{p_crowns} - {o_crowns}</span>
                        </div>
                        <div style="font-size: 0.55em; color: #94a3b8; margin-bottom: 6px; text-transform: uppercase;">📅 {dt_str} 🕒 {time_str} • {modo_jogo[:12]}</div>
                        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px;">
                            {mini_cards_html}
                        </div>
                    </div>
                </div>'''
            
            timeline_h += '</div></div>'

            wr_c = '#48bb78' if win_rate >= 60 else ('#f56565' if win_rate <= 40 else '#718096')
            
            html += f'''
            <div class="cr-deck-card cr-glass-premium" style="margin-bottom: 12px; overflow: visible; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; background: rgba(15,23,42,0.4);">
                <!-- Header Compacto -->
                <div class="cr-deck-header" style="padding: 10px 15px; background: rgba(0,0,0,0.4); border-bottom: 1px solid rgba(255,255,255,0.05); border-radius: 16px 16px 0 0;">
                    <div style="display: flex; align-items: center; gap: 10px; width: 100%; flex-wrap: wrap;">
                        <span style="background:#4299e1; color: #fff; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-weight: 900; font-size: 0.75em;">#{i}</span>
                        <span style="color: #fff; font-size: 0.85em; font-weight: 700;">WR: <span style="color: {wr_c}; font-weight:900;">{win_rate}%</span> <span style="opacity: 0.5; font-size: 0.8em;">({deck['recent_total']} partidas)</span></span>
                        <span style="margin-left: auto; background:{wr_c}22; border: 1px solid {wr_c}33; color: {wr_c}; font-weight: 900; font-size: 0.7em; padding: 2px 8px; border-radius: 6px;">{total} TOTAL</span>
                    </div>
                </div>
                
                <!-- Barra de Progresso Horizontal -->
                <div style="height: 3px; background: rgba(0,0,0,0.3); display: flex;">
                    <div style="width:{wins_pct}%; background: #48bb78;"></div>
                    <div style="width:{draws_pct}%; background: #718096;"></div>
                    <div style="width:{losses_pct}%; background: #f56565;"></div>
                </div>

                <!-- Conteúdo Compacto -->
                <div style="padding: 12px !important; background: transparent;">
                    <!-- Grid 4x2 do Deck do Jogador -->
                    <div style="width: 100%; max-width: 320px; margin: 0 auto 10px auto;">
                        {self._generate_deck_grid_html_simple(deck['deck_cards'], self.get_copy_deck_link([c.split('|')[0] for c in deck['deck_cards'].split('|') if c]))}
                    </div>
                    
                    <!-- Badges de Elixir Médio e Ciclo 4 -->
                    <div style="display: flex; gap: 8px; justify-content: center; margin-bottom: 8px;">
                        <div class="cr-metric-inline" title="Elixir Médio" style="display: flex; align-items: center; gap: 5px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.75em;">
                            <img src="https://cdn.royaleapi.com/static/img/ui/elixir.png" style="width: 14px; height: 14px; filter: drop-shadow(0 0 5px rgba(168, 85, 247, 0.4));">
                            <span style="font-weight: 900; color: #fff; font-family: 'Krona One', sans-serif;">{my_m_f['avg']}</span>
                        </div>
                        <div class="cr-metric-inline" title="Ciclo 4" style="display: flex; align-items: center; gap: 5px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.75em;">
                            <img src="./ciclo4.png" style="width: 14px; height: 14px; object-fit: contain; filter: drop-shadow(0 0 5px rgba(59, 130, 246, 0.4));">
                            <span style="font-weight: 900; color: #fff; font-family: 'Krona One', sans-serif;">{my_m_f['cycle']}</span>
                        </div>
                    </div>
                    
                    <!-- Linha de Dots do Histórico -->
                    {timeline_h}
                </div>
            </div>
            '''
        
        html += '</div>'
        return html

    def generate_winning_decks_html(self, winning_data: List[Dict]) -> str:
        """Gera HTML para a aba de melhores decks da semana (Meta/Global) no padrao Premium v2 similar a Meus Decks."""
        if not winning_data: return '<div class="cr-empty-state">Dados globais insuficientes para o Top Vencedores.</div>'
        
        # Usar grid de colunas para telas médias/grandes
        html = '<div class="cr-decks-list" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px;">'
        
        for i, deck in enumerate(winning_data, 1):
            total = deck['total']
            win_rate = deck['win_rate']
            deck_cards = deck['deck_cards']
            
            source_label = deck.get('source', 'Dados do Clã')
            is_global = source_label == 'Global Meta'
            game_mode = "Ranked" if is_global else "Guerra/Desafio"
            
            metrics = self._get_deck_metrics(deck_cards)
            wr_c = '#48bb78' if win_rate >= 55 else ('#4299e1' if win_rate >= 50 else '#f87171')
            
            cards_for_copy = [c.split('|')[0] for c in deck_cards.split('|') if c]
            copy_link = self.get_copy_deck_link(cards_for_copy)
            
            html += f'''
            <div class="cr-deck-card cr-glass-premium" style="margin-bottom: 12px; overflow: visible; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; background: rgba(15,23,42,0.4);">
                <!-- Header Compacto -->
                <div class="cr-deck-header" style="padding: 10px 15px; background: rgba(0,0,0,0.4); border-bottom: 1px solid rgba(255,255,255,0.05); border-radius: 16px 16px 0 0;">
                    <div style="display: flex; align-items: center; gap: 10px; width: 100%; flex-wrap: wrap;">
                        <span style="background:{wr_c}; color: #fff; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-weight: 900; font-size: 0.75em; font-family: 'Krona One', sans-serif;">#{i}</span>
                        <span style="color: #fff; font-size: 0.8em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">{source_label}</span>
                        <span style="margin-left: auto; background:{wr_c}22; border: 1px solid {wr_c}33; color: {wr_c}; font-weight: 950; font-size: 0.8em; padding: 2px 8px; border-radius: 6px; font-family: 'Krona One', sans-serif;">{win_rate}% WR</span>
                    </div>
                </div>
                
                <!-- Sub-header com detalhes de partidas -->
                <div style="padding: 6px 12px; background: rgba(0,0,0,0.2); border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 0.7em; color: rgba(255,255,255,0.5); font-weight: 800; display: flex; justify-content: space-between;">
                    <span>{game_mode}</span>
                    <span>{total} partidas</span>
                </div>

                <!-- Conteúdo Compacto -->
                <div style="padding: 12px !important; background: transparent;">
                    <!-- Grid 4x2 do Deck -->
                    <div style="width: 100%; max-width: 320px; margin: 0 auto 10px auto;">
                        {self._generate_deck_grid_html_simple(deck_cards, copy_link)}
                    </div>
                    
                    <!-- Badges de Elixir Médio e Ciclo 4 -->
                    <div style="display: flex; gap: 8px; justify-content: center; margin-bottom: 4px;">
                        <div class="cr-metric-inline" title="Elixir Médio" style="display: flex; align-items: center; gap: 5px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.75em;">
                            <img src="https://cdn.royaleapi.com/static/img/ui/elixir.png" style="width: 14px; height: 14px; filter: drop-shadow(0 0 5px rgba(168, 85, 247, 0.4));">
                            <span style="font-weight: 900; color: #f59e0b;">{metrics['avg']}</span>
                        </div>
                        <div class="cr-metric-inline" title="Custo de Ciclo (4 cartas)" style="display: flex; align-items: center; gap: 5px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.75em;">
                            <img src="./ciclo4.png" style="width: 14px; height: 14px; filter: drop-shadow(0 0 5px rgba(56, 189, 248, 0.4));">
                            <span style="font-weight: 900; color: #38bdf8;">{metrics['cycle']}</span>
                        </div>
                    </div>
                </div>
            </div>
            '''
            
        return html + '</div>'

    def get_repeated_opponents_from_csv(self, player_tag: str = None) -> List[Dict]:
        """Agrupa oponentes repetidos com deduplicação rigorosa e sincronização de chaves para o HTML."""
        if player_tag:
            all_rows = self.battles_by_tag.get(player_tag, [])
        else:
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
            d_str = dt.strftime('%d/%m')
            t_str = dt.strftime('%H:%M')
                
            opp_stats[tag]['stats'].append({
                'resultado': res, 
                'result': res,
                'data_str': d_display,
                'battle_time': d_display,
                'data': d_display,
                'date_str': d_str,
                'time_str': t_str,
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
        # Apenas listar oponentes com pelo menos 2 batalhas (oponentes repetidos reais)
        # Evita exibir oponentes de batalhas únicas no VS Stage, o que poluía visualmente
        min_battles_required = 2
        
        repeated = []
        for o in opp_stats.values():
            if o['total_battles'] >= min_battles_required:
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

        repeated.sort(key=lambda x: (x['total_battles'] > 1, x['last_battle_dt']), reverse=True)
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

        # Coletar as batalhas de todas as contas em formato JSON limpo
        battles_json_data = {}
        for tag in self.tracked_tags:
            tag_battles = self.battles_by_tag.get(tag, [])
            mapped_battles = []
            for b in tag_battles:
                # Calcular a data correta de batalha considerando o rollover da respectiva conta
                rollover_hour = DAY_ROLLOVER_HOURS['primary']
                if tag == self.player_tag_sec:
                    rollover_hour = DAY_ROLLOVER_HOURS['secondary']
                b_date = _get_battle_date(b.get('battle_time', ''), rollover_hour)
                
                # Extrair metricas reais dos decks e torres
                my_m = self._get_battle_deck_metrics(b.get('deck_cards', ''), b, is_opponent=False)
                opp_m = self._get_battle_deck_metrics(b.get('opponent_deck_cards', ''), b, is_opponent=True)
                
                mapped_battles.append({
                    'b_date': b_date,
                    'result': b.get('result', ''),
                    'opponent_name': b.get('opponent_name', ''),
                    'crowns': int(b.get('crowns', 0) or 0),
                    'opponent_crowns': int(b.get('opponent_crowns', 0) or 0),
                    'elixir_p': float(b.get('elixir_vazado_jogador') or 0.0),
                    'elixir_o': float(b.get('elixir_vazado_oponente') or 0.0),
                    'game_mode': b.get('game_mode', 'Batalha'),
                    'arena_name': b.get('arena_name', 'Arena'),
                    'trophy_change': int(b.get('trophy_change', 0) or 0),
                    'my_deck': b.get('deck_cards', ''),
                    'opp_deck': b.get('opponent_deck_cards', ''),
                    'opponent_tag': b.get('opponent_tag', ''),
                    'opp_level': int(b.get('opponent_level') or 14),
                    'p_tower_url': my_m.get('tower_url', ''),
                    'o_tower_url': opp_m.get('tower_url', ''),
                    'p_hp': my_m.get('hp', '4820'),
                    'o_hp': opp_m.get('hp', '4820'),
                })
            battles_json_data[tag] = mapped_battles
        
        battles_json = json.dumps(battles_json_data, ensure_ascii=False)
        card_map_json = json.dumps(card_urls)

        return """
        <script>
        const CARD_MAP = """ + card_map_json + """;
        window.PLAYER_BATTLES_DATA = """ + battles_json + """;

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
            
            const copyHtml = deckLink ? `<button type="button" onclick="copyDeckLink(event, this, '${deckLink}')" class="cr-copy-deck-btn" title="Copiar Deck">📋</button>` : '';
            
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



        function updateOpponentView(oppId, element) {
            try {
                const dataRaw = element.getAttribute('data-battle');
                const data = JSON.parse(dataRaw);
                
                // Update date and time (simples: subir até cr-deck-card)
                const deckCard = element.closest('.cr-deck-card');
                const dateEl = deckCard ? deckCard.querySelector(`#date-${oppId}`) : null;
                const timeEl = deckCard ? deckCard.querySelector(`#time-${oppId}`) : null;
                
                if (dateEl) dateEl.innerHTML = `<i class="far fa-calendar-alt"></i> ${data.date || '--/--'}`;
                if (timeEl) timeEl.innerHTML = `<i class="far fa-clock"></i> ${data.time || '--:--'}`;

                // Support for modernized VS Stage date displays
                const vsContainer = document.getElementById(`vs-stage-${oppId}`);
                if (vsContainer) {
                    const dateDisplay = vsContainer.querySelector('.cr-battle-date-p');
                    const metaDateDisplay = vsContainer.querySelector('.match-date');
                    const dateContent = `${data.date || ''} ${data.time || ''}`.trim() || 'Data desconhecida';
                    
                    if (dateDisplay) dateDisplay.innerHTML = `<i class="far fa-calendar-alt"></i> ${dateContent}`;
                    if (metaDateDisplay) metaDateDisplay.innerHTML = `<i class="far fa-calendar-alt"></i> ${dateContent}`;
                }

                console.log(`[RoyaleAnalytics] Updating Opponent ${oppId} details...`, data);
                
                // Update scores and mode
                const scoreEl = document.getElementById(`score-${oppId}`);
                const modeEl = document.getElementById(`mode-${oppId}`);
                if (scoreEl) scoreEl.innerText = `${data.crowns || 0} - ${data.o_crowns || 0}`;
                if (modeEl) modeEl.innerText = data.mode || 'Batalha';
                
                // Update Metadata Row
                const arenaEl = document.getElementById(`arena-${oppId}`);
                const trophyEl = document.getElementById(`trophy-change-${oppId}`);
                const rankPEl = document.getElementById(`rank-p-${oppId}`);
                const rankOEl = document.getElementById(`rank-o-${oppId}`);

                if (arenaEl) arenaEl.innerHTML = `<i class="fas fa-map-marker-alt" style="color: var(--primary); opacity: 0.7;"></i> ${data.arena || 'Arena'}`;
                if (trophyEl) {
                    const val = parseInt(data.trophy_change || 0);
                    const color = val > 0 ? '#48bb78' : (val < 0 ? '#f56565' : '#94a3b8');
                    const sign = val > 0 ? '+' : '';
                    trophyEl.innerText = `${sign}${val} Troféus`;
                    trophyEl.style.color = color;
                }
                if (rankPEl) rankPEl.innerHTML = `<i class="fas fa-globe" style="margin-right: 4px; opacity: 0.7;"></i> Rank P: ${data.rank_p || 'N/A'}`;
                if (rankOEl) rankOEl.innerHTML = `<i class="fas fa-globe" style="margin-right: 4px; opacity: 0.7;"></i> Rank O: ${data.rank_o || 'N/A'}`;

                // Update names and tags
                const pNameEl = document.getElementById(`p-name-${oppId}`);
                const oNameEl = document.getElementById(`o-name-${oppId}`);
                const pTagEl = document.getElementById(`p-tag-${oppId}`);
                const oTagEl = document.getElementById(`o-tag-${oppId}`);
                if (pNameEl && data.p_name) pNameEl.innerText = data.p_name;
                if (oNameEl && data.o_name) oNameEl.innerText = data.o_name;
                if (pTagEl && data.p_tag) pTagEl.innerText = `#${data.p_tag}`;
                if (oTagEl && data.o_tag) oTagEl.innerText = `#${data.o_tag}`;
                
                const pClanEl = document.getElementById(`p-clan-${oppId}`);
                const oClanEl = document.getElementById(`o-clan-${oppId}`);
                if (pClanEl) pClanEl.innerText = data.p_clan || '';
                if (oClanEl) oClanEl.innerText = data.o_clan || '';
                
                // Update metrics
                const pMetricsEl = document.getElementById(`player-metrics-${oppId}`);
                const oMetricsEl = document.getElementById(`opp-metrics-${oppId}`);
                if (pMetricsEl) pMetricsEl.innerHTML = data.p_metrics;
                if (oMetricsEl) oMetricsEl.innerHTML = data.o_metrics;

                // Update towers
                const pTowerImg = document.getElementById(`p-tower-img-${oppId}`);
                const oTowerImg = document.getElementById(`o-tower-img-${oppId}`);
                const pHpEl = document.getElementById(`p-tower-hp-${oppId}`);
                const oHpEl = document.getElementById(`o-tower-hp-${oppId}`);
                
                if (pTowerImg) {
                    pTowerImg.src = data.p_tower_url || pTowerImg.src;
                    pTowerImg.style.opacity = '0.5';
                    setTimeout(() => pTowerImg.style.opacity = '1', 50);
                }
                if (oTowerImg) {
                    oTowerImg.src = data.o_tower_url || oTowerImg.src;
                    oTowerImg.style.transform = 'scaleX(-1)';
                    oTowerImg.style.opacity = '0.5';
                    setTimeout(() => oTowerImg.style.opacity = '1', 50);
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
                    transform-origin: bottom center !important;
                    will-change: transform;
                    image-rendering: auto;
                }
                .cr-tower-zoom:hover {
                    transform: scale(1.15) translateY(-8px) !important;
                    filter: brightness(1.2) drop-shadow(0 12px 24px rgba(0,0,0,0.5)) !important;
                    z-index: 100 !important;
                }
                .cr-tower-zoom.cr-tower-mirrored {
                    transform: scaleX(-1) !important;
                }
                .cr-tower-zoom.cr-tower-mirrored:hover {
                    transform: scale(1.15) scaleX(-1) translateY(-8px) !important;
                    filter: brightness(1.2) drop-shadow(0 12px 24px rgba(0,0,0,0.5)) !important;
                    z-index: 100 !important;
                }
                .cr-battle-preview-v2 div {
                    white-space: nowrap !important;
                }
                .cr-opp-card-row {
                    padding-bottom: 5px !important;
                }
            `;
            document.head.appendChild(style);
        });

        let currentDayBattles = [];
        let currentDayPlayerTag = '';

        function showDayDetailModal(playerTag, dateStr) {
            console.log("[RoyaleAnalytics] showDayDetailModal called for tag:", playerTag, "date:", dateStr);

            const battles = window.PLAYER_BATTLES_DATA[playerTag] || [];
            const dayBattles = battles.filter(b => b.b_date === dateStr);

            if (dayBattles.length === 0) {
                console.warn("[RoyaleAnalytics] No battles found for date:", dateStr);
                return;
            }

            currentDayBattles = dayBattles;
            currentDayPlayerTag = playerTag;

            const totalBattles = dayBattles.length;
            let wins = 0;
            let losses = 0;
            let draws = 0;
            let totalCrowns = 0;
            let totalElixirLeaked = 0.0;

            let maxConseqWins = 0;
            let currentConseqWins = 0;

            let worstLossDiff = -999;
            let worstEnemyDecks = "Nenhum";

            const cronoBattles = [...dayBattles].reverse();

            cronoBattles.forEach(b => {
                const res = b.result.toLowerCase();
                if (res === 'victory' || res === 'win') {
                    wins++;
                    currentConseqWins++;
                    if (currentConseqWins > maxConseqWins) {
                        maxConseqWins = currentConseqWins;
                    }
                } else {
                    currentConseqWins = 0;
                    if (res === 'defeat' || res === 'loss') {
                        losses++;
                    } else {
                        draws++;
                    }
                }

                totalCrowns += b.crowns;
                totalElixirLeaked += b.elixir_p;

                if (res === 'defeat' || res === 'loss') {
                    const diff = b.opponent_crowns - b.crowns;
                    if (diff > worstLossDiff) {
                        worstLossDiff = diff;
                        const cards = (b.opp_deck || '').split('|').map(c => c.trim()).filter(Boolean);
                        worstEnemyDecks = cards.slice(0, 4).join(' | ') + (cards.length > 4 ? ' ...' : '');
                    }
                }
            });

            const winRate = totalBattles > 0 ? ((wins / totalBattles) * 100).toFixed(2) : "0.00";
            const avgCrowns = totalBattles > 0 ? (totalCrowns / totalBattles).toFixed(1) : "0.0";
            const avgElixir = totalBattles > 0 ? (totalElixirLeaked / totalBattles).toFixed(1) : "0.0";

            let gridHtml = '';
            dayBattles.forEach((b, idx) => {
                const resClass = b.result.toLowerCase() === 'victory' || b.result.toLowerCase() === 'win' ? 'win' :
                    (b.result.toLowerCase() === 'defeat' || b.result.toLowerCase() === 'loss' ? 'loss' : 'draw');

                const mode = b.game_mode || 'Batalha';
                let icon = '\\u{1F6E1}\\u{FE0F}';
                if (mode.includes('Duelo') || mode.includes('Duel')) icon = '\u26A1';
                else if (mode.includes('Barco') || mode.includes('Boat')) icon = '\\u{1F6A3}';
                else if (mode.includes('Guerra') || mode.includes('War')) icon = '\u2694\\u{FE0F}';
                else if (mode.includes('Range')) icon = '\\u{1F3AF}';

                gridHtml += `
                    <div class="cr-day-battle-card ${resClass}" id="modal-battle-dot-${idx}" onclick="showModalBattleDetails(${idx})" title="${b.opponent_name || 'Guerra'} (${b.crowns}x${b.opponent_crowns})">
                        ${icon}
                    </div>
                `;
            });

            const modalContent = document.getElementById('battle-modal-content');
            if (!modalContent) return;

            modalContent.innerHTML = `
                <div class="cr-day-modal-title">
                    <span>\u2694\\u{FE0F} Detalhes da Atividade - ${dateStr}</span>
                </div>

                <div class="cr-day-modal-layout">
                    <div class="cr-day-modal-box">
                        <h3 class="clash-font" style="font-size: 1.1em; color: #4299e1; margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
                            \u2694\\u{FE0F} BATTLE SUMMARY
                        </h3>

                        <div class="cr-day-metric-row">
                            <span class="cr-day-metric-label">Taxa de vit\u00f3ria</span>
                            <span class="cr-day-metric-dots"></span>
                            <span class="cr-day-metric-value" style="color: #48bb78;">${winRate}%</span>
                        </div>
                        <div class="cr-day-metric-row">
                            <span class="cr-day-metric-label">Sequ\u00eancia mais longa</span>
                            <span class="cr-day-metric-dots"></span>
                            <span class="cr-day-metric-value">${maxConseqWins}</span>
                        </div>
                        <div class="cr-day-metric-row">
                            <span class="cr-day-metric-label">M\u00e9dia de coroas</span>
                            <span class="cr-day-metric-dots"></span>
                            <span class="cr-day-metric-value">${avgCrowns}</span>
                        </div>
                        <div class="cr-day-metric-row">
                            <span class="cr-day-metric-label">Avg. Elixir Leaked</span>
                            <span class="cr-day-metric-dots"></span>
                            <span class="cr-day-metric-value">${avgElixir}</span>
                        </div>
                        <div class="cr-day-metric-row">
                            <span class="cr-day-metric-label">Deck Oponente</span>
                            <span class="cr-day-metric-dots"></span>
                            <span class="cr-day-metric-value" style="color: #f56565; font-size: 0.75em; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${worstEnemyDecks}</span>
                        </div>
                    </div>

                    <div class="cr-day-modal-box">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                            <h3 class="clash-font" style="font-size: 1.1em; color: #4299e1; margin: 0; display: flex; align-items: center; gap: 8px;">
                                \\u{1F6E1}\\u{FE0F} BATALHAS RECENTES
                            </h3>
                            <span class="clash-font" style="font-size: 0.95em; color: #94a3b8;">
                                <span style="color: #48bb78;">W${wins}</span> &middot; <span style="color: #f56565;">L${losses}</span>${draws > 0 ? ` &middot; <span style="color: #a0aec0;">D${draws}</span>` : ''}
                            </span>
                        </div>

                        <div class="cr-day-battles-grid">
                            ${gridHtml}
                        </div>
                    </div>
                </div>

                <div id="cr-day-battle-vs-container">
                </div>
            `;

            const modal = document.getElementById('cr-battle-modal');
            if (modal) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }

            if (dayBattles.length > 0) {
                showModalBattleDetails(0);
            }
        }

        function showModalBattleDetails(idx) {
            const battle = currentDayBattles[idx];
            if (!battle) return;

            currentDayBattles.forEach((_, i) => {
                const dot = document.getElementById(`modal-battle-dot-${i}`);
                if (dot) {
                    if (i === idx) dot.classList.add('active');
                    else dot.classList.remove('active');
                }
            });

            const container = document.getElementById('cr-day-battle-vs-container');
            if (!container) return;

            const crowns = battle.crowns;
            const opponent_crowns = battle.opponent_crowns;
            const dateContent = battle.b_date;
            const gameMode = battle.game_mode || 'Batalha';
            const arenaName = battle.arena_name || 'Arena';
            const trophyChange = battle.trophy_change || 0;

            const resClass = crowns > opponent_crowns ? 'victory' : (crowns < opponent_crowns ? 'defeat' : 'draw');
            const resultText = crowns > opponent_crowns ? 'VIT\u00d3RIA' : (crowns < opponent_crowns ? 'DERROTA' : 'EMPATE');

            const playerMetrics = {
                avg: '--',
                cycle: '--',
                leaked: battle.elixir_p || 0,
                level: 14,
                hp: battle.p_hp || '4.820',
                tower_url: battle.p_tower_url
            };

            const oppMetrics = {
                avg: '--',
                cycle: '--',
                leaked: battle.elixir_o || 0,
                level: battle.opp_level || 14,
                hp: battle.o_hp || '4.820',
                tower_url: battle.o_tower_url
            };

            const pCardIds = battle.p_deck_list && window.CARD_IDS ? battle.p_deck_list.map(c => window.CARD_IDS[c]).filter(Boolean) : [];
            const oCardIds = battle.o_deck_list && window.CARD_IDS ? battle.o_deck_list.map(c => window.CARD_IDS[c]).filter(Boolean) : [];
            const pDeckLink = pCardIds.length >= 8 ? 'https://link.clashroyale.com/pt/?clashroyale://copyDeck?deck=' + pCardIds.join(';') + '&l=Royals&tt=159000000' : '';
            const oDeckLink = oCardIds.length >= 8 ? 'https://link.clashroyale.com/pt/?clashroyale://copyDeck?deck=' + oCardIds.join(';') + '&l=Royals&tt=159000000' : '';

            const pGrid = getMiniGridJS(battle.my_deck, 'cr-deck-left', 'Voc\u00ea', '', playerMetrics, pDeckLink, null);

            const oGrid = getMiniGridJS(battle.opp_deck, 'cr-deck-right', battle.opponent_name || 'Oponente', '', oppMetrics, oDeckLink, null);

            let trophyHtml = '';
            if (trophyChange !== 0) {
                const sign = trophyChange > 0 ? '+' : '';
                const color = trophyChange > 0 ? '#48bb78' : '#f56565';
                trophyHtml = `<span style="color: ${color}; font-weight: bold; font-family: 'Inter', monospace; margin-left: 10px;">${sign}${trophyChange} Trof\u00e9us</span>`;
            }

            container.innerHTML = `
                <div class="cr-main-vs-stage cr-day-modal-box" style="margin-top: 20px; padding: 25px !important; border: 1px solid rgba(255,255,255,0.06); background: rgba(15, 23, 42, 0.6) !important;">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 15px; margin-bottom: 25px; flex-wrap: wrap; gap: 15px;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span class="clash-font" style="font-size: 1.1em; color: #4299e1;">${gameMode}</span>
                            <span style="color: #64748b; font-size: 0.9em;">&bull;</span>
                            <span style="color: #94a3b8; font-size: 0.9em; font-weight: 600;">${arenaName}</span>
                            ${trophyHtml}
                        </div>
                        <div style="color: #94a3b8; font-size: 0.9em; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                            <i class="far fa-calendar-alt" style="opacity: 0.7;"></i>
                            <span>${dateContent}</span>
                        </div>
                    </div>

                    <div class="cr-vs-decks-row-premium" style="display: grid; grid-template-columns: 1fr 150px 1fr; gap: 20px; align-items: center;">

                        <div class="cr-deck-side cr-deck-left" style="display: flex; flex-direction: column; align-items: flex-start; width: 100%;">
                            <div class="cr-vs-player-info" style="margin-bottom: 15px; display: flex; align-items: center; gap: 12px; width: 100%;">
                                <div class="cr-tower-card-premium" style="margin: 0; width: 64px; height: 80px; border-radius: 12px; padding: 5px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); display: flex; flex-direction: column; justify-content: center; align-items: center;">
                                    <img src="${pGrid.towerUrl}" class="cr-tower-img-premium cr-tower-zoom" style="width: 50px; height: 50px; object-fit: contain;">
                                    <span style="font-size: 0.65em; font-weight: 800; color: #94a3b8; margin-top: 4px;">NV ${pGrid.tLevel}</span>
                                </div>
                                <div>
                                    <div class="cr-player-name-vs clash-font" style="font-size: 1.15em; color: #fff; margin-bottom: 2px;">Voc\u00ea</div>
                                    <div style="display: flex; gap: 10px; font-size: 0.8em; color: #94a3b8; font-weight: 600;">
                                        <span>\\u{1F3F0} HP: ${pGrid.tHP}</span>
                                        ${battle.elixir_p > 0 ? `<span class="cr-leak-active" style="color: #f6ad55;">\\u{1F4A7} Vazou: ${battle.elixir_p.toFixed(1)}</span>` : ''}
                                    </div>
                                </div>
                            </div>

                            <div style="width: 100%;">
                                ${pGrid.cardsHtml}
                            </div>
                        </div>

                        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;">
                            <div class="clash-font" style="font-size: 2.2em; color: #fff; text-shadow: 0 0 20px rgba(255,255,255,0.2); letter-spacing: 2px;">
                                ${crowns} - ${opponent_crowns}
                            </div>
                            <div class="cr-vs-center-divider" style="font-size: 0.8em; font-weight: 900; letter-spacing: 2px; padding: 4px 12px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8;">
                                VS
                            </div>
                            <div style="font-size: 0.75em; font-weight: 800; letter-spacing: 1px; color: ${resClass === 'victory' ? '#48bb78' : (resClass === 'defeat' ? '#f56565' : '#a0aec0')};">
                                ${resultText}
                            </div>
                        </div>

                        <div class="cr-deck-side cr-deck-right" style="display: flex; flex-direction: column; align-items: flex-end; width: 100%;">
                            <div class="cr-vs-player-info" style="margin-bottom: 15px; display: flex; flex-direction: row-reverse; align-items: center; gap: 12px; width: 100%; text-align: right;">
                                <div class="cr-tower-card-premium" style="margin: 0; width: 64px; height: 80px; border-radius: 12px; padding: 5px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); display: flex; flex-direction: column; justify-content: center; align-items: center;">
                                    <img src="${oGrid.towerUrl}" class="cr-tower-img-premium cr-tower-zoom cr-tower-mirrored" style="width: 50px; height: 50px; object-fit: contain;">
                                    <span style="font-size: 0.65em; font-weight: 800; color: #94a3b8; margin-top: 4px;">NV ${oGrid.tLevel}</span>
                                </div>
                                <div>
                                    <div class="cr-player-name-vs clash-font" style="font-size: 1.15em; color: #fff; margin-bottom: 2px; display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                                        <span>${battle.opponent_name || 'Oponente'}</span>
                                    </div>
                                    <div style="display: flex; gap: 10px; font-size: 0.8em; color: #94a3b8; font-weight: 600; justify-content: flex-end;">
                                        ${battle.elixir_o > 0 ? `<span class="cr-leak-active" style="color: #f6ad55;">\\u{1F4A7} Vazou: ${battle.elixir_o.toFixed(1)}</span>` : ''}
                                        <span>#${battle.opponent_tag || ''}</span>
                                    </div>
                                </div>
                            </div>

                            <div style="width: 100%;">
                                ${oGrid.cardsHtml}
                            </div>
                        </div>

                    </div>
                </div>
            `;
        }

        function closeBattleModal() {
            const modal = document.getElementById('cr-battle-modal');
            if (modal) modal.classList.remove('active');
            document.body.style.overflow = '';
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeBattleModal();
        });

        document.addEventListener('click', (e) => {
            const modal = document.getElementById('cr-battle-modal');
            if (e.target === modal) closeBattleModal();
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
                "p_grid": self._generate_deck_grid_html_simple(b['my_deck'], self.get_copy_deck_link([c.strip() for c in b.get('my_deck','').split('|') if c.strip()])),
                "o_grid": self._generate_deck_grid_html_simple(b['opp_deck'], self.get_copy_deck_link([c.strip() for c in b.get('opp_deck','').split('|') if c.strip()])),
                "p_tower_url": my_m['tower_url'],
                "o_tower_url": opp_m['tower_url'],
                "p_level": my_m['level'],
                "o_level": opp_m['level'],
                "p_hp": my_m.get('hp', '--'),
                "o_hp": opp_m.get('hp', '--'),
                "p_deck_list": [c.strip() for c in b.get('my_deck','').split('|') if c.strip()],
                "o_deck_list": [c.strip() for c in b.get('opp_deck','').split('|') if c.strip()],
                "p_name": p_name,
                "p_tag": self.player_tag,
                "p_clan": p_clan,
                "o_name": o_name,
                "o_tag": o_tag,
                "o_clan": o_clan,
                "trophy_change": b.get('trophy_change', 0),
                "arena": b.get('arena_name', 'Arena'),
                "t_ini": b.get('trofes_iniciais_jogador', '0'),
                "t_fin": b.get('trofes_finais_jogador', '0'),
                "rank_p": b.get('posicao_global_jogador', 'N/A'),
                "rank_o": b.get('posicao_global_oponente', 'N/A')
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
    
    def _generate_history_dots_simple(self, deck_id, battles_list, p_name, p_clan):
        """Versão simples dos dots históricos para Meus Decks (sem JS complex)."""
        if not battles_list:
            return ''
        
        dots_html = '<div style="margin-top: 12px; padding: 10px; background: rgba(15,23,42,0.3); border-radius: 10px; border: 1px solid rgba(255,255,255,0.03);">'
        dots_html += '<div style="display: flex; gap: 4px; overflow-x: auto; flex-wrap: wrap;">'
        
        for b in battles_list[:10]:
            res = b['resultado'].lower() if b.get('resultado') else 'unknown'
            res_char = 'V' if any(x in res for x in ['vitoria', 'victory', 'vitória']) else ('D' if any(x in res for x in ['derrota', 'defeat']) else 'E')
            res_color = '#48bb78' if res_char == 'V' else ('#f56565' if res_char == 'D' else '#718096')
            time_str = b['dt_obj'].strftime('%H:%M') if b.get('dt_obj') else '--:--'
            
            dots_html += f'''<div style="flex-shrink: 0; padding: 4px 8px; background: rgba(0,0,0,0.2); border-radius: 6px; border: 1px solid {res_color}40; text-align: center;">
                <div style="font-size: 0.75em; font-weight: 900; color: {res_color};">{res_char}</div>
                <div style="font-size: 0.55em; color: rgba(255,255,255,0.4);">{time_str}</div>
            </div>'''
        
        dots_html += '</div></div>'
        return dots_html

    def _render_tower_v2(self, metrics: Dict, section_id: str = "", is_opponent: bool = False) -> str:
        """Renderiza o componente de torre Premium v2."""
        side = "o" if is_opponent else "p"
        alt = "Torre Oponente" if is_opponent else "Torre Jogador"
        img_id = f'{side}-tower-img-{section_id}' if section_id else ""
        id_attr = f'id="{img_id}"' if img_id else ""
        
        return f'''
            <div class="cr-tower-display-v2">
                <img {id_attr} src="{metrics["tower_url"]}" class="cr-tower-img-premium" alt="{alt}">
                <div class="cr-tower-hp-v2">{metrics.get("hp", "--")} HP</div>
            </div>
        '''

    def _render_player_meta_v2(self, info: Dict, is_opponent: bool = False) -> str:
        """Renderiza os metadados do jogador (Tag, Nome, Clã)."""
        return f'''
            <div class="cr-vs-player-meta">
                <span class="cr-vs-tag">#{info["tag"]}</span>
                <span class="cr-vs-name">{info["name"]}</span>
                <span class="cr-vs-clan">{info.get("clan", "")}</span>
            </div>
        '''

    def _generate_metrics_panel_html_simple(self, metrics):
        leaked = float(metrics.get('leaked', 0))
        leak_class = "cr-leak-warning" if leaked > 0 else ""
        t_hp = metrics.get('hp', '--')
        
        # Ícone de leak: vermelho com glow se vazou, cinza semi-transparente se não vazou
        has_leak = leaked > 0
        leak_icon = "./ElixirVazado.png" if has_leak else "https://cdn.royaleapi.com/static/img/ui/elixir.png"
        
        # Cor do leak: vermelho se alto, amarelo se médio, branco se zero
        leak_color = "#f87171" if leaked > 0.5 else ("#fbbf24" if leaked > 0 else "#fff")
        
        return f"""
            <div class="cr-metric-inline" title="Elixir Médio" style="display: flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.3); padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <img src="https://cdn.royaleapi.com/static/img/ui/elixir.png" style="width: 20px; height: 20px; filter: drop-shadow(0 0 5px rgba(168, 85, 247, 0.4));">
                <span style="font-weight: 900; font-size: 1.1em; color: #fff; font-family: 'Krona One', sans-serif;">{metrics['avg']}</span>
            </div>
            <div class="cr-metric-inline" title="Ciclo 4" style="display: flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.3); padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <img src="./ciclo4.png" style="width: 20px; height: 20px; object-fit: contain; filter: drop-shadow(0 0 5px rgba(59, 130, 246, 0.4));">
                <span style="font-weight: 900; font-size: 1.1em; color: #fff; font-family: 'Krona One', sans-serif;">{metrics['cycle']}</span>
            </div>
            <div class="cr-metric-inline {leak_class}" title="Elixir Vazado" style="display: flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.3); padding: 4px 10px; border-radius: 8px; border: 1px solid { 'rgba(248, 113, 113, 0.3)' if leaked > 0 else 'rgba(255,255,255,0.05)' };">
                <img src="{leak_icon}" style="width: 20px; height: 20px; opacity: {1 if has_leak else 0.4}; filter: { 'drop-shadow(0 0 8px rgba(248, 113, 113, 0.8))' if has_leak else 'none' };">
                <span style="font-weight: 900; font-size: 1.1em; color: {leak_color}; font-family: 'Krona One', sans-serif;">{metrics.get('leaked_label', '0.0')}</span>
            </div>
            <div class="cr-metric-inline" title="HP Restante" style="display: flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.3); padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <img src="./torreDoRei.png" style="width: 20px; height: 20px; filter: drop-shadow(0 0 5px rgba(255,255,255,0.2));">
                <span style="font-weight: 900; font-size: 1.1em; color: #fff; font-family: 'Krona One', sans-serif;">{t_hp}</span>
            </div>
        """


    def _generate_deck_grid_html_simple(self, deck_str, copy_link=None):
        if not deck_str or deck_str == 'N/D': return '<div class="cr-empty-grid">N/D</div>'
        
        # Parse das cartas: "Nome|Nível|Evolução"
        cards_raw = [c.strip() for c in deck_str.replace(' | ', '|').split('|') if c.strip()][:8]
        cards_data = []
        for c in cards_raw:
            parts = c.split('|')
            name = parts[0]
            level = parts[1] if len(parts) > 1 else "14"
            is_evo = parts[2].lower() == 'true' if len(parts) > 2 else False
            cards_data.append({'name': name, 'level': level, 'is_evo': is_evo})

        html_cards = ""
        for card in cards_data:
            img_url = self.get_card_image_path(card['name'])
            
            # Premium v2: Evolução com glow roxo e badge
            evo_class = "cr-card-evo-premium" if card['is_evo'] else ""
            evo_badge = '<div class="cr-evo-badge-icon"></div>' if card['is_evo'] else ""
            
            # Premium v2: Nível 15 (Elite) com badge especial dourado
            level_class = "cr-lvl-15" if card['level'] == "15" else ""
            level_badge = f'<span class="cr-card-level-badge {level_class}">{card["level"]}</span>'
            
            html_cards += f'''
                <div class="cr-card-wrap-premium {evo_class} {level_class}">
                    <img src="{img_url}" class="cr-card-img" alt="{card['name']}">
                    {evo_badge}
                    {level_badge}
                </div>'''

        copy_btn = ""
        if copy_link:
            copy_btn = f'<button type="button" onclick="copyDeckLink(event, this, \'{copy_link}\')" class="cr-copy-deck-btn" title="Copiar Deck"><span><i class="fas fa-copy"></i></span></button>'

        return f'<div class="cr-grid-wrapper-premium"><div class="cr-grid-4x2">{html_cards}</div>{copy_btn}</div>'
        
    def _generate_deck_view_html(self, deck_str, battle_data, player_name, player_clan, player_tag, section_id, deck_id, is_opponent=False):
        """Gera visualização de deck similar ao VS Stage para Meus Decks e Top Global."""
        my_metrics = self._get_battle_deck_metrics(deck_str, battle_data, is_opponent=False)
        opp_metrics = self._get_battle_deck_metrics(battle_data.get('opp_deck', ''), battle_data, is_opponent=True)
        
        p_crowns = battle_data.get('coroas_jogador', 0)
        o_crowns = battle_data.get('coroas_oponente', 0)
        res_color = "#4ade80" if p_crowns > o_crowns else ("#f87171" if p_crowns < o_crowns else "#94a3b8")
        
        try:
            trophy_val = int(battle_data.get('mudanca_trofes', 0))
        except (ValueError, TypeError):
            trophy_val = 0
        trophy_color = '#4ade80' if trophy_val > 0 else ('#f87171' if trophy_val < 0 else '#94a3b8')
        trophy_sign = '+' if trophy_val > 0 else ''
        
        return f"""
        <div style="width: 100%; max-width: 600px; margin: 0 auto;">
            <!-- Linha 1: Info e Placar (Topo) -->
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 12px; gap: 15px;">
                <!-- Jogador -->
                <div style="text-align: left; flex: 1;">
                    <div style="font-size: 0.55em; color: rgba(255,255,255,0.25); font-weight: 800;">#{player_tag}</div>
                    <div style="font-size: 0.9em; font-weight: 950; color: #fff; font-family: 'Outfit', sans-serif;">{player_name}</div>
                </div>

                <!-- Centro: Placar -->
                <div style="text-align: center; min-width: 80px;">
                    <div style="font-size: 1.5em; font-weight: 950; color: {res_color}; letter-spacing: -1px; line-height: 1; font-family: 'Outfit', sans-serif;">
                        {p_crowns} - {o_crowns}
                    </div>
                    <div style="font-size: 0.55em; font-weight: 800; color: rgba(255,255,255,0.4); text-transform: uppercase;">{battle_data.get('modo_jogo', 'Batalha')[:15]}</div>
                </div>

                <!-- Oponente -->
                <div style="text-align: right; flex: 1;">
                    <div style="font-size: 0.55em; color: rgba(255,255,255,0.25); font-weight: 800;">#{battle_data.get('tag_oponente', '000000')[:10]}</div>
                    <div style="font-size: 0.9em; font-weight: 950; color: #f87171; font-family: 'Outfit', sans-serif;">{battle_data.get('nome_oponente', 'Oponente')[:15]}</div>
                </div>
            </div>

            <!-- Linha 2: Torres e Decks Compacto -->
            <div style="display: flex; gap: 12px; width: 100%; position: relative;">
                
                <!-- Coluna Jogador -->
                <div style="flex: 1; display: flex; flex-direction: column; align-items: center; position: relative;">
                    <div style="width: 60px; margin-bottom: 6px;">
                        <img src="{my_metrics['tower_url']}" style="width: 100%; filter: drop-shadow(0 0 10px rgba(74, 222, 128, 0.4));">
                    </div>
                    <div style="width: 100%; position: relative; z-index: 5;">
                        {self._generate_deck_grid_html_simple(deck_str, self.get_copy_deck_link([c.split('|')[0] for c in deck_str.split('|') if c]))}
                    </div>
                </div>

                <!-- Coluna Oponente -->
                <div style="flex: 1; display: flex; flex-direction: column; align-items: center; position: relative;">
                    <div style="width: 60px; margin-bottom: 6px;">
                        <img src="{opp_metrics['tower_url']}" style="width: 100%; transform: scaleX(-1); filter: drop-shadow(0 0 10px rgba(248, 113, 113, 0.4));">
                    </div>
                    <div style="width: 100%; position: relative; z-index: 5;">
                        {self._generate_deck_grid_html_simple(battle_data.get('opp_deck', ''), self.get_copy_deck_link([c.split('|')[0] for c in battle_data.get('opp_deck', '').split('|') if c]))}
                    </div>
                </div>
            </div>

            <!-- Linha 3: Meta Info (Rodapé) -->
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); width: 100%; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; gap: 10px; align-items: center;">
                    <span style="font-size: 0.6em; font-weight: 700; color: rgba(255,255,255,0.4);">{battle_data.get('dt_obj', '').strftime('%d/%m') if battle_data.get('dt_obj') else '--/--'}</span>
                    <span style="font-size: 0.6em; font-weight: 900; color: {trophy_color};">{trophy_sign}{trophy_val} Troféus</span>
                </div>
            </div>
        </div>
        """

    def build_battle_preview_v2(self, battle_data, player_info, opp_info, section_id):
        """Construtor modular para o componente VS Stage (Redesign Premium v2)."""
        my_metrics = self._get_battle_deck_metrics(battle_data['my_deck'], battle_data, is_opponent=False)
        opp_metrics = self._get_battle_deck_metrics(battle_data['opp_deck'], battle_data, is_opponent=True)
        
        # Cores dinâmicas para o placar
        p_crowns = battle_data.get('crowns', 0)
        o_crowns = battle_data.get('opponent_crowns', 0)
        
        res_color = "#4ade80" if p_crowns > o_crowns else ("#f87171" if p_crowns < o_crowns else "#94a3b8")
        
        # Troféus
        try:
            trophy_val = int(battle_data.get('trophy_change', 0))
        except (ValueError, TypeError):
            trophy_val = 0
            
        trophy_color = '#4ade80' if trophy_val > 0 else ('#f87171' if trophy_val < 0 else '#94a3b8')
        trophy_sign = '+' if trophy_val > 0 else ''

        return f"""
        <div class="cr-vs-stage-v2" id="vs-content-{section_id}">
            
            <!-- Linha 1: Info e Placar (Topo) - Layout Compacto -->
            <div class="cr-vs-top-row-v2" style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 20px; gap: 20px;">
                <!-- Jogador -->
                <div class="cr-vs-side-info player" style="text-align: left; flex: 1;">
                    <div id="p-tag-{section_id}" style="font-size: 0.6em; color: rgba(255,255,255,0.2); font-weight: 800; font-family: 'Krona One', sans-serif;">#{player_info['tag']}</div>
                    <div id="p-name-{section_id}" style="font-size: 1.1em; font-weight: 950; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: 'Krona One', sans-serif;">{player_info['name']}</div>
                    <div id="p-clan-{section_id}" style="font-size: 0.7em; color: rgba(255,255,255,0.4); font-weight: 700;">{player_info.get('clan', 'Sem Clã')}</div>
                </div>

                <!-- Centro: Placar -->
                <div class="cr-vs-center-v2" style="text-align: center; min-width: 120px;">
                    <div id="score-{section_id}" style="font-size: 2em; font-weight: 950; color: {res_color}; letter-spacing: -2px; line-height: 1; font-family: 'Krona One', sans-serif;">
                        {p_crowns} - {o_crowns}
                    </div>
                    <div id="mode-{section_id}" style="font-size: 0.65em; font-weight: 900; color: rgba(255,255,255,0.4); text-transform: uppercase; margin-top: 4px;">
                        {battle_data.get('game_mode', 'Batalha')}
                    </div>
                </div>

                <!-- Oponente -->
                <div class="cr-vs-side-info opponent" style="text-align: right; flex: 1;">
                    <div id="o-tag-{section_id}" style="font-size: 0.6em; color: rgba(255,255,255,0.2); font-weight: 800; font-family: 'Krona One', sans-serif;">#{opp_info['tag']}</div>
                    <div id="o-name-{section_id}" style="font-size: 1.1em; font-weight: 950; color: #f87171; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: 'Krona One', sans-serif;">{opp_info['name']}</div>
                    <div id="o-clan-{section_id}" style="font-size: 0.7em; color: rgba(255,255,255,0.4); font-weight: 700;">{opp_info.get('clan', '')}</div>
                </div>
            </div>

            <!-- Linha 2: Torres e Decks -->
            <div class="cr-vs-decks-row-v2" style="display: flex; gap: 20px; width: 100%; position: relative;">
                
                <!-- Coluna Jogador -->
                <div class="cr-vs-deck-column player" style="flex: 1; display: flex; flex-direction: column; align-items: center; position: relative;">
                    <div id="p-tower-container-{section_id}" style="width: 90px; margin-bottom: 10px; transition: all 0.3s ease;">
                        <img id="p-tower-img-{section_id}" src="{my_metrics['tower_url']}" class="cr-tower-zoom" style="width: 100%; filter: drop-shadow(0 0 15px rgba(74, 222, 128, 0.4));">
                        <div id="p-tower-hp-{section_id}" style="text-align: center; font-size: 0.6em; font-weight: 950; color: #4ade80; margin-top: -5px; background: rgba(0,0,0,0.6); padding: 1px 6px; border-radius: 10px;">{my_metrics.get('hp', '--')} HP</div>
                    </div>
                    <div id="p-grid-{section_id}" style="width: 100%; position: relative; z-index: 5;">
                        {self._generate_deck_grid_html_simple(battle_data['my_deck'], self.get_copy_deck_link([c.split('|')[0] for c in battle_data['my_deck'].split('|') if c]))}
                    </div>
                    <div id="player-metrics-{section_id}" style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; width: 100%;">
                        {self._generate_metrics_panel_html_simple(my_metrics)}
                    </div>
                </div>

                <!-- Coluna Oponente -->
                <div class="cr-vs-deck-column opponent" style="flex: 1; display: flex; flex-direction: column; align-items: center; position: relative;">
                    <div id="o-tower-container-{section_id}" style="width: 90px; margin-bottom: 10px; transition: all 0.3s ease;">
                        <img id="o-tower-img-{section_id}" src="{opp_metrics['tower_url']}" class="cr-tower-zoom cr-tower-mirrored" style="width: 100%; filter: drop-shadow(0 0 15px rgba(248, 113, 113, 0.4));">
                        <div id="o-tower-hp-{section_id}" style="text-align: center; font-size: 0.6em; font-weight: 950; color: #f87171; margin-top: -5px; background: rgba(0,0,0,0.6); padding: 1px 6px; border-radius: 10px;">{opp_metrics.get('hp', '--')} HP</div>
                    </div>
                    <div id="o-grid-{section_id}" style="width: 100%; position: relative; z-index: 5;">
                        {self._generate_deck_grid_html_simple(battle_data['opp_deck'], self.get_copy_deck_link([c.split('|')[0] for c in battle_data['opp_deck'].split('|') if c]))}
                    </div>
                    <div id="opp-metrics-{section_id}" style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; width: 100%;">
                        {self._generate_metrics_panel_html_simple(opp_metrics)}
                    </div>
                </div>
            </div>

            <!-- Linha 3: Meta Info (Rodapé) -->
            <div class="cr-vs-footer-v2" style="margin-top: 15px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); width: 100%; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; gap: 15px; align-items: center;">
                    <span id="date-{section_id}" style="font-size: 0.7em; font-weight: 700; color: rgba(255,255,255,0.4);"><i class="far fa-calendar-alt" style="margin-right: 4px;"></i> {battle_data.get('date_str', '--/--')}</span>
                    <span id="time-{section_id}" style="font-size: 0.7em; font-weight: 700; color: rgba(255,255,255,0.3);"><i class="far fa-clock" style="margin-right: 4px;"></i> {battle_data.get('time_str', '--:--')}</span>
                    <span id="arena-{section_id}" style="font-size: 0.7em; color: rgba(255,255,255,0.4); font-weight: 800;"><i class="fas fa-map-marker-alt" style="margin-right: 4px; opacity: 0.7;"></i> {battle_data.get('arena_name', 'Arena')}</span>
                </div>
                <div style="display: flex; gap: 15px; align-items: center;">
                    <span id="trophy-change-{section_id}" style="font-size: 0.7em; font-weight: 900; color: {trophy_color};"><i class="fas fa-trophy" style="margin-right: 4px;"></i> {trophy_sign}{trophy_val} Troféus</span>
                    <span id="rank-p-{section_id}" style="font-size: 0.7em; color: rgba(255,255,255,0.3); font-weight: 800;"><i class="fas fa-globe" style="margin-right: 4px; opacity: 0.7;"></i> Rank P: {battle_data.get('posicao_global_jogador', 'N/A')}</span>
                    <span id="rank-o-{section_id}" style="font-size: 0.7em; color: rgba(255,255,255,0.3); font-weight: 800;"><i class="fas fa-globe" style="margin-right: 4px; opacity: 0.7;"></i> Rank O: {battle_data.get('posicao_global_oponente', 'N/A')}</span>
                </div>
                <div style="display: flex; gap: 10px;">
                     <button id="p-copy-{section_id}" onclick="copyToClipboardDeckDirect({[c.split('|')[0] for c in battle_data['my_deck'].split('|') if c]})" 
                             style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); color: #93c5fd; padding: 5px 12px; border-radius: 8px; font-size: 0.65em; font-weight: 900; cursor: pointer; transition: all 0.2s;">
                         <i class="far fa-copy"></i> MEU DECK
                     </button>
                     <button id="o-copy-{section_id}" onclick="copyToClipboardDeckDirect({[c.split('|')[0] for c in battle_data['opp_deck'].split('|') if c]})" 
                             style="background: rgba(248, 113, 113, 0.1); border: 1px solid rgba(248, 113, 113, 0.2); color: #fca5a5; padding: 5px 12px; border-radius: 8px; font-size: 0.65em; font-weight: 900; cursor: pointer; transition: all 0.2s;">
                         <i class="far fa-copy"></i> OPONENTE
                     </button>
                </div>
            </div>
        </div>
        """


    def generate_repeated_opponents_html(self, opponents: List[Dict]) -> str:
        """Gera HTML para oponentes repetidos com match cards inline usando layout Premium v2."""
        if not opponents: return '<div class="cr-empty-state">Nenhum oponente repetido encontrado no histórico recente.</div>'
        
        player_name = self.player_name_override or next((p.get('name', 'Jogador') for p in self.players_cache if p.get('player_tag') == self.player_tag), 'Jogador')
        player_clan = next((p.get('clan_name', '') for p in self.players_cache if p.get('player_tag') == self.player_tag), '')
        
        html = '<div class="cr-opponents-list" style="display: grid; gap: 30px;">'
        
        for i, opp in enumerate(opponents, 1):
            wr = opp['user_win_rate']
            category, cat_class = opp['category'], opp['category_class']
            stats_list = opp['stats']
            wr_c = '#4ade80' if wr >= 60 else ('#f87171' if wr <= 40 else '#94a3b8')
            
            # Primeira batalha (Palco VS inicial)
            first_b = stats_list[0]
            
            # Info necessária para o build_battle_preview_v2
            player_info = {'tag': self.player_tag, 'name': player_name, 'clan': player_clan}
            opp_info = {'tag': opp['opponent_tag'], 'name': opp['opponent_name'], 'clan': opp.get('opp_clan', '')}

            vs_stage_html = self.build_battle_preview_v2(first_b, player_info, opp_info, i)

            html += f'''
            <div class="cr-deck-card cr-glass-premium" id="opp-section-{i}" style="margin-bottom: 0 !important; overflow: visible; border: 1px solid rgba(255,255,255,0.1);">
                <div class="cr-deck-header" style="padding: 15px 25px; background: rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.05); border-radius: 24px 24px 0 0;">
                    <div style="display: flex; align-items: center; gap: 20px; width: 100%;">
                        <div class="cr-opp-rank" style="background: #fbbf24; color: #000; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: 10px; font-weight: 950; font-size: 1.1em; box-shadow: 0 0 20px rgba(251,191,36,0.3); font-family: 'Krona One', sans-serif;">{i}</div>
                        <div style="display: flex; flex-direction: column;">
                            <span style="font-weight: 950; font-size: 1.3em; color: #fff; letter-spacing: -0.5px; font-family: 'Krona One', sans-serif;">{opp['opponent_name']}</span>
                            <span style="font-size: 0.7em; color: rgba(255,255,255,0.4); font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">#{opp['opponent_tag']}</span>
                        </div>
                        <div style="margin-left: auto; display: flex; align-items: center; gap: 15px;">
                            <span class="rival-badge {cat_class}-badge" style="font-size: 0.75em; padding: 6px 12px; border-radius: 10px; font-weight: 900; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #e2e8f0;">{category}</span>
                            <div class="cr-wr-badge-v2" style="background: {wr_c}22; border: 1px solid {wr_c}44; color: {wr_c}; font-weight: 950; font-size: 0.9em; padding: 6px 15px; border-radius: 10px; font-family: 'Krona One', sans-serif;">
                                {wr}% WR
                            </div>
                        </div>
                    </div>
                </div>

                <div class="cr-deck-body" style="padding: 30px !important; background: transparent;">
                    {vs_stage_html}
                    
                    <!-- Histórico e Navegação -->
                    <div class="cr-history-nav-v2" style="margin-top: 30px; padding: 25px; background: rgba(15, 23, 42, 0.3); border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                            <span style="font-size: 0.75em; font-weight: 950; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 2px; font-family: 'Krona One', sans-serif;">Histórico de Encontros:</span>
                            <div style="display: flex; gap: 15px; font-size: 0.75em; color: rgba(255,255,255,0.5); font-weight: 800;">
                                <span id="history-date-{i}" title="Data do último encontro"><i class="far fa-calendar-alt"></i> {first_b.get('data_str','--/--').split(' ')[0]}</span>
                            </div>
                        </div>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                            {self._generate_history_dots(i, stats_list, player_name, player_clan, opp["opponent_name"], opp.get('opp_clan', ''), opp['opponent_tag'])}
                        </div>
                    </div>
                </div>
            </div>
            '''
        return html + "</div>"


    def generate_lethal_decks_html(self, lethal_decks: List[Dict]) -> str:
        """Gera HTML para os decks que mais causam derrotas com layout Premium v2 similar a Meus Decks."""
        if not lethal_decks: return '<div class="cr-empty-state">Dados insuficientes para mapear decks letais.</div>'
        
        # Container Grid para os Decks Letais
        html = '<div class="cr-lethal-decks-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px;">'
        
        for i, ld in enumerate(lethal_decks, 1):
            deck_str = ld['deck'] # O deck letal do oponente
            losses = ld['losses_caused'] 
            last = ld['last_encounter'][:16].replace('T', ' ')
            
            metrics = self._get_deck_metrics(deck_str)
            
            opp_cards_for_copy = [c.split('|')[0] for c in deck_str.split('|') if c]
            opp_copy_link = self.get_copy_deck_link(opp_cards_for_copy)
            
            html += f'''
            <div class="cr-deck-card cr-glass-premium" style="margin-bottom: 12px; overflow: visible; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; background: rgba(15,23,42,0.4);">
                <!-- Header Compacto -->
                <div class="cr-deck-header" style="padding: 10px 15px; background: rgba(0,0,0,0.4); border-bottom: 1px solid rgba(255,255,255,0.05); border-radius: 16px 16px 0 0;">
                    <div style="display: flex; align-items: center; gap: 10px; width: 100%; flex-wrap: wrap;">
                        <span style="background:#ef4444; color: #fff; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-weight: 900; font-size: 0.75em; font-family: 'Krona One', sans-serif;">#{i}</span>
                        <span style="color: #fff; font-size: 0.8em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">DECK INIMIGO</span>
                        <span style="margin-left: auto; background:rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; font-weight: 950; font-size: 0.8em; padding: 2px 8px; border-radius: 6px; font-family: 'Krona One', sans-serif;">{losses} Quedas</span>
                    </div>
                </div>
                
                <!-- Sub-header com data da última queda -->
                <div style="padding: 6px 12px; background: rgba(0,0,0,0.2); border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 0.7em; color: rgba(255,255,255,0.4); font-weight: 800; display: flex; justify-content: space-between;">
                    <span>Lethal Meta</span>
                    <span>Última queda: {last.split(' ')[0]}</span>
                </div>

                <!-- Conteúdo Compacto -->
                <div style="padding: 12px !important; background: transparent;">
                    <!-- Grid 4x2 do Deck -->
                    <div style="width: 100%; max-width: 320px; margin: 0 auto 10px auto;">
                        {self._generate_deck_grid_html_simple(deck_str, opp_copy_link)}
                    </div>
                    
                    <!-- Badges de Elixir Médio e Ciclo 4 -->
                    <div style="display: flex; gap: 8px; justify-content: center; margin-bottom: 4px;">
                        <div class="cr-metric-inline" title="Elixir Médio" style="display: flex; align-items: center; gap: 5px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.75em;">
                            <img src="https://cdn.royaleapi.com/static/img/ui/elixir.png" style="width: 14px; height: 14px; filter: drop-shadow(0 0 5px rgba(168, 85, 247, 0.4));">
                            <span style="font-weight: 900; color: #f59e0b;">{metrics['avg']}</span>
                        </div>
                        <div class="cr-metric-inline" title="Custo de Ciclo (4 cartas)" style="display: flex; align-items: center; gap: 5px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.75em;">
                            <img src="./ciclo4.png" style="width: 14px; height: 14px; filter: drop-shadow(0 0 5px rgba(56, 189, 248, 0.4));">
                            <span style="font-weight: 900; color: #38bdf8;">{metrics['cycle']}</span>
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
        war_decks_path = os.path.join(self.project_root, "data", "csv", "war_decks_top_players.csv")
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
            logger.error(f"Error loading war decks: {e}")
            
        # Aumenta o limite para mostrar mais jogadores do clã
        players['clan'] = players['clan'][:15]
        players['global'] = players['global'][:10]
        return players

    def get_meta_brasil_data(self):
        """Lê os dados do ranking Top 100 Brasil do JSON com filtro de reset."""
        file_path = os.path.join(self.project_root, "data", "csv", "meta_brasil_top100.json")
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
            logger.error(f"Error reading meta_brasil_top100.json: {e}")
            return []

    def get_war_day_history(self, days_back: int = 7) -> List[Dict]:
        """Coleta histórico de status_barcos para os últimos dias."""
        # 1. Tenta buscar do historico consolidado status_barcos_historico.csv
        historico_path = os.path.join(self.project_root, "data", "csv", "status_barcos_historico.csv")
        if os.path.exists(historico_path):
            try:
                with open(historico_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    rows = list(reader)
                
                # Agrupar por data_coleta
                # Para get_war_day_history retrocompativel, pegamos os dados de 'principal' por padrao
                by_date = {}
                for row in rows:
                    if row.get('conta_tipo') != 'principal':
                        continue
                    
                    data_coleta = row.get('data_coleta')
                    if not data_coleta:
                        continue
                    
                    # Converte YYYY-MM-DD para YYYY_MM_DD
                    date_key = data_coleta.replace('-', '_')
                    if date_key not in by_date:
                        by_date[date_key] = []
                    
                    by_date[date_key].append({
                        'Posicao': row.get('posicao'),
                        'Nome_Cla': row.get('clan_nome'),
                        'Fama_Atual': row.get('fama_atual'),
                        'Pontos_Reparo': row.get('pontos_reparo'),
                        'Finalizado': row.get('finalizado'),
                        'Pontos_Periodo': row.get('pontos_periodo')
                    })
                
                # Ordenar datas decrescente
                sorted_dates = sorted(by_date.keys(), reverse=True)
                
                history = []
                for d in sorted_dates[:days_back]:
                    history.append({
                        'date': d,
                        'boats': by_date[d]
                    })
                return history
            except Exception as e:
                logger.error(f"Erro ao ler consolidado status_barcos_historico.csv em get_war_day_history: {e}")
        
        # Fallback para o comportamento legado de glob fisico
        history = []
        import glob
        boat_files = glob.glob(os.path.join(self.project_root, "data", "csv", "status_barcos_*.csv"))
        
        if not boat_files:
            return history
        
        # Ordena por data (mais recente primeiro)
        sorted_files = sorted(boat_files, reverse=True)
        
        for filepath in sorted_files[:days_back]:
            try:
                filename = os.path.basename(filepath)
                date_str = filename.replace('status_barcos_', '').replace('.csv', '')
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    boats = list(reader)
                    
                history.append({
                    'date': date_str,
                    'boats': boats
                })
            except Exception as e:
                logger.error(f"Erro ao ler {filepath}: {e}")
                continue
        
        return history
    
    def get_war_calendar_data(self, my_clan: str, days_back: int = 5, suffix: str = '', player_tag: str = None) -> List[Dict]:
        """Retorna dados processados do calendario de guerra para um cla especifico de forma unificada.
        
        Garante exatamente 5 datas operacionais cronologicas crescentes de Quinta a Segunda.
        """
        # Obter logical_today baseado no corte operacional das 07:00 da manha
        now = _get_brt_now()
        if now.hour < 7:
            logical_today = now.date() - timedelta(days=1)
        else:
            logical_today = now.date()
        
        # Achar a Quinta-feira operacional de inicio da guerra
        weekday = logical_today.weekday()
        if weekday >= 3:
            start_date = logical_today - timedelta(days=(weekday - 3))
        else:
            start_date = logical_today - timedelta(days=(weekday + 4))
            
        war_dates = []
        for i in range(5):
            war_dates.append(start_date + timedelta(days=i))
            
        war_day_labels = {3: "Reset", 4: "Dia 1", 5: "Dia 2", 6: "Dia 3", 0: "Dia 4"}
        
        guerra_hist_path = os.path.join(self.project_root, "data", "csv", "guerra_historico.csv")
        status_hist_path = os.path.join(self.project_root, "data", "csv", "status_barcos_historico.csv")
        
        # Se os consolidados existem, faz a leitura unificada
        if os.path.exists(guerra_hist_path) and os.path.exists(status_hist_path):
            try:
                pref_suffix = '_pri'
                my_clan_lower = my_clan.lower() if my_clan else ''
                if 'lendario' in my_clan_lower or 'secund' in my_clan_lower or 'bruxo 2' in my_clan_lower or 'sec' in suffix or (player_tag and '2220UQQ0UU' in player_tag.upper()):
                    pref_suffix = '_sec'
                
                target_suffix = suffix or pref_suffix
                conta_tipo = 'principal' if target_suffix == '_pri' else 'secundaria'
                
                # 1. Carrega dados de barcos do historico
                with open(status_hist_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    status_rows = list(reader)
                
                status_by_date = {}
                clans_cumulative = {}  # date_str -> clan_nome -> fame_acumulada
                for row in status_rows:
                    if row.get('conta_tipo') == conta_tipo:
                        dt = row.get('data_coleta', '')
                        dt_key = dt.replace('-', '_')
                        if dt_key not in status_by_date:
                            status_by_date[dt_key] = []
                        status_by_date[dt_key].append(row)
                        
                        clan_nome = row.get('clan_nome', '')
                        if dt_key and clan_nome:
                            if dt_key not in clans_cumulative:
                                clans_cumulative[dt_key] = {}
                            clans_cumulative[dt_key][clan_nome] = safe_int(row.get('fama_atual', 0))
                
                # Calcular a fama diária e a posição diária para todas as 5 datas da guerra ativa
                clans_daily_data = {}  # date_str -> clan_nome -> {fama_diaria, posicao_diaria}
                cron_dates = sorted(war_dates)
                for idx, day_date in enumerate(cron_dates):
                    date_str = day_date.strftime('%Y_%m_%d')
                    logical_weekday = day_date.weekday()
                    clans_daily_data[date_str] = {}
                    
                    if logical_weekday == 3:  # Reset (Quinta-feira)
                        if date_str in clans_cumulative:
                            for cn in clans_cumulative[date_str].keys():
                                clans_daily_data[date_str][cn] = {
                                    'fama_diaria': 0,
                                    'posicao_diaria': 0
                                }
                        continue
                    
                    today_cums = clans_cumulative.get(date_str, {})
                    prev_date_str = cron_dates[idx-1].strftime('%Y_%m_%d') if idx > 0 else None
                    
                    is_prev_reset = False
                    if idx > 0 and cron_dates[idx-1].weekday() == 3:
                        is_prev_reset = True
                        
                    prev_cums = {}
                    if prev_date_str and not is_prev_reset:
                        prev_cums = clans_cumulative.get(prev_date_str, {})
                        
                    day_fames = []
                    for cn, fame_today in today_cums.items():
                        fame_prev = prev_cums.get(cn, 0)
                        fama_diaria = max(0, fame_today - fame_prev)
                        day_fames.append((cn, fama_diaria))
                    
                    # Ordenar por fama diária decrescente
                    sorted_day = sorted(day_fames, key=lambda x: x[1], reverse=True)
                    
                    ranked_count = 1
                    for cn, fama in sorted_day:
                        if fama > 0:
                            pos = ranked_count
                            ranked_count += 1
                        else:
                            pos = 0
                        clans_daily_data[date_str][cn] = {
                            'fama_diaria': fama,
                            'posicao_diaria': pos
                        }
                
                # 2. Carrega dados de inteligencia do historico
                with open(guerra_hist_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    guerra_rows = list(reader)
                
                # Mapear as famas acumuladas dos jogadores por data e player_tag
                player_tag_cums = {}  # date_key -> player_tag_or_name -> cumulative_fame
                for row in guerra_rows:
                    dt = row.get('data_coleta', '')
                    dt_key = dt.replace('-', '_')
                    tag = row.get('player_tag') or row.get('player_nome') or row.get('Jogador', '')
                    fame = safe_int(row.get('player_fame') or row.get('Fama_Hoje', 0))
                    if dt_key and tag:
                        if dt_key not in player_tag_cums:
                            player_tag_cums[dt_key] = {}
                        player_tag_cums[dt_key][tag] = fame
                
                intel_data = {}  # date_key -> clan_name -> {position, fame}
                players_by_date = {}  # date_key -> list of rows
                
                for row in guerra_rows:
                    dt = row.get('data_coleta', '')
                    dt_key = dt.replace('-', '_')
                    
                    if dt_key not in intel_data:
                        intel_data[dt_key] = {}
                    if dt_key not in players_by_date:
                        players_by_date[dt_key] = []
                    
                    players_by_date[dt_key].append(row)
                    
                    clan_nome = row.get('clan_nome') or row.get('Cla', '')
                    if clan_nome:
                        if clan_nome not in intel_data[dt_key]:
                            intel_data[dt_key][clan_nome] = {
                                'position': safe_int(row.get('clan_posicao') or row.get('Ranking', 0)),
                                'fame': safe_int(row.get('clan_fame') or row.get('Fama_Hoje', 0))
                            }
                
                days = []
                for day_date in war_dates:
                    date_str = day_date.strftime('%Y_%m_%d')
                    logical_weekday = day_date.weekday()
                    day_label = war_day_labels.get(logical_weekday, f"D{logical_weekday}")
                    is_today = day_date == logical_today
                    
                    clan_data = None
                    boat_status = 'unknown'
                    
                    if date_str in status_by_date:
                        for row in status_by_date[date_str]:
                            cn = row.get('clan_nome', '')
                            if my_clan.lower() in cn.lower() or cn.lower() in my_clan.lower():
                                finalizado = row.get('finalizado', 'Não')
                                reparo = safe_int(row.get('pontos_reparo', 0))
                                if finalizado == 'Sim':
                                    boat_status = 'complete'
                                elif reparo > 0:
                                    boat_status = 'repairing'
                                else:
                                    boat_status = 'active'
                                break
                    
                    # Priorizar dados oficiais acumulados de intel_data (guerra_historico.csv)
                    if date_str in intel_data:
                        my_clan_upper = my_clan.strip().upper()
                        for cn, data in intel_data[date_str].items():
                            cn_upper = cn.upper()
                            my_clean = ''.join(c for c in my_clan_upper if c.isascii())
                            cn_clean = ''.join(c for c in cn_upper if c.isascii())
                            if (my_clean in cn_clean or cn_clean in my_clean or 
                                my_clean.replace(' ', '') in cn_clean.replace(' ', '')):
                                clan_data = data
                                break

                    # Se nao encontrou no intel_data, tentar no status_by_date (dados de corrida de barco acumulados)
                    if not clan_data and date_str in status_by_date:
                        for row in status_by_date[date_str]:
                            cn = row.get('clan_nome', '')
                            if my_clan.lower() in cn.lower() or cn.lower() in my_clan.lower():
                                clan_data = {
                                    'position': safe_int(row.get('clan_posicao') or row.get('posicao', 0)),
                                    'fame': safe_int(row.get('clan_fame') or row.get('fama_acumulada') or row.get('Fama_Atual', 0)),
                                    'points': safe_int(row.get('pontos_reparo', 0))
                                }
                                break

                    # Fallback em ultimo caso para clans_daily_data
                    if not clan_data and date_str in clans_daily_data:
                        for cn, daily in clans_daily_data[date_str].items():
                            if my_clan.lower() in cn.lower() or cn.lower() in my_clan.lower():
                                clan_data = {
                                    'position': daily['posicao_diaria'],
                                    'fame': daily['fama_diaria']
                                }
                                break
                    
                    if clan_data:
                        top_players = []
                        if logical_weekday == 3:  # Quinta-feira (Reset) deve exibir "Sem dados"
                            top_players = []
                        elif date_str in players_by_date:
                            clan_players = []
                            prev_date_str = war_dates[idx-1].strftime('%Y_%m_%d') if idx > 0 else None
                            is_prev_reset = (idx > 0 and war_dates[idx-1].weekday() == 3)
                            
                            for row in players_by_date[date_str]:
                                clan_nome = row.get('clan_nome') or row.get('Cla', '')
                                my_clean = ''.join(c for c in my_clan.upper() if c.isascii())
                                cn_clean = ''.join(c for c in clan_nome.upper() if c.isascii())
                                if my_clean in cn_clean or cn_clean in my_clean:
                                    player_name = row.get('player_nome') or row.get('Jogador') or 'N/A'
                                    player_tag = row.get('player_tag') or player_name
                                    
                                    # Fama diária real (priorizar coluna war_medals limpa do dia operacional correspondente)
                                    fame_daily = safe_int(row.get('war_medals') or 0)
                                    if fame_daily > 900:
                                        fame_daily = 900
                                        
                                    if fame_daily == 0:
                                        # Fallback seguro para o cálculo de subtração
                                        fame_today = safe_int(row.get('player_fame') or row.get('Fama_Hoje', 0))
                                        fame_prev = 0
                                        if prev_date_str and not is_prev_reset:
                                            fame_prev = player_tag_cums.get(prev_date_str, {}).get(player_tag, 0)
                                        fame_daily = max(0, fame_today - fame_prev)
                                        
                                        # Se o delta diário der um valor impossível (> 900) por ausência de registro prévio, recalcula de forma estrita
                                        if fame_daily > 900:
                                            vits = safe_int(row.get('war_vitorias') or 0)
                                            ders = safe_int(row.get('war_derrotas') or 0)
                                            calculated_fame = (vits * 200) + (ders * 100)
                                            if calculated_fame > 0:
                                                fame_daily = min(900, calculated_fame)
                                            else:
                                                decks_used_num = safe_int(row.get('decks_usados') or 0)
                                                fame_daily = min(900, max(1, decks_used_num) * 100)
                                        elif fame_daily > 0 and fame_daily not in [100, 200, 300, 350, 400, 500, 600, 700, 800, 900]:
                                            # Caso tenhamos valores fracionados bizarros
                                            vits = safe_int(row.get('war_vitorias') or 0)
                                            ders = safe_int(row.get('war_derrotas') or 0)
                                            calculated_fame = (vits * 200) + (ders * 100)
                                            if calculated_fame > 0:
                                                fame_daily = min(900, calculated_fame)
                                    
                                    # Apenas jogadores que ativamente lutaram na guerra (pontuação > 0)
                                    if fame_daily > 0:
                                        clan_players.append({
                                            'name': player_name,
                                            'fame': fame_daily,
                                            'medals': fame_daily // 100
                                        })
                             
                            # Ordenar de forma estritamente decrescente pela fama diária do dia correspondente
                            clan_players_sorted = sorted(clan_players, key=lambda x: x['fame'], reverse=True)
                            top_players = clan_players_sorted[:3]
                        
                        # Calcular metricas preditivas usando o prediction_engine
                        decks_played = 0
                        decks_remaining = 200
                        efficiency = 0.0
                        projected_fame = clan_data['fame']
                        
                        if date_str in players_by_date:
                            metrics = self.prediction_engine.calculate_clan_metrics(players_by_date[date_str], my_clan)
                            decks_played = metrics['decks_played']
                            decks_remaining = metrics['decks_remaining']
                            efficiency = metrics['efficiency']
                            projected_fame = metrics['projected_fame']

                        days.append({
                            'date': date_str,
                            'label': day_label,
                            'position': clan_data['position'],
                            'fame': clan_data['fame'],
                            'points': clan_data.get('points', 0),
                            'is_active': is_today,
                            'boat_status': boat_status,
                            'top_players': top_players,
                            'decks_played': decks_played,
                            'decks_remaining': decks_remaining,
                            'efficiency': efficiency,
                            'projected_fame': projected_fame
                        })
                    else:
                        days.append({
                            'date': date_str,
                            'label': day_label,
                            'position': 0,
                            'fame': 0,
                            'points': 0,
                            'is_active': is_today,
                            'boat_status': 'unknown',
                            'top_players': [],
                            'decks_played': 0,
                            'decks_remaining': 200,
                            'efficiency': 0.0,
                            'projected_fame': 0
                        })
                return days
            except Exception as e:
                logger.error(f"Erro ao processar consolidado em get_war_calendar_data: {e}")
        
        # Fallback legado usando as mesmas 5 datas de Quinta a Segunda
        import glob
        days = []
        try:
            pref_suffix = '_pri'
            my_clan_lower = my_clan.lower() if my_clan else ''
            if 'lendario' in my_clan_lower or 'secund' in my_clan_lower or 'bruxo 2' in my_clan_lower or 'sec' in suffix:
                pref_suffix = '_sec'
            
            for day_date in war_dates:
                date_str = day_date.strftime('%Y_%m_%d')
                logical_weekday = day_date.weekday()
                day_label = war_day_labels.get(logical_weekday, f"D{logical_weekday}")
                is_today = day_date == logical_today
                
                # Procura arquivo de barco correspondente
                boat_file = None
                boat_files_found = glob.glob(os.path.join(self.project_root, "data", "csv", f"status_barcos_*_{date_str}.csv"))
                if boat_files_found:
                    for f in boat_files_found:
                        if suffix and f"status_barcos{suffix}_" in os.path.basename(f):
                            boat_file = f
                            break
                    if not boat_file:
                        for f in boat_files_found:
                            if f"status_barcos{pref_suffix}_" in os.path.basename(f):
                                boat_file = f
                                break
                    if not boat_file:
                        boat_file = boat_files_found[0]
                else:
                    # Tenta arquivo sem sufixo
                    single_file = os.path.join(self.project_root, "data", "csv", f"status_barcos_{date_str}.csv")
                    if os.path.exists(single_file):
                        boat_file = single_file
                
                # Procura arquivo de inteligencia correspondente
                intel_file = os.path.join(self.project_root, "data", "csv", f"inteligencia_guerra_{day_date.strftime('%Y-%m-%d')}.csv")
                if not os.path.exists(intel_file):
                    intel_file = os.path.join(self.project_root, "data", "csv", f"inteligencia_guerra_{date_str}.csv")
                if not os.path.exists(intel_file):
                    intel_file = None
                
                clan_data = None
                boat_status = 'unknown'
                top_players = []
                
                if intel_file:
                    try:
                        with open(intel_file, 'r', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f, delimiter=';')
                            clans_aggregated = {}
                            for row in reader:
                                clan_nome = row.get('clan_nome') or row.get('Cla', '')
                                if clan_nome:
                                    if clan_nome not in clans_aggregated:
                                        clans_aggregated[clan_nome] = {
                                            'position': safe_int(row.get('clan_posicao') or row.get('Ranking', 0)),
                                            'fame': safe_int(row.get('clan_fame') or row.get('Fama_Hoje', 0))
                                        }
                            
                            my_clan_upper = my_clan.strip().upper()
                            for cn, data in clans_aggregated.items():
                                cn_upper = cn.upper()
                                my_clean = ''.join(c for c in my_clan_upper if c.isascii())
                                cn_clean = ''.join(c for c in cn_upper if c.isascii())
                                if (my_clean in cn_clean or cn_clean in my_clean or 
                                    my_clean.replace(' ', '') in cn_clean.replace(' ', '')):
                                    clan_data = data
                                    break
                                    
                        top_players = self._get_top_players_for_day(intel_file, my_clan)
                    except Exception as e:
                        logger.error(f"Erro ao ler intel no fallback de calendario para {date_str}: {e}")
                
                if boat_file:
                    try:
                        with open(boat_file, 'r', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f, delimiter=';')
                            for b in reader:
                                cn = b.get('Nome_Cla') or b.get('clan_nome', '')
                                if my_clan.lower() in cn.lower() or cn.lower() in my_clan.lower():
                                    finalizado = b.get('Finalizado') or b.get('finalizado', 'Não')
                                    reparo = safe_int(b.get('pontos_reparo') or b.get('Pontos_Reparo', 0))
                                    if finalizado == 'Sim':
                                        boat_status = 'complete'
                                    elif reparo > 0:
                                        boat_status = 'repairing'
                                    else:
                                        boat_status = 'active'
                                        
                                    if not clan_data:
                                        clan_data = {
                                            'position': safe_int(b.get('Posicao') or b.get('posicao', 0)),
                                            'fame': safe_int(b.get('Fama_Atual') or b.get('fama_atual', 0))
                                        }
                                    break
                    except Exception as e:
                        logger.error(f"Erro ao ler boat no fallback de calendario para {date_str}: {e}")
                
                if clan_data:
                    days.append({
                        'date': date_str,
                        'label': day_label,
                        'position': clan_data['position'],
                        'fame': clan_data['fame'],
                        'points': clan_data.get('points', 0),
                        'is_active': is_today,
                        'boat_status': boat_status,
                        'top_players': top_players
                    })
                else:
                    days.append({
                        'date': date_str,
                        'label': day_label,
                        'position': 0,
                        'fame': 0,
                        'points': 0,
                        'is_active': is_today,
                        'boat_status': 'unknown',
                        'top_players': []
                    })
        except Exception as e:
            logger.error(f"Erro no fallback legado de get_war_calendar_data: {e}")
        
        return days
    
    def get_war_intelligence_data(self):
        """Coleta dados de inteligencia de guerra (Dia 4)."""
        guerra_hist_path = os.path.join(self.project_root, "data", "csv", "guerra_historico.csv")
        status_hist_path = os.path.join(self.project_root, "data", "csv", "status_barcos_historico.csv")
        
        # Tenta buscar dos consolidados
        if os.path.exists(guerra_hist_path) and os.path.exists(status_hist_path):
            try:
                data = {
                    'boats': [],
                    'rivals': {},
                    'difficulty': 'Indeterminada',
                    'summary': '',
                    'my_clan': 'Desconhecido'
                }
                
                # 1. Busca status dos barcos mais recentes
                with open(status_hist_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    status_rows = list(reader)
                
                if status_rows:
                    latest_date = max(row['data_coleta'] for row in status_rows)
                    # clãs da data mais recente da conta principal
                    latest_boats = [row for row in status_rows if row['data_coleta'] == latest_date and row.get('conta_tipo') == 'principal']
                    
                    if not latest_boats:
                        latest_boats = [row for row in status_rows if row['data_coleta'] == latest_date]
                        
                    data['boats'] = [{
                        'Posicao': r.get('posicao'),
                        'Nome_Cla': r.get('clan_nome'),
                        'Fama_Atual': r.get('fama_atual'),
                        'Pontos_Reparo': r.get('pontos_reparo'),
                        'Finalizado': r.get('finalizado'),
                        'Pontos_Periodo': r.get('pontos_periodo')
                    } for r in latest_boats]
                
                # 2. Busca inteligencia de oponentes mais recente
                with open(guerra_hist_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    guerra_rows = list(reader)
                
                if guerra_rows:
                    latest_intel_date = max(row['data_coleta'] for row in guerra_rows)
                    latest_guerra = [row for row in guerra_rows if row['data_coleta'] == latest_intel_date]
                    
                    for row in latest_guerra:
                        cla = row.get('clan_nome') or row.get('Cla') or 'Unknown'
                        if cla not in data['rivals']:
                            data['rivals'][cla] = []
                        if len(data['rivals'][cla]) < 3:
                            data['rivals'][cla].append(row)
                
                my_clan = "Tropa Do Bruxo"
                try:
                    players_file = os.path.join(self.project_root, "data", "csv", "players.csv")
                    if os.path.exists(players_file):
                        with open(players_file, 'r', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f, delimiter=';')
                            for row in reader:
                                if row.get('player_tag'):
                                    my_clan = row.get('clan_name', my_clan)
                                    break
                except Exception as e:
                    logger.warning(f"Erro ao ler players: {e}")
                
                data['my_clan'] = my_clan
                return data
            except Exception as e:
                logger.error(f"Erro em get_war_intelligence_data consolidado: {e}")
        
        # Fallback legado
        try:
            data = {
                'boats': [],
                'rivals': {},
                'difficulty': 'Indeterminada',
                'summary': '',
                'my_clan': 'Desconhecido'
            }
            
            import glob
            boat_files = glob.glob(os.path.join(self.project_root, "data", "csv", "status_barcos_*.csv"))
            if boat_files:
                latest_boat = max(boat_files)
                try:
                    with open(latest_boat, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f, delimiter=';')
                        data['boats'] = list(reader)
                except Exception as e:
                    logger.warning(f"Erro ao ler boats: {e}")
            
            intel_files = glob.glob(os.path.join(self.project_root, "data", "csv", "inteligencia_guerra_*.csv"))
            if intel_files:
                latest_intel = max(intel_files)
                try:
                    with open(latest_intel, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f, delimiter=';')
                        for row in reader:
                            cla = row.get('clan_nome') or row.get('Cla') or 'Unknown'
                            if cla not in data['rivals']:
                                data['rivals'][cla] = []
                            if len(data['rivals'][cla]) < 3:
                                data['rivals'][cla].append(row)
                except Exception as e:
                    logger.warning(f"Erro ao ler intel: {e}")
                
            my_clan = "Tropa Do Bruxo"
            try:
                players_file = os.path.join(self.project_root, "data", "csv", "players.csv")
                if os.path.exists(players_file):
                    with open(players_file, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f, delimiter=';')
                        for row in reader:
                            if row.get('player_tag'):
                                my_clan = row.get('clan_name', my_clan)
                                break
            except Exception as e:
                logger.warning(f"Erro ao ler players: {e}")
            
            data['my_clan'] = my_clan
            return data
        except Exception as e:
            logger.error(f"Erro em get_war_intelligence_data: {e}")
            return {'boats': [], 'rivals': {}, 'my_clan': 'Desconhecido'}
    
    def get_war_radar_data(self, player_tag: str = None, mode: str = 'my-war', target_date: str = None):
        """Coleta dados do radar de guerra historicos por data operacional.
        
        Retorna estrutura organizada por data contendo clans classificados e jogadores independentes.
        """
        if not player_tag:
            player_tag = self.player_tag
        
        # Calcular as 5 datas operacionais da guerra ativa atual
        now = _get_brt_now()
        if now.hour < 7:
            logical_today = now.date() - timedelta(days=1)
        else:
            logical_today = now.date()
        
        weekday = logical_today.weekday()
        if weekday >= 3:
            start_date = logical_today - timedelta(days=(weekday - 3))
        else:
            start_date = logical_today - timedelta(days=(weekday + 4))
            
        target_dates_dash = []
        target_dates_under = []
        for i in range(5):
            d = start_date + timedelta(days=i)
            target_dates_dash.append(d.strftime('%Y-%m-%d'))
            target_dates_under.append(d.strftime('%Y_%m_%d'))
            
        if target_date:
            dash = target_date.replace('_', '-')
            under = target_date.replace('-', '_')
            target_dates_dash = [dash]
            target_dates_under = [under]
            
        guerra_hist_path = os.path.join(self.project_root, "data", "csv", "guerra_historico.csv")
        clans_by_date = {}
        for u_date in target_dates_under:
            clans_by_date[u_date] = []
            
        # Tenta buscar direto do guerra_historico.csv consolidado
        if os.path.exists(guerra_hist_path):
            try:
                my_clan = ''
                my_clan_tag = ''
                try:
                    players_file = os.path.join(self.project_root, "data", "csv", "players.csv")
                    if os.path.exists(players_file):
                        with open(players_file, 'r', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f, delimiter=';')
                            for row in reader:
                                if row.get('player_tag') == player_tag:
                                    my_clan = row.get('clan_name', '')
                                    my_clan_tag = row.get('clan_tag', '')
                                    if my_clan_tag and not my_clan_tag.startswith('#'):
                                        my_clan_tag = '#' + my_clan_tag
                                    break
                except Exception as e:
                    logger.warning(f"Erro ao ler players.csv: {e}")
                    
                # Carregar registros de guerra_historico.csv
                with open(guerra_hist_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    rows = list(reader)
                
                rows = [row for row in rows if row.get('data_coleta') in target_dates_dash]
                
                # Mapear as famas acumuladas reais dos jogadores por data e player_tag
                player_tag_cums = {}  # date_dash -> player_tag_or_name -> cumulative_fame
                for row in rows:
                    dt = row.get('data_coleta', '')
                    tag = row.get('player_tag') or row.get('player_nome') or row.get('Jogador', '')
                    fame = max(
                        safe_int(row.get('player_fame') or 0),
                        safe_int(row.get('war_medals') or 0),
                        safe_int(row.get('Fama_Hoje') or 0)
                    )
                    if dt and tag:
                        if dt not in player_tag_cums:
                            player_tag_cums[dt] = {}
                        player_tag_cums[dt][tag] = fame
                
                # Vamos carregar os dados de status_barcos_historico.csv para obter a fama diária e a posição diária reais de cada clã
                clans_daily_data = {}  # date_str -> clan_nome -> {fama_diaria, posicao_diaria}
                status_hist_path = os.path.join(self.project_root, "data", "csv", "status_barcos_historico.csv")
                if os.path.exists(status_hist_path):
                    try:
                        pref_suffix = '_pri'
                        my_clan_lower = my_clan.lower() if my_clan else ''
                        if 'lendario' in my_clan_lower or 'secund' in my_clan_lower or 'bruxo 2' in my_clan_lower or (player_tag and '2220UQQ0UU' in player_tag.upper()):
                            pref_suffix = '_sec'
                        
                        conta_tipo = 'principal' if pref_suffix == '_pri' else 'secundaria'
                        
                        with open(status_hist_path, 'r', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f, delimiter=';')
                            status_rows = list(reader)
                        
                        clans_cumulative = {}  # date_str -> clan_nome -> fame_acumulada
                        for row in status_rows:
                            if row.get('conta_tipo') == conta_tipo:
                                dt = row.get('data_coleta', '')
                                dt_key = dt.replace('-', '_')
                                clan_nome = row.get('clan_nome', '')
                                if dt_key and clan_nome:
                                    if dt_key not in clans_cumulative:
                                        clans_cumulative[dt_key] = {}
                                    clans_cumulative[dt_key][clan_nome] = safe_int(row.get('fama_atual', 0))
                        
                        cron_dates = sorted(start_date + timedelta(days=i) for i in range(5))
                        for idx, day_date in enumerate(cron_dates):
                            date_str = day_date.strftime('%Y_%m_%d')
                            logical_weekday = day_date.weekday()
                            clans_daily_data[date_str] = {}
                            
                            if logical_weekday == 3: # Reset
                                if date_str in clans_cumulative:
                                    for cn in clans_cumulative[date_str].keys():
                                        clans_daily_data[date_str][cn] = {
                                            'fama_diaria': 0,
                                            'posicao_diaria': 0
                                        }
                                continue
                                
                            today_cums = clans_cumulative.get(date_str, {})
                            prev_date_str = cron_dates[idx-1].strftime('%Y_%m_%d') if idx > 0 else None
                            
                            is_prev_reset = False
                            if idx > 0 and cron_dates[idx-1].weekday() == 3:
                                is_prev_reset = True
                                
                            prev_cums = {}
                            if prev_date_str and not is_prev_reset:
                                prev_cums = clans_cumulative.get(prev_date_str, {})
                            
                            day_fames = []
                            for cn, fame_today in today_cums.items():
                                fame_prev = prev_cums.get(cn, 0)
                                fama_diaria = max(0, fame_today - fame_prev)
                                day_fames.append((cn, fama_diaria))
                            
                            sorted_day = sorted(day_fames, key=lambda x: x[1], reverse=True)
                            ranked_count = 1
                            for cn, fama in sorted_day:
                                if fama > 0:
                                    pos = ranked_count
                                    ranked_count += 1
                                else:
                                    pos = 0
                                clans_daily_data[date_str][cn] = {
                                    'fama_diaria': fama,
                                    'posicao_diaria': pos
                                }
                    except Exception as e:
                        logger.error(f"Erro ao calcular clans_daily_data em get_war_radar_data: {e}")
                
                grouped_data = {}
                for d_dash in target_dates_dash:
                    grouped_data[d_dash] = {}
                    
                for row in rows:
                    row_account = row.get('conta_tipo', '')
                    if mode == 'top-global':
                        if row_account != 'TOP_GLOBAL':
                            continue
                    else:
                        expected_accounts = []
                        if player_tag:
                            tag_clean = player_tag.strip().upper()
                            if not tag_clean.startswith('#'):
                                expected_accounts.extend([f"#{tag_clean}", tag_clean])
                            else:
                                expected_accounts.extend([tag_clean, tag_clean.replace('#', '')])
                            
                            # Suporte a base legada
                            if '2QR292P' in tag_clean:
                                expected_accounts.append('principal')
                            if '2220UQQ0UU' in tag_clean:
                                expected_accounts.append('secundaria')
                                
                        if row_account not in expected_accounts:
                            continue
                            
                    d_dash = row.get('data_coleta', '')
                    cla = row.get('clan_nome') or row.get('Cla', 'Unknown')
                    if not cla or cla.strip() == '':
                        continue
                        
                    if cla not in grouped_data[d_dash]:
                        grouped_data[d_dash][cla] = []
                    grouped_data[d_dash][cla].append(row)
                
                # --- PREENCHIMENTO DE GAPS ---
                # Caso o guerra_historico.csv não tenha os dados de d_dash (ex: Reset), buscamos os CSVs individuais
                import glob
                intel_files_found = glob.glob(os.path.join(self.project_root, "data", "csv", "inteligencia_guerra_*.csv"))
                intel_files_found = [f for f in intel_files_found if '_full_' not in f and '_pri_' not in f and '_sec_' not in f]
                
                intel_by_date = {}
                for fpath in intel_files_found:
                    fname = os.path.basename(fpath)
                    import re
                    match = re.search(r'inteligencia_guerra_(\d{4}[-_]\d{2}[-_]\d{2})\.csv', fname)
                    if match:
                        d_norm = match.group(1).replace('_', '-')
                        intel_by_date[d_norm] = fpath

                for d_dash in target_dates_dash:
                    if not grouped_data.get(d_dash):
                        fpath = intel_by_date.get(d_dash)
                        if fpath and os.path.exists(fpath):
                            try:
                                with open(fpath, 'r', encoding='utf-8-sig') as f:
                                    reader = csv.DictReader(f, delimiter=';')
                                    for row in reader:
                                        row_account = row.get('conta_tipo', '') or row.get('player_tag_conta', '')
                                        if mode == 'top-global':
                                            if row_account != 'TOP_GLOBAL':
                                                continue
                                        else:
                                            expected_accounts = []
                                            if player_tag:
                                                tag_clean = player_tag.strip().upper()
                                                if not tag_clean.startswith('#'):
                                                    expected_accounts.extend([f"#{tag_clean}", tag_clean])
                                                else:
                                                    expected_accounts.extend([tag_clean, tag_clean.replace('#', '')])
                                                if '2QR292P' in tag_clean:
                                                    expected_accounts.append('principal')
                                                if '2220UQQ0UU' in tag_clean:
                                                    expected_accounts.append('secundaria')
                                                    
                                            if expected_accounts and row_account not in expected_accounts:
                                                continue
                                                
                                        cla = row.get('clan_nome') or row.get('Cla', 'Unknown')
                                        if not cla or cla.strip() == '':
                                            continue
                                            
                                        if cla not in grouped_data[d_dash]:
                                            grouped_data[d_dash][cla] = []
                                        grouped_data[d_dash][cla].append(row)
                            except Exception as e:
                                logger.error(f"Erro ao ler {fpath} para preencher gaps: {e}")
                # -----------------------------

                cron_dates_dash = sorted(target_dates_dash)
                for d_dash, u_date in zip(target_dates_dash, target_dates_under):
                    # Obter a data anterior para o cálculo diário dos jogadores
                    try:
                        idx = cron_dates_dash.index(d_dash)
                    except:
                        idx = 0
                    
                    prev_d_dash = None
                    if idx > 0:
                        prev_d_dash = cron_dates_dash[idx-1]
                        
                    is_prev_reset = False
                    if prev_d_dash:
                        try:
                            prev_dt = datetime.strptime(prev_d_dash, '%Y-%m-%d')
                            if prev_dt.weekday() == 3:
                                is_prev_reset = True
                        except: pass

                    is_today_reset = False
                    try:
                        today_dt = datetime.strptime(d_dash, '%Y-%m-%d')
                        if today_dt.weekday() == 3:
                            is_today_reset = True
                    except: pass
                    
                    clan_list = []
                    for cla, player_rows in grouped_data[d_dash].items():
                        seen_players = {}
                        for row in player_rows:
                            player_name = row.get('player_nome') or row.get('Jogador', '')
                            player_tag_row = row.get('player_tag', '')
                            
                            # Calcular fama diária do jogador de forma robusta e livre de alucinações
                            decks_used_raw = row.get('decks_usados') or '0'
                            decks_used_num = 0
                            if '/' in str(decks_used_raw):
                                try: decks_used_num = int(str(decks_used_raw).split('/')[0])
                                except: pass
                            elif str(decks_used_raw).strip():
                                try: decks_used_num = int(decks_used_raw)
                                except: pass
                            
                            boat_num = safe_int(row.get('boat_attacks') or 0)
                            war_battles_num = safe_int(row.get('war_battles_count', 0))
                            war_vitorias_num = safe_int(row.get('war_vitorias', 0))
                            war_derrotas_num = safe_int(row.get('war_derrotas', 0))
                            
                            if is_today_reset:
                                participou_hoje = (decks_used_num > 0 or boat_num > 0 or war_battles_num > 0)
                            else:
                                participou_hoje = (decks_used_num > 0 or boat_num > 0)
                            
                            if not participou_hoje:
                                fame_daily = 0
                            else:
                                if is_today_reset:
                                    # No primeiro dia (Reset / Quinta-feira), a fama diária é a própria fama acumulada do dia
                                    fame_daily = max(
                                        safe_int(row.get('war_medals') or 0),
                                        safe_int(row.get('player_fame') or 0),
                                        safe_int(row.get('Fama_Hoje') or 0)
                                    )
                                    if fame_daily > 900 or fame_daily == 0:
                                        fame_daily = 500  # Fallback seguro para o reset
                                    elif fame_daily > 900:
                                        fame_daily = 900
                                else:
                                    # Nos demais dias (Sexta a Segunda), fazemos a subtração do acumulado da data anterior
                                    fame_today = max(
                                        safe_int(row.get('player_fame') or 0),
                                        safe_int(row.get('war_medals') or 0),
                                        safe_int(row.get('Fama_Hoje') or 0)
                                    )
                                    key_tag = player_tag_row or player_name
                                    fame_prev = 0
                                    if prev_d_dash and not is_prev_reset:
                                        prev_fames = player_tag_cums.get(prev_d_dash, {})
                                        fame_prev = prev_fames.get(key_tag, 0)
                                        if fame_prev == 0 and isinstance(key_tag, str):
                                            alt_key = key_tag.replace('#', '') if '#' in key_tag else '#' + key_tag
                                            fame_prev = prev_fames.get(alt_key, 0)
                                    fame_daily = max(0, fame_today - fame_prev)
                                    
                                    # Corrige multiplicadores exagerados e calcula fama de forma real
                                    # Se a fama diária der 0 mas o jogador participou hoje, calculamos com base nas batalhas reais
                                    if fame_daily == 0 and participou_hoje:
                                        fame_daily = (war_vitorias_num * 200) + (war_derrotas_num * 100)
                                        if fame_daily == 0:
                                            fame_daily = max(1, decks_used_num) * 100
                                    
                                    # Se o cálculo do delta falhou (ex: dia anterior sem registro) e a fama diária deu um valor
                                    # impossível (> 900), corrigimos usando as batalhas reais do dia
                                    elif fame_daily > 900:
                                        calculated_fame = (war_vitorias_num * 200) + (war_derrotas_num * 100)
                                        if calculated_fame > 0:
                                            fame_daily = calculated_fame
                                        else:
                                            fame_daily = min(900, fame_daily)
                                            if fame_daily not in [400, 500, 600, 700, 800, 900]:
                                                fame_daily = max(1, decks_used_num) * 100
                                                
                                    if fame_daily > 900:
                                        fame_daily = 900
                            
                            player_fame = fame_daily
                            clan_tag_from_row = row.get('clan_tag', '')
                            deck_1 = row.get('deck_1', '')
                            
                            ranking = safe_int(row.get('clan_posicao') or row.get('Ranking') or row.get('posicao') or row.get('ranking') or 99)
                            
                            # O jogador é participante ativo se utilizou decks ou atacou barcos
                            if is_today_reset:
                                war_participant = (decks_used_num > 0 or boat_num > 0 or war_battles_num > 0)
                            else:
                                war_participant = (decks_used_num > 0 or boat_num > 0)
                            
                            player_item = {
                                'ranking': ranking,
                                'player': player_name,
                                'fame': player_fame,
                                'date': u_date,
                                'war_participant': war_participant,
                                'lutou': "Sim" if boat_num > 0 else "Nao",
                                'ataques': f"{decks_used_raw}/4" if decks_used_raw and '/' not in str(decks_used_raw) else decks_used_raw or '0/4',
                                'deck_1': deck_1,
                                'deck_1_tipo': row.get('deck_1_tipo', 'Guerra'),
                                'deck_2': row.get('deck_2', ''),
                                'deck_2_tipo': row.get('deck_2_tipo', ''),
                                'deck_3': row.get('deck_3', ''),
                                'deck_3_tipo': row.get('deck_3_tipo', ''),
                                'deck_4': row.get('deck_4', ''),
                                'deck_4_tipo': row.get('deck_4_tipo', ''),
                                'war_vitorias': war_vitorias_num,
                                'war_derrotas': war_derrotas_num,
                                'war_medals': safe_int(row.get('war_medals', 0)),
                                'war_torre': row.get('war_torre', 'Tower Princess'),
                                'war_tipo_principal': row.get('war_tipo_principal', ''),
                                'war_battles_count': war_battles_num
                            }
                            
                            if player_name not in seen_players:
                                seen_players[player_name] = player_item
                            else:
                                existing = seen_players[player_name]
                                # Usar max em vez de sum cumulativo para blindagem contra duplicatas
                                existing['war_vitorias'] = max(existing.get('war_vitorias', 0), player_item.get('war_vitorias', 0))
                                existing['war_derrotas'] = max(existing.get('war_derrotas', 0), player_item.get('war_derrotas', 0))
                                existing['war_medals'] = max(existing.get('war_medals', 0), player_item.get('war_medals', 0))
                                existing['war_battles_count'] = max(existing.get('war_battles_count', 0), player_item.get('war_battles_count', 0))
                                if player_fame > existing['fame'] or (player_item.get('war_battles_count', 0) > 0 and not existing.get('deck_1', '')):
                                    existing['fame'] = max(existing['fame'], player_fame)
                                    if player_item.get('deck_1', ''):
                                        existing['deck_1'] = player_item['deck_1']
                                        existing['deck_1_tipo'] = player_item['deck_1_tipo']
                                        existing['deck_2'] = player_item['deck_2']
                                        existing['deck_2_tipo'] = player_item['deck_2_tipo']
                                        existing['deck_3'] = player_item['deck_3']
                                        existing['deck_3_tipo'] = player_item['deck_3_tipo']
                                        existing['deck_4'] = player_item['deck_4']
                                        existing['deck_4_tipo'] = player_item['deck_4_tipo']
                                seen_players[player_name] = existing
                        
                        sorted_players = sorted(seen_players.values(), key=lambda x: (x.get('war_participant', False), x['fame'], x.get('war_vitorias', 0), -safe_int(x.get('ranking', 99))), reverse=True)
                        clan_tag_from_data = player_rows[0].get('clan_tag', '').replace('#', '') if player_rows else ''
                        is_my_own_clan = (my_clan_tag.replace('#', '') == clan_tag_from_data)
                        max_players = 10 if (is_my_own_clan and mode == 'my-war') else 3
                        top_players = [p for p in sorted_players if p['fame'] > 0 and p.get('war_participant', False)][:max_players]
                        
                        clan_daily_fame = 0
                        if u_date in clans_daily_data:
                            for cn, daily in clans_daily_data[u_date].items():
                                if cla.lower() in cn.lower() or cn.lower() in cla.lower():
                                    clan_daily_fame = daily['fama_diaria']
                                    break
                        if clan_daily_fame == 0:
                            if is_today_reset:
                                clan_daily_fame = 0
                            else:
                                clan_daily_fame = sum(p['fame'] for p in top_players)
                                
                        metrics = self.prediction_engine.calculate_clan_metrics(player_rows, cla)
 
                        clan_list.append({
                            'name': cla,
                            'players': top_players,
                            'total_fame': clan_daily_fame,
                            'date': u_date,
                            'is_me': is_my_own_clan,
                            'decks_played': metrics['decks_played'],
                            'decks_remaining': metrics['decks_remaining'],
                            'efficiency': metrics['efficiency'],
                            'projected_fame': metrics['projected_fame']
                        })
                    
                    my_projection = 0
                    for c in clan_list:
                        if c['is_me']:
                            my_projection = c['projected_fame']
                            break
                    
                    for c in clan_list:
                        if c['is_me']:
                            c['threat_level'] = 'CONTROLADA'
                        else:
                            c['threat_level'] = self.prediction_engine.determine_threat_level(
                                rival_projection=c['projected_fame'],
                                my_projection=my_projection,
                                rival_decks_remaining=c['decks_remaining']
                            )
 
                    clan_list.sort(key=lambda x: x['total_fame'], reverse=True)
                    for idx, c in enumerate(clan_list):
                        if is_today_reset or c['total_fame'] == 0:
                            c['position'] = 0
                        else:
                            c['position'] = idx + 1
                    clans_by_date[u_date] = clan_list
                    
                total_clans = len(clans_by_date[target_dates_under[-1]]) if clans_by_date else 0
                return {
                    'clans_by_date': clans_by_date,
                    'my_clan': my_clan,
                    'total_clans': total_clans
                }
            except Exception as e:
                logger.error(f"Erro em get_war_radar_data consolidado: {e}")
                
        # Fallback legado usando glob fisico
        try:
            import glob
            my_clan = ''
            my_clan_tag = ''
            try:
                players_file = os.path.join(self.project_root, "data", "csv", "players.csv")
                if os.path.exists(players_file):
                    with open(players_file, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f, delimiter=';')
                        for row in reader:
                            if row.get('player_tag') == player_tag:
                                my_clan = row.get('clan_name', '')
                                my_clan_tag = row.get('clan_tag', '')
                                if my_clan_tag and not my_clan_tag.startswith('#'):
                                    my_clan_tag = '#' + my_clan_tag
                                break
            except Exception as e:
                logger.warning(f"Erro ao ler players.csv: {e}")
            
            intel_files_found = glob.glob(os.path.join(self.project_root, "data", "csv", "inteligencia_guerra_*.csv"))
            intel_files_found = [f for f in intel_files_found if '_full_' not in f and '_pri_' not in f and '_sec_' not in f]
            
            intel_by_date = {}
            for fpath in intel_files_found:
                fname = os.path.basename(fpath)
                import re
                match = re.search(r'inteligencia_guerra_(\d{4}[-_]\d{2}[-_]\d{2})\.csv', fname)
                if match:
                    d_norm = match.group(1).replace('_', '-')
                    intel_by_date[d_norm] = fpath
            
            for d_dash, u_date in zip(target_dates_dash, target_dates_under):
                clan_list = []
                fpath = intel_by_date.get(d_dash)
                
                if fpath and os.path.exists(fpath):
                    try:
                        with open(fpath, 'r', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f, delimiter=';')
                            rows = list(reader)
                        
                        grouped_clans = {}
                        has_tag_col = rows and 'player_tag_conta' in rows[0]
                        
                        for row in rows:
                            row_account = row.get('player_tag_conta', '')
                            if mode == 'top-global':
                                if row_account != 'TOP_GLOBAL':
                                    continue
                            else:
                                is_sec = player_tag and '2220UQQ0UU' in player_tag
                                # Aceita tanto '#2220UQQ0UU' (novo padrao) quanto '2220UQQ0UU' (registros antigos sem #)
                                expected_accounts = ['#2220UQQ0UU', '2220UQQ0UU'] if is_sec else ['#2QR292P', 'principal']
                                if has_tag_col and row_account and row_account not in expected_accounts:
                                    continue
                                    
                            cla = row.get('clan_nome') or row.get('Cla', 'Unknown')
                            if not cla or cla.strip() == '':
                                continue
                            if cla not in grouped_clans:
                                grouped_clans[cla] = []
                            grouped_clans[cla].append(row)
                            
                        for cla, player_rows in grouped_clans.items():
                            seen_players = {}
                            for row in player_rows:
                                player_name = row.get('player_nome') or row.get('Jogador', '')
                                player_fame = safe_int(row.get('player_fame') or row.get('Fama_Hoje', 0))
                                clan_tag_from_row = row.get('clan_tag', '')
                                decks_used_raw = row.get('decks_usados') or '0'
                                boat_attacks = row.get('boat_attacks', '0')
                                deck_1 = row.get('deck_1', '')
                                
                                ranking = safe_int(row.get('clan_posicao') or row.get('Ranking', 99), 99)
                                
                                decks_used_num = 0
                                if '/' in str(decks_used_raw):
                                    try: decks_used_num = int(str(decks_used_raw).split('/')[0])
                                    except: pass
                                elif str(decks_used_raw).strip():
                                    try: decks_used_num = int(decks_used_raw)
                                    except: pass
                                boat_num = safe_int(boat_attacks)
                                war_battles_num = safe_int(row.get('war_battles_count', 0))
                                war_vitorias_num = safe_int(row.get('war_vitorias', 0))
                                war_derrotas_num = safe_int(row.get('war_derrotas', 0))
                                
                                if is_today_reset:
                                    participou_hoje = (decks_used_num > 0 or boat_num > 0 or war_battles_num > 0)
                                else:
                                    participou_hoje = (decks_used_num > 0 or boat_num > 0)
                                
                                if not participou_hoje:
                                    war_participant = False
                                else:
                                    war_participant = True
                                
                                player_item = {
                                    'ranking': ranking,
                                    'player': player_name,
                                    'fame': player_fame,
                                    'date': u_date,
                                    'war_participant': war_participant,
                                    'lutou': "Sim" if boat_num > 0 else "Nao",
                                    'ataques': f"{decks_used_raw}/4" if decks_used_raw and '/' not in str(decks_used_raw) else decks_used_raw or '0/4',
                                    'deck_1': deck_1,
                                    'deck_1_tipo': row.get('deck_1_tipo', 'Guerra'),
                                    'deck_2': row.get('deck_2', ''),
                                    'deck_2_tipo': row.get('deck_2_tipo', ''),
                                    'deck_3': row.get('deck_3', ''),
                                    'deck_3_tipo': row.get('deck_3_tipo', ''),
                                    'deck_4': row.get('deck_4', ''),
                                    'deck_4_tipo': row.get('deck_4_tipo', ''),
                                    'war_vitorias': safe_int(row.get('war_vitorias', 0)),
                                    'war_derrotas': safe_int(row.get('war_derrotas', 0)),
                                    'war_medals': safe_int(row.get('war_medals', 0)),
                                    'war_torre': row.get('war_torre', 'Tower Princess'),
                                    'war_tipo_principal': row.get('war_tipo_principal', ''),
                                    'war_battles_count': safe_int(row.get('war_battles_count', 0))
                                }
                                
                                if player_name not in seen_players:
                                    seen_players[player_name] = player_item
                                else:
                                    existing = seen_players[player_name]
                                    # Usar max em vez de sum cumulativo para blindagem contra duplicatas
                                    existing['war_vitorias'] = max(existing.get('war_vitorias', 0), player_item.get('war_vitorias', 0))
                                    existing['war_derrotas'] = max(existing.get('war_derrotas', 0), player_item.get('war_derrotas', 0))
                                    existing['war_medals'] = max(existing.get('war_medals', 0), player_item.get('war_medals', 0))
                                    existing['war_battles_count'] = max(existing.get('war_battles_count', 0), player_item.get('war_battles_count', 0))
                                    if player_fame > existing['fame'] or (player_item.get('war_battles_count', 0) > 0 and not existing.get('deck_1', '')):
                                        existing['fame'] = max(existing['fame'], player_fame)
                                        if player_item.get('deck_1', ''):
                                            existing['deck_1'] = player_item['deck_1']
                                            existing['deck_1_tipo'] = player_item['deck_1_tipo']
                                            existing['deck_2'] = player_item['deck_2']
                                            existing['deck_2_tipo'] = player_item['deck_2_tipo']
                                            existing['deck_3'] = player_item['deck_3']
                                            existing['deck_3_tipo'] = player_item['deck_3_tipo']
                                            existing['deck_4'] = player_item['deck_4']
                                            existing['deck_4_tipo'] = player_item['deck_4_tipo']
                                    seen_players[player_name] = existing
                            
                            sorted_players = sorted(seen_players.values(), key=lambda x: (x.get('war_participant', False), x['fame'], x.get('war_vitorias', 0), -safe_int(x.get('ranking', 99))), reverse=True)
                            clan_tag_from_data = player_rows[0].get('clan_tag', '').replace('#', '') if player_rows else ''
                            is_my_own_clan = (my_clan_tag.replace('#', '') == clan_tag_from_data)
                            max_players = 10 if (is_my_own_clan and mode == 'my-war') else 3
                            top_players = [p for p in sorted_players if p['fame'] > 0 and p.get('war_participant', False)][:max_players]
                            
                            total_fame = sum(p['fame'] for p in top_players)
                            
                            clan_list.append({
                                'name': cla,
                                'players': top_players,
                                'total_fame': total_fame,
                                'date': u_date,
                                'is_me': is_my_own_clan
                            })
                    except Exception as e:
                        logger.error(f"Erro ao ler fpath {fpath} no radar de guerra fallback: {e}")
                
                clan_list.sort(key=lambda x: x['total_fame'], reverse=True)
                for idx, c in enumerate(clan_list):
                    c['position'] = idx + 1
                clans_by_date[u_date] = clan_list
                
            total_clans = len(clans_by_date[target_dates_under[-1]]) if clans_by_date else 0
            return {
                'clans_by_date': clans_by_date,
                'my_clan': my_clan,
                'total_clans': total_clans
            }
        except Exception as e:
            logger.error(f"Erro geral em get_war_radar_data fallback: {e}")
            return {
                'clans_by_date': clans_by_date,
                'my_clan': 'Desconhecido',
                'total_clans': 0
            }
    
    def _generate_war_calendar_html(self, day_history: List[Dict], my_clan: str, tab_id: str) -> str:
        """Gera o HTML do calendário de dias de guerra com timeline horizontal reduzida (apenas as datas)."""
        if not day_history:
            return ""
        
        days_html = ""
        for entry in day_history[:5]:  # Limita a 5 dias operacionais (Reset a Dia 4)
            date = entry['date']
            label = entry.get('label', date)
            is_active = entry.get('is_active', False)
            position = entry.get('position', 0)
            fame = entry.get('fame', 0)
            
            # Recuperar outras métricas se disponíveis (para o JS usar depois)
            decks_played = entry.get('decks_played', 0)
            decks_remaining = entry.get('decks_remaining', 200)
            efficiency = entry.get('efficiency', 0.0)
            projected_fame = entry.get('projected_fame', 0)
            
            active_class = "rd-calendar-day-active" if is_active else ""
            
            # Formatação do ícone de medalha baseado na posição
            medal_icon = ""
            if position == 1:
                medal_icon = "🥇"
            elif position == 2:
                medal_icon = "🥈"
            elif position == 3:
                medal_icon = "🥉"
            elif position > 0:
                medal_icon = "🏅"
                
            pos_text = f"#{position}" if position > 0 else "#—"
            fame_text = f"{fame:,}".replace(',', '.') if fame > 0 else "0"
            status_text = "Sem dados" if fame == 0 else ""
            
            days_html += f"""
                <div class="rd-calendar-day {active_class}" 
                     onclick="selectWarDay('{tab_id}', '{date}', this)"
                     data-date="{date}" data-position="{position}" data-fame="{fame}"
                     data-decks-played="{decks_played}" data-decks-remaining="{decks_remaining}"
                     data-efficiency="{efficiency}" data-projected-fame="{projected_fame}">
                    <div class="rd-calendar-label">{label}</div>
                    <div class="rd-calendar-medal">{medal_icon}</div>
                    <div class="rd-calendar-pos">{pos_text}</div>
                    <div class="rd-calendar-fame">⚔ {fame_text}</div>
                    <div class="rd-calendar-boat">⚓</div>
                    <div class="rd-calendar-status">{status_text}</div>
                </div>
            """
            
        my_clan_safe = my_clan.replace("'", "\\'")
        return f"""
                <div class="rd-calendar-title">&#x1F4C5; Calendario Guerra - {my_clan_safe}</div>
                <div class="rd-calendar-timeline">
                    {days_html}
                </div>
        """
        
    def generate_war_radar_html(self, data, player_tag: str = None, tab_id: str = None):
        """Gera o HTML para a secao de Radar de Guerra (grids independentes por dia operacional).
        
        Args:
            data: Dados dos clans e jogadores estruturados por clans_by_date
            player_tag: Tag do jogador para identificar conta
            tab_id: ID da tab (pri/sec)
        """
        if tab_id is None:
            tab_id = "pri" if player_tag and '2QR292P' in player_tag else "sec"
        
        if not data.get('clans_by_date'):
            return {'content': '', 'tab': '', 'tab_id': tab_id}
        
        # Alinhamento do dia da semana de acordo com o corte operacional das 7:00 da manha
        now = _get_brt_now()
        if now.hour < 7:
            logical_today = now.date() - timedelta(days=1)
        else:
            logical_today = now.date()
        weekday = logical_today.weekday()
        war_day_map = {3: "Reset", 4: "Dia 1", 5: "Dia 2", 6: "Dia 3", 0: "Dia 4"}
        day_suffix = f": {war_day_map[weekday]}" if weekday in war_day_map else ""
        
        # Nome da conta para a tab
        account_label = "CONTA PRINCIPAL" if player_tag and '2QR292P' in player_tag else "CONTA SECUNDÁRIA"
        
        # Identificar clan da conta para usar no calendario
        my_clan = data.get('my_clan', '')
        
        # Gerar calendario de dias de guerra usando dados processados
        calendar_html = ""
        if not my_clan:
            # Fallback se nao achou my_clan
            my_clan = "Tropa Do Bruxo"
            
        calendar_data = self.get_war_calendar_data(my_clan, 5, '', player_tag=player_tag)
        if calendar_data:
            calendar_html = self._generate_war_calendar_html(calendar_data, my_clan, tab_id)
            
        today_str = logical_today.strftime('%Y_%m_%d')
        
        # Achar a Quinta-feira operacional de inicio da guerra para gerar exatamente as 5 divs de grids
        if weekday >= 3:
            start_date = logical_today - timedelta(days=(weekday - 3))
        else:
            start_date = logical_today - timedelta(days=(weekday + 4))
            
        war_dates = []
        for i in range(5):
            war_dates.append((start_date + timedelta(days=i)).strftime('%Y_%m_%d'))
            
        grids_html = ""
        clans_by_date = data.get('clans_by_date', {})
        
        for date_str in war_dates:
            clans_list = clans_by_date.get(date_str, [])
            grid_id = f"rd-grid-{tab_id}-{date_str}"
            
            clan_cards_html = ""
            if clans_list:
                for clan in clans_list:
                    is_me = clan.get('is_me', False)
                    me_class = "rd-clan-me" if is_me else ""
                    me_badge = "<span class='rd-me-badge'>MEU CLÃ</span>" if is_me else ""
                    
                    player_rows_html = ""
                    for p in clan.get('players', []):
                        # Pular jogadores sem participacao real e sem fama (inativos)
                        if not p.get('war_participant', False) and p.get('fame', 0) == 0:
                            continue
                        
                        lutou_icon = "🔴" if p.get('lutou', '').lower() == 'sim' else "⚪"
                        attacks = p.get('ataques', '0/4')
                        fame = p.get('fame', 0)
                        ranking = p.get('ranking', '-')
                        player_name = p.get('player', '')
                        
                        deck_rows_html = ""
                        valid_deck_count = 0
                        for d in range(1, 5):
                            deck = p.get(f'deck_{d}', '')
                            deck_tipo = p.get(f'deck_{d}_tipo', 'Batalha')
                            if deck and deck != 'Deck nao encontrado no log recente' and deck != 'N/A' and deck.strip() != 'N/A' and deck.strip():
                                cards = [c.strip() for c in deck.split(',') if c.strip()][:8]
                                cards_row1 = cards[:4]
                                cards_row2 = cards[4:8]
                                cards_imgs = ""
                                for card in cards_row1:
                                    cards_imgs += f'<div class="cr-card-wrap-premium rd-card"><img src="{self.get_card_image_path(card)}" alt="{card}" title="{card}"></div>'
                                cards_imgs += '<div class="rd-deck-break"></div>'
                                for card in cards_row2:
                                    cards_imgs += f'<div class="cr-card-wrap-premium rd-card"><img src="{self.get_card_image_path(card)}" alt="{card}" title="{card}"></div>'
                                
                                tipo_icon = {
                                    'Guerra': '⚔️',
                                    'Barco': '🚣',
                                    'Range Battle': '🎯',
                                    'Duelo': '⚡'
                                }.get(deck_tipo, '🛡️')
                                
                                copy_link = self.get_copy_deck_link(cards)
                                btn_html = f'<button type="button" onclick="copyDeckLink(event, this, \'{copy_link}\')" class="cr-copy-btn-v2" style="border: none; padding: 4px 8px; cursor: pointer; background: transparent; margin-left: 8px;" title="Copiar/Compartilhar"><img src="https://media.ffycdn.net/eu/supercell/jsmnnT9Z8mF79QiwDcsW.png?width=2400" alt="Copiar Deck" style="height: 28px; vertical-align: middle;"></button>'
                                
                                deck_label = f'<div class="rd-deck-label" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">{tipo_icon} Deck {d} ({deck_tipo}){btn_html}</div>'
                                deck_rows_html += f'<div class="rd-deck-row">{deck_label}<div class="rd-deck">{cards_imgs}</div></div>'
                                valid_deck_count += 1
                        
                        if not deck_rows_html:
                            deck_rows_html = '<div class="rd-no-deck">Sem decks recentes</div>'
                        
                        player_rows_html += f"""
                            <div class="rd-player" data-date="{p.get('date', date_str)}">
                                <div class="rd-player-header">
                                    <span class="rd-rank">#{ranking}</span>
                                    <span class="rd-name">{player_name}</span>
                                    <span class="rd-fame">+{fame}</span>
                                    <span class="rd-lutou" title="Lutou hoje">{lutou_icon}</span>
                                    <span class="rd-attacks">{attacks}</span>
                                </div>
                                <div class="rd-player-stats">
                                    <span class="rd-stat rd-vitorias" title="Vitórias de guerra">🏆 {p.get('war_vitorias', 0)}</span>
                                    <span class="rd-stat rd-derrotas" title="Derrotas de guerra">💔 {p.get('war_derrotas', 0)}</span>
                                    <span class="rd-stat rd-medals" title="Medals ganhos">🏅 {p.get('war_medals', 0)}</span>
                                    <span class="rd-stat rd-battles" title="Total de batalhas">⚔️ {p.get('war_battles_count', 0)}</span>
                                    <span class="rd-stat rd-torre" title="Torre do jogador">🏰 {p.get('war_torre', 'Tower Princess')}</span>
                                </div>
                                <div class="rd-decks">
                                    {deck_rows_html}
                                </div>
                                <div class="rd-deck-count">{valid_deck_count}/4 decks</div>
                            </div>
                        """
                    
                    total_fame = clan.get('total_fame', 0)
                    position = clan.get('position', '?')
                    clan_name = clan.get('name', '')
                    
                    decks_played = clan.get('decks_played', 0)
                    efficiency = clan.get('efficiency', 0.0)
                    projected_fame = clan.get('projected_fame', 0)
                    threat_level = clan.get('threat_level', 'CONTROLADA')
                    
                    # Definir badge de ameaca e cores neon para rivais
                    threat_badge = ""
                    if not is_me:
                        threat_colors = {
                            'CRITICA': 'rd-threat-critical',
                            'MODERADA': 'rd-threat-moderate',
                            'CONTROLADA': 'rd-threat-controlled'
                        }
                        t_class = threat_colors.get(threat_level, 'rd-threat-controlled')
                        threat_badge = f'<span class="rd-threat-badge {t_class}">{threat_level}</span>'
                    
                    metrics_bar_html = f"""
                    <div class="rd-clan-metrics-bar">
                        <div class="rd-clan-metric-item" title="Eficiencia de vitoria">
                            <span class="rd-metric-icon">⚡</span>
                            <span class="rd-metric-val">{efficiency:.1f}%</span>
                        </div>
                        <div class="rd-clan-metric-item" title="Decks jogados de 200">
                            <span class="rd-metric-icon">🎴</span>
                            <span class="rd-metric-val">{decks_played}/200</span>
                        </div>
                        {"" if is_me else f'''
                        <div class="rd-clan-metric-item" title="Fama projetada no final do dia">
                            <span class="rd-metric-icon">🔮</span>
                            <span class="rd-metric-val">{projected_fame:,} ⭐</span>
                        </div>
                        '''}
                        {threat_badge}
                    </div>
                    """
                    
                    clan_cards_html += f"""
                        <div class="rd-clan {me_class}">
                            <div class="rd-clan-header">
                                <span class="rd-pos">{f"#{position}" if safe_int(position) > 0 else "—"}</span>
                                <span class="rd-clan-name">{clan_name}</span>
                                {me_badge}
                                <span class="rd-clan-fame">{total_fame:,} ⭐</span>
                            </div>
                            {metrics_bar_html}
                            <div class="rd-players">
                                {player_rows_html}
                            </div>
                        </div>
                    """
            else:
                clan_cards_html = '<div class="rd-no-data">Sem dados registrados para este dia de guerra</div>'
                
            grids_html += f"""
                <div id="{grid_id}" class="rd-grid-day rd-my-war-grid-day" style="display: none;">
                    <div class="rd-grid">
                        {clan_cards_html}
                    </div>
                </div>
            """
            
        # Adicionar tab para esta conta
        tab_html = f"""
            <button class="rd-tab" onclick="switchRadarTab('{tab_id}', this)" data-tag="{player_tag}">
                {account_label}
            </button>
        """
        
        content_html = f"""
            <div id="rd-content-{tab_id}" class="rd-content">
                <div class="rd-calendar-container" id="rd-calendar-{tab_id}">
                    {calendar_html}
                    
                    <!-- Analytics Cards Logo Abaixo do Calendário -->
                    <div class="rd-analytics-cards" id="rd-analytics-cards-{tab_id}">
                        <div class="rd-card-premium rd-decks-card">
                            <div class="rd-card-glow"></div>
                            <div class="rd-card-icon">🎴</div>
                            <div class="rd-card-details">
                                <span class="rd-card-title">Decks Utilizados</span>
                                <span class="rd-card-value" id="rd-decks-value-{tab_id}">0 / 200</span>
                                <span class="rd-card-sub" id="rd-decks-sub-{tab_id}">200 restantes</span>
                            </div>
                        </div>
                        
                        <div class="rd-card-premium rd-efficiency-card">
                            <div class="rd-card-glow"></div>
                            <div class="rd-card-icon">⚡</div>
                            <div class="rd-card-details">
                                <span class="rd-card-title">Eficiencia Media</span>
                                <span class="rd-card-value" id="rd-efficiency-value-{tab_id}">0.0%</span>
                                <span class="rd-card-sub">Baseada em vitorias</span>
                            </div>
                        </div>
                        
                        <div class="rd-card-premium rd-projection-card">
                            <div class="rd-card-glow"></div>
                            <div class="rd-card-icon">🔮</div>
                            <div class="rd-card-details">
                                <span class="rd-card-title">Projecao de Fama</span>
                                <span class="rd-card-value" id="rd-projection-value-{tab_id}">0 ⭐</span>
                                <span class="rd-card-sub">Estimativa matematica</span>
                            </div>
                        </div>
                    </div>

                    <div id="rd-war-summary-{tab_id}" class="rd-war-summary" style="display: none; margin-top: 15px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 12px;">
                        <div class="rd-war-summary-inner" style="justify-content: center;">
                            <span class="rd-war-summary-label">📅 Dia selecionado:</span>
                            <span id="rd-summary-date-{tab_id}" class="rd-war-summary-date">—</span>
                            <span class="rd-war-summary-sep">|</span>
                            <span class="rd-war-summary-label">🏆 Posicao:</span>
                            <span id="rd-summary-pos-{tab_id}" class="rd-war-summary-pos">—</span>
                            <span class="rd-war-summary-sep">|</span>
                            <span class="rd-war-summary-label">⭐ Fama:</span>
                            <span id="rd-summary-fame-{tab_id}" class="rd-war-summary-fame">—</span>
                        </div>
                    </div>
                </div>

                <div id="rd-day-content-{tab_id}" class="cr-war-content-area" style="margin-top: 15px;">
                        
                        <!-- rd-war-summary movido para o rd-calendar-container -->



                        <div class="rd-header">
                            <div class="rd-badge">RADAR DE GUERRA</div>
                            <h2>📡 Radar TOP Global WAR{day_suffix}</h2>
                            <div class="rd-legend">
                                <span class="rd-legend-item"><span class="rd-legend-dot rd-red"></span> Lutou hoje</span>
                                <span class="rd-legend-item"><span class="rd-legend-dot rd-gray"></span> Nao lutou</span>
                                <span class="rd-legend-item">|</span>
                                <span class="rd-legend-item">5 clans Top 5 players 4 decks Stats</span>
                            </div>
                        </div>
                        <div class="rd-mode-selector">
                            <button class="rd-mode-btn rd-mode-active" onclick="toggleWarMode('{tab_id}', 'my-war', this)">Meu Cla TOP 10</button>
                            <button class="rd-mode-btn" onclick="toggleWarMode('{tab_id}', 'global', this)">TOP 3 Todos</button>
                        </div>
                        
                        <div class="rd-grids-wrapper">
                            <div class="rd-my-war-container">
                                {grids_html}
                            </div>
                            <div class="rd-global-container" style="display: none;">
                            </div>
                        </div>
                    </div>
                </div>
        """
        
        return {'content': content_html, 'tab': tab_html, 'tab_id': tab_id}

    def generate_war_intelligence_html(self, data):
        """Gera o HTML para a seção de Inteligência de Guerra."""
        if not data.get('boats'):
            return ""
        
        # Meta de fama (ex: 50.000 para terminar a corrida)
        FAME_GOAL = 50000
        
        # Calculo de vantagem estrategica para alertas taticos
        my_fame = 0
        my_clan = data.get('my_clan') or 'Desconhecido'
        for b in data['boats']:
            if b.get('Nome_Cla') == my_clan:
                try:
                    my_fame = int(b.get('Fama_Atual', '0').replace(',', '').replace('.', ''))
                except: pass
                break
        
        # Detecção de Reset da Temporada (Primeira segunda-feira do mês)
        is_reset_day = False
        today_dt = _get_brt_now()
        if today_dt.weekday() == 0 and today_dt.day <= 7:
            is_reset_day = True

        intel_alerts = ""
        if is_reset_day:
            intel_alerts += f"<div class='intel-alert' style='background: #fef3c7; border-left: 4px solid #d97706; color: #92400e;'><strong>[RESET]</strong> Temporada nova iniciada! Foco em subir trofeus e garantir as primeiras vitorias na guerra.</div>"

        for b in data.get('boats', []):
            if b.get('Nome_Cla') != my_clan:
                try:
                    rival_fame = int(b.get('Fama_Atual', '0').replace(',', '').replace('.', ''))
                    diff_val = my_fame - rival_fame
                    if diff_val > 0:
                        intel_alerts += f"<div class='intel-alert positive'>Vantagem de <strong>{diff_val:,}</strong> sobre {b.get('Nome_Cla')}</div>"
                    else:
                        intel_alerts += f"<div class='intel-alert negative'>Atras de {b.get('Nome_Cla')} por <strong>{abs(diff_val):,}</strong></div>"
                except: pass

        boat_rows = ""
        for b in data.get('boats', []):
            is_me = "highlight-row" if b.get('Nome_Cla') == my_clan else ""
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
                    <td style="text-align: center;">{"[OK]" if b.get('Finalizado') == 'Sim' else "[ ]"}</td>
                </tr>
            """
            
        rival_cards = ""
        for cla, players in data.get('rivals', {}).items():
            if cla == my_clan: continue
            
            player_list = "".join([f"<li><span class='rival-name'>{p.get('Jogador') or p.get('player_nome') or 'N/A'}</span> <span class='rival-fame'>+{p.get('Fama_Hoje') or p.get('player_fame') or 0}</span></li>" for p in players])
            rival_cards += f"""
                <div class="rival-mini-card">
                    <h4>{cla}</h4>
                    <ul>{player_list}</ul>
                </div>
            """
            
        # Titulo dinamico baseado no dia da semana (Guerra: Qui=3 a Dom=6 + Seg=0 para Reset)
        now = _get_brt_now()
        if now.hour < 7:
            logical_today = now.date() - timedelta(days=1)
        else:
            logical_today = now.date()
        logical_weekday = logical_today.weekday()
        war_day_map = {3: "Reset", 4: "Dia 1", 5: "Dia 2", 6: "Dia 3", 0: "Dia 4"}
        day_suffix = f": {war_day_map[logical_weekday]}" if logical_weekday in war_day_map else ""

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
                
/* WAR RADAR CSS - Movido para base para garantir disponibilidade */
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
                        <button type="button" onclick="copyDeckLink(event, this, '{copy_link}')" class="cr-copy-btn-v2" style="border: none; padding: 4px 8px; cursor: pointer; background: transparent;">
                            <img src="https://media.ffycdn.net/eu/supercell/jsmnnT9Z8mF79QiwDcsW.png?width=2400" alt="Copiar Deck" style="height: 28px; vertical-align: middle;">
                        </button>
                    </div>
                    <div class="cr-side-container">
                        <div class="cr-tower-floating left">
                            <div class="cr-tower-badge">LV 15</div>
                            <img src="./princesa-tropa-de-torre-clash-royale.png" class="cr-tower-img-v2">
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
                        <button type="button" onclick="copyDeckLink(event, this, '{copy_link}')" class="cr-copy-btn-v2" style="border: none; padding: 4px 8px; cursor: pointer; background: transparent;">
                            <img src="https://media.ffycdn.net/eu/supercell/jsmnnT9Z8mF79QiwDcsW.png?width=2400" alt="Copiar Deck" style="height: 28px; vertical-align: middle;">
                        </button>
                    </div>
                    <div class="cr-side-container">
                        <div class="cr-tower-floating left">
                            <div class="cr-tower-badge">LV 15</div>
                            <img src="./princesa-tropa-de-torre-clash-royale.png" class="cr-tower-img-v2">
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

    
    def generate_chests_html(self, chests_data: List[Dict] = None) -> str:
        """Gera o HTML para a seção de próximos baús."""
        chests = chests_data if chests_data is not None else self.upcoming_chests
        if not chests:
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
        """Gera o relatório HTML completo consolidando todas as seções e múltiplas contas."""
        try:
            account_tabs_html = '<div class="cr-account-tabs">'
            account_contents_html = ''
            
            for idx, tag in enumerate(self.tracked_tags):
                try:
                    stats = self.get_player_stats(tag)
                    if not stats:
                        # Fallback critico: cria stats minimo para nao perder a conta no HTML
                        battles = self.battles_by_tag.get(tag, [])
                        if battles:
                            stats = {
                                'player_tag': tag,
                                'name': f'Conta {tag[-4:]}',
                                'trophies': 0,
                                'best_trophies': 0,
                                'level': 0,
                                'clan_tag': '',
                                'clan_name': '',
                                'last_updated': datetime.now(UTC).isoformat(),
                                'total_battles': len(battles),
                                'wins': sum(1 for b in battles if b.get('result') == 'victory'),
                                'losses': sum(1 for b in battles if b.get('result') == 'defeat'),
                                'draws': sum(1 for b in battles if b.get('result') == 'draw'),
                                'total_trophy_change': 0,
                                'last_battle': battles[0].get('battle_time', ''),
                                'first_battle': battles[-1].get('battle_time', '')
                            }
                            logger.warning(f"Conta {tag} usando stats fallback: {len(battles)} batalhas")
                        else:
                            logger.error(f"Conta {tag} SEM batalhas e SEM stats, pulando")
                            continue
                    
                    logger.info(f"Conta {tag} ({stats['name']}) processada: {stats['total_battles']} batalhas")
                    
                    is_active = (idx == 0)
                    active_class = 'active' if is_active else ''
                    clean_tag = tag.replace('#', '')
                    
                    # Tab Header
                    label = "CONTA PRINCIPAL" if idx == 0 else "CONTA SECUNDÁRIA"
                    icon = "fa-user-shield" if idx == 0 else "fa-user-ninja"
                    account_tabs_html += f'<div class="cr-tab {active_class}" onclick="switchAccountTab(\'{tag}\', this)"><i class="fas {icon}"></i> <span>{label}</span><small style="opacity: 0.7; font-size: 0.8em; margin-left: 8px;">({stats["name"]})</small></div>'
                    
                    # Tab Content
                    content_html = self._generate_account_content_html(tag, stats)
                    
                    # Radar de Guerra
                    try:
                        radar_data = self.get_war_radar_data(tag)
                        tab_id = "pri" if idx == 0 else "sec"
                        radar_result = self.generate_war_radar_html(radar_data, tag, tab_id)
                        radar_content = radar_result['content']
                        if radar_content:
                            content_html += f'<div class="section"><h2 class="clash-font" style="margin-bottom: 20px;">🎯 Radar de Guerra</h2>{radar_content}</div>'
                    except Exception as e:
                        logger.error(f"Error generating war radar for {tag}: {e}")
                        
                    account_contents_html += f'<div id="account-tab-{clean_tag}" class="cr-tab-content {active_class}">{content_html}</div>'
                except Exception as e:
                    logger.error(f"Error processing account {tag}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            account_tabs_html += '</div>'
            
            # Global Sections - with granular try-except
            clan_member_activity_html = ""
            try:
                clan_members = self.get_clan_members()
                deck_analytics = self.get_clan_deck_analytics()
                clan_member_activity_html = self.generate_clan_member_activity_html(clan_members, deck_analytics, "")
            except Exception as e:
                logger.error(f"Error generating clan activity: {e}")

            war_intel_html = ""

            war_radar_html = ""
            top_global_script = ""
            try:
                # Gerar dados do TOP Global
                top_global_data = self.get_war_radar_data(None, mode='top-global')
                if top_global_data.get('clans_by_date'):
                    tab_id_for_js = "pri" if len(self.tracked_tags) == 1 else "sec"
                    top_global_json = json.dumps(top_global_data.get('clans_by_date', {}), ensure_ascii=False)
                    
                    # Criar mapeamento de imagens de cartas para o JavaScript
                    card_img_paths = {}
                    card_ids_map = {}
                    for card_name in self.cards_master.keys():
                        img_path = self.get_card_image_path(card_name)
                        card_img_paths[card_name] = img_path
                        info = self.cards_master.get(card_name)
                        if info and 'card_id' in info:
                            card_ids_map[card_name] = str(info['card_id'])
                    card_img_json = json.dumps(card_img_paths, ensure_ascii=False)
                    card_ids_json = json.dumps(card_ids_map, ensure_ascii=False)
                    
                    top_global_script = f"""
                        <script>
                            window.TOP_GLOBAL_DATA = {top_global_json};
                            window.CARD_IMAGE_PATHS = {card_img_json};
                            window.CARD_IDS = {card_ids_json};
                            function toggleWarMode(tabId, mode, btn) {{
                                var parent = document.getElementById('rd-day-content-' + tabId);
                                if (!parent) return;
                                
                                parent.querySelectorAll('.rd-mode-btn').forEach(function(b) {{ b.classList.remove('rd-mode-active'); }});
                                btn.classList.add('rd-mode-active');
                                
                                var grids = parent.querySelectorAll('.rd-grid-day');
                                grids.forEach(function(g) {{ g.style.display = 'none'; }});
                                
                                var activeDate = document.getElementById('rd-summary-date-' + tabId).textContent.replace(/-/g, '_');
                                
                                if (mode === 'global') {{
                                    var myWarContainer = parent.querySelector('.rd-my-war-container');
                                    if (myWarContainer) myWarContainer.style.display = 'none';
                                    
                                    var globalContainer = parent.querySelector('.rd-global-container');
                                    if (globalContainer) {{
                                        globalContainer.style.display = 'block';
                                        renderTopGlobal(tabId, activeDate);
                                    }}
                                }} else {{
                                    var globalContainer = parent.querySelector('.rd-global-container');
                                    if (globalContainer) globalContainer.style.display = 'none';
                                    
                                    var myWarContainer = parent.querySelector('.rd-my-war-container');
                                    if (myWarContainer) myWarContainer.style.display = 'block';
                                    
                                    var target = document.getElementById('rd-grid-' + tabId + '-' + activeDate);
                                    if (target) target.style.display = 'block';
                                }}
                            }}
                            function renderTopGlobal(tabId, activeDate) {{
                                var parent = document.getElementById('rd-day-content-' + tabId);
                                var grid = parent.querySelector('.rd-global-container');
                                if (!grid || !window.TOP_GLOBAL_DATA) return;
                                grid.innerHTML = '';
                                
                                var clansForDate = window.TOP_GLOBAL_DATA[activeDate] || [];
                                if (clansForDate.length === 0) {{
                                    grid.innerHTML = '<div class="rd-no-data">Sem dados registrados para este dia de guerra</div>';
                                    return;
                                }}
                                
                                var html = '<div class="rd-grid">';
                                clansForDate.forEach(function(clan) {{
                                    var playersHtml = '';
                                    clan.players.forEach(function(p) {{
                                        var decksHtml = '';
                                        for (var d = 1; d <= 4; d++) {{
                                            var deck = p['deck_' + d];
                                            if (deck && deck.trim() && deck !== 'Deck nao encontrado no log recente') {{
                                                var cards = deck.split(',').map(function(c) {{ return c.trim(); }}).filter(function(c) {{ return c; }}).slice(0, 8);
                                                var row1 = cards.slice(0, 4);
                                                var row2 = cards.slice(4, 8);
                                                var tipo = p['deck_' + d + '_tipo'] || 'Batalha';
                                                var tipoIcon = {{'Guerra': '⚔️', 'Barco': '🚣', 'Range Battle': '🎯', 'Duelo': '⚡'}}[tipo] || '🛡️';
                                                var deckCardIds = [];
                                                cards.forEach(function(c) {{
                                                    if(window.CARD_IDS && window.CARD_IDS[c]) {{
                                                        deckCardIds.push(window.CARD_IDS[c]);
                                                    }}
                                                }});
                                                var copyLink = deckCardIds.length >= 8 ? 'https://link.clashroyale.com/pt/?clashroyale://copyDeck?deck=' + deckCardIds.join(';') + '&l=Royals&tt=159000000' : '#';
                                                var copyBtnHtml = '<button type="button" onclick="copyDeckLink(event, this, \\'' + copyLink + '\\')" class="cr-copy-btn-v2" style="border: none; padding: 4px 8px; cursor: pointer; background: transparent; margin-left: 8px;" title="Copiar/Compartilhar"><img src="https://media.ffycdn.net/eu/supercell/jsmnnT9Z8mF79QiwDcsW.png?width=2400" alt="Copiar Deck" style="height: 28px; vertical-align: middle;"></button>';
                                                decksHtml += '<div class="rd-deck-row"><div class="rd-deck-label" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">' + tipoIcon + ' Deck ' + d + ' (' + tipo + ')' + copyBtnHtml + '</div><div class="rd-deck">';
                                                row1.forEach(function(card) {{
                                                    var imgPath = window.CARD_IMAGE_PATHS && window.CARD_IMAGE_PATHS[card];
                                                    var imgTag = imgPath 
                                                        ? '<img src="' + imgPath + '" alt="' + card + '" title="' + card + '">' 
                                                        : '<span class="rd-card-text">' + card + '</span>';
                                                    decksHtml += '<div class="cr-card-wrap-premium rd-card">' + imgTag + '</div>';
                                                }});
                                                decksHtml += '<div class="rd-deck-break"></div>';
                                                row2.forEach(function(card) {{
                                                    var imgPath = window.CARD_IMAGE_PATHS && window.CARD_IMAGE_PATHS[card];
                                                    var imgTag = imgPath 
                                                        ? '<img src="' + imgPath + '" alt="' + card + '" title="' + card + '">' 
                                                        : '<span class="rd-card-text">' + card + '</span>';
                                                    decksHtml += '<div class="cr-card-wrap-premium rd-card">' + imgTag + '</div>';
                                                }});
                                                decksHtml += '</div></div>';
                                            }}
                                        }}
                                        var lutouIcon = p.lutou === 'Sim' ? '🔴' : '⚪';
                                        var warStats = '<div class="rd-player-stats">' +
                                            '<span class="rd-stat rd-vitorias">🏆 ' + p.war_vitorias + '</span>' +
                                            '<span class="rd-stat rd-derrotas">💔 ' + p.war_derrotas + '</span>' +
                                            '<span class="rd-stat rd-medals">🏅 ' + p.war_medals + '</span>' +
                                            '<span class="rd-stat rd-battles">⚔️ ' + p.war_battles_count + '</span>' +
                                            '</div>';
                                        playersHtml += '<div class="rd-player"><div class="rd-player-header"><div class="rd-player-name">' + lutouIcon + ' ' + p.player + '</div><div class="rd-player-fame">' + p.fame + ' ⭐</div></div>' + decksHtml + warStats + '</div>';
                                    }});
                                    var meClass = clan.is_me ? 'rd-clan-me' : '';
                                    var meBadge = clan.is_me ? '<span class="rd-me-badge">VOCÊ</span>' : '';
                                    html += '<div class="rd-clan ' + meClass + '">' +
                                        '<div class="rd-clan-header">' +
                                        '<span class="rd-pos">#' + clan.position + '</span>' +
                                        '<span class="rd-clan-name">' + clan.name + '</span>' + meBadge +
                                        '<span class="rd-clan-fame">' + clan.total_fame.toLocaleString() + ' ⭐</span>' +
                                        '</div><div class="rd-players">' + playersHtml + '</div></div>';
                                }});
                                html += '</div>';
                                grid.innerHTML = html;
                            }}
                        </script>
                    """
            except Exception as e:
                logger.error(f"Error generating TOP Global script: {e}")
            
            war_radar_html += top_global_script
            
            return self.generate_full_html(account_tabs_html, account_contents_html, 
                                         clan_member_activity_html, war_intel_html, war_radar_html)
        except Exception as e:
            logger.error(f"Error generating complete HTML report: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return self.generate_error_page()

    def _generate_account_content_html(self, player_tag: str, stats: Dict) -> str:
        """Generates account-specific content HTML with granular error handling."""
        # Initialize component placeholders
        battles_table_html = ""
        battles_cards_html = ""
        other_battles_table_html = ""
        other_battles_cards_html = ""
        other_name = "Secundária"
        daily_histogram_html = ""
        chests_html = ""
        deck_performance_html = ""
        lethal_decks_html = ""
        
        try:
            win_rate = (stats['wins'] / max(stats['total_battles'], 1)) * 100
            
            # 1. Auxiliary Data & Lethal Decks
            try:
                battles = self.get_recent_battles(15, player_tag=player_tag)
                daily_stats = self.get_daily_battle_stats(30, player_tag=player_tag)
                daily_stats_7_days = self.get_daily_battle_stats(7, player_tag=player_tag)
                
                lethal_decks_data = self.get_lethal_opponent_decks(player_tag=player_tag)
                lethal_decks_html = self.generate_lethal_decks_html(lethal_decks_data)
            except Exception as e:
                logger.error(f"Error fetching auxiliary data for {player_tag}: {e}")
                battles = []
                daily_stats = []
                daily_stats_7_days = []

            # 2. Deck Performance
            try:
                weekly_decks = self.get_weekly_decks_from_csv(player_tag=player_tag)
                repeated_opponents = self.get_repeated_opponents_from_csv(player_tag=player_tag)
                winning_decks_global = self.get_top_winning_decks_weekly()
                
                deck_performance_html = self.generate_deck_performance_with_tabs(
                    weekly_decks, repeated_opponents, winning_decks_global, [], stats, player_tag, lethal_decks_html
                )
            except Exception as e:
                logger.error(f"Error generating deck performance for {player_tag}: {e}")
                deck_performance_html = "<div class='error'>Error loading deck performance</div>"

            # 3. Recent Battles Loop
            try:
                for battle in battles[:10]:
                    result_raw = battle.get('result') or 'UNKNOWN'
                    result_class = result_raw.lower()
                    result_text = result_raw.upper()
                    trophy_color = "green" if (battle.get('trophy_change') or 0) >= 0 else "red"
                    result_display = 'Vitória' if result_text in ['VICTORY', 'VITORIA', 'VITÓRIA'] else 'Derrota' if result_text in ['DEFEAT', 'DERROTA'] else 'Empate'
                    
                    elixir_p = battle.get('elixir_vazado_jogador', '0')
                    elixir_o = battle.get('elixir_vazado_oponente', '0')
                    hp_p = battle.get('vida_torre_rei_jogador', '0')
                    hp_o = battle.get('vida_torre_rei_oponente', '0')
                    hp_pri_p = battle.get('vida_torres_princesa_jogador', '0')
                    hp_pri_o = battle.get('vida_torres_princesa_oponente', '0')
                    
                    t_ini = battle.get('trofes_iniciais_jogador', '0')
                    t_fin = battle.get('trofes_finais_jogador', '0')
                    
                    opp_tower_lv = safe_int(battle.get('nivel_torre_oponente', '0'))
                    if opp_tower_lv > 0:
                        opp_display = f"{battle['opponent_name']} <small>(Nv {opp_tower_lv})</small>"
                    else:
                        opp_display = battle['opponent_name']
                    
                    battles_table_html += f"""
                        <tr class="battle-{result_class}">
                            <td>{self.format_time_ago(battle['battle_time'])}</td>
                            <td><span class="result-{result_class}">{result_display}</span></td>
                            <td>{opp_display}</td>
                            <td class="center">{battle['crowns']}</td>
                            <td class="center" style="color: {trophy_color}">
                                <strong>{int(battle['trophy_change']):+d}</strong>
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
                                <div class="battle-opponent">
                                    <span class="opp-name">vs {battle['opponent_name']}</span>
                                    <span class="arena-name">{battle['arena_name']}</span>
                                </div>
                                <div class="battle-metrics">
                                    <div class="metric crown">
                                        <span class="metric-value">{battle['crowns']}</span>
                                        <span class="metric-label">Crowns</span>
                                    </div>
                                    <div class="metric trophy" style="color: {trophy_color}">
                                        <span class="metric-value">{int(battle['trophy_change']):+d}</span>
                                        <span class="metric-label">Trophies</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    """
                
                # 3.1. Identificar a outra conta e buscar dados de batalhas
                other_tag = None
                for t in self.tracked_tags:
                    if t != player_tag:
                        other_tag = t
                        break
                
                other_battles = []
                other_name = "Conta Secundária" if player_tag == '#2QR292P' else "Conta Principal"
                
                if other_tag:
                    try:
                        other_battles = self.get_recent_battles(15, player_tag=other_tag)
                        other_stats = self.get_player_stats(other_tag)
                        if other_stats:
                            other_name = other_stats.get('name', other_name)
                    except Exception as ex_other:
                        logger.error(f"Erro ao buscar batalhas da outra conta {other_tag}: {ex_other}")
                
                # 3.2. Gerar HTML de tabelas e cards para a outra conta
                for battle in other_battles[:10]:
                    result_raw = battle.get('result') or 'UNKNOWN'
                    result_class = result_raw.lower()
                    result_text = result_raw.upper()
                    trophy_color = "green" if (battle.get('trophy_change') or 0) >= 0 else "red"
                    result_display = 'Vitória' if result_text in ['VICTORY', 'VITORIA', 'VITÓRIA'] else 'Derrota' if result_text in ['DEFEAT', 'DERROTA'] else 'Empate'
                    
                    opp_tower_lv = safe_int(battle.get('nivel_torre_oponente', '0'))
                    if opp_tower_lv > 0:
                        opp_display = f"{battle['opponent_name']} <small>(Nv {opp_tower_lv})</small>"
                    else:
                        opp_display = battle['opponent_name']
                    
                    other_battles_table_html += f"""
                        <tr class="battle-{result_class}">
                            <td>{self.format_time_ago(battle['battle_time'])}</td>
                            <td><span class="result-{result_class}">{result_display}</span></td>
                            <td>{opp_display}</td>
                            <td class="center">{battle['crowns']}</td>
                            <td class="center" style="color: {trophy_color}">
                                <strong>{int(battle['trophy_change']):+d}</strong>
                            </td>
                            <td>{battle['arena_name']}</td>
                        </tr>
                    """
                    
                    other_battles_cards_html += f"""
                        <div class="battle-card battle-{result_class}">
                            <div class="battle-card-header">
                                <span class="result-{result_class} battle-result">{result_display}</span>
                                <span class="battle-time">{self.format_time_ago(battle['battle_time'])}</span>
                            </div>
                            <div class="battle-card-content">
                                <div class="battle-opponent">
                                    <span class="opp-name">vs {battle['opponent_name']}</span>
                                    <span class="arena-name">{battle['arena_name']}</span>
                                </div>
                                <div class="battle-metrics">
                                    <div class="metric crown">
                                        <span class="metric-value">{battle['crowns']}</span>
                                        <span class="metric-label">Crowns</span>
                                    </div>
                                    <div class="metric trophy" style="color: {trophy_color}">
                                        <span class="metric-value">{int(battle['trophy_change']):+d}</span>
                                        <span class="metric-label">Trophies</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    """
            except Exception as e:
                logger.error(f"Error generating battle history for {player_tag}: {e}")
                battles_table_html = "<tr><td colspan='6'>Error loading battles</td></tr>"
                other_battles_table_html = "<tr><td colspan='6'>Error loading battles</td></tr>"

            # 4. Histograms
            try:
                daily_histogram_desktop = self.generate_daily_histogram_html(daily_stats, f"histogram-desktop-{player_tag.replace('#','')}", include_legend=True, player_tag=player_tag)
                daily_histogram_mobile = self.generate_daily_histogram_html(daily_stats_7_days, f"histogram-mobile-{player_tag.replace('#','')}", include_legend=False, player_tag=player_tag)
                daily_histogram_html = daily_histogram_desktop + daily_histogram_mobile
            except Exception as e:
                logger.error(f"Error generating histograms for {player_tag}: {e}")
                daily_histogram_html = "<div class='error'>Error loading activity chart</div>"

            # 5. Chests (Desativado conforme solicitacao do usuario)
            chests_html = ""

            # 6. Final Assembly
            return f"""
            <div class="cr-account-header glass-panel" style="padding: 30px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center;">
                <div class="player-info">
                    <h2 style="margin: 0; font-size: 2em;">{stats['name']} <span style="font-size: 0.5em; color: rgba(255,255,255,0.3); vertical-align: middle;">{stats['player_tag']}</span></h2>
                    <p style="margin: 5px 0 0 0; color: #94a3b8;">Clan: {stats['clan_name'] or 'None'} | Level: {stats['level']}</p>
                    <p style="font-size: 0.8em; color: #64748b; margin-top: 10px;">Since {self.format_date(stats['first_battle'])}</p>
                </div>
                <div class="player-stats" style="display: flex; gap: 20px;">
                    <div class="stat-card" style="text-align: center; min-width: 120px;">
                        <div class="value" style="font-size: 1.5em; font-weight: 900;">{stats['trophies']:,}</div>
                        <small style="color: #94a3b8;">Trophies</small>
                    </div>
                    <div class="stat-card" style="text-align: center; min-width: 120px;">
                        <div class="value" style="font-size: 1.5em; font-weight: 900; color: #10b981;">{win_rate:.1f}%</div>
                        <small style="color: #94a3b8;">Win Rate</small>
                    </div>
                    <div class="stat-card" style="text-align: center; min-width: 120px;">
                        <div class="value" style="font-size: 1.5em; font-weight: 900;">{stats['total_battles']}</div>
                        <small style="color: #94a3b8;">Battles</small>
                    </div>
                </div>
            </div>

            {chests_html}

            <div class="section glass-panel" style="padding: 25px; margin-bottom: 30px;">
                <h2 class="clash-font" style="margin-bottom: 20px;">📊 Daily Activity</h2>
                {daily_histogram_html}
            </div>

            <div class="section">
                <h2 class="clash-font">🏆 Deck Performance</h2>
                {deck_performance_html}
            </div>

            <div class="section">
                <h2 class="clash-font" style="margin-bottom: 20px;">⚔️ Last Battles</h2>
                
                <!-- Layout de Duas Colunas Lado a Lado no Desktop, Empilhado no Mobile -->
                <div class="cr-last-battles-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 30px;">
                    
                    <!-- Coluna 1: Conta Atual (Destaque) -->
                    <div class="cr-battles-column">
                        <h3 class="clash-font" style="font-size: 1.1em; color: #60a5fa; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                            <i class="fas fa-star" style="color: #fbbf24;"></i> {stats['name']} <small style="opacity: 0.7; font-size: 0.8em;">(Foco Atual)</small>
                        </h3>
                        <div class="desktop-table">
                            <table>
                                <thead><tr><th>Time</th><th>Result</th><th>Opponent</th><th>Crowns</th><th>Trophies</th><th>Arena</th></tr></thead>
                                <tbody>{battles_table_html if battles_table_html else '<tr><td colspan="6">Sem batalhas registradas</td></tr>'}</tbody>
                            </table>
                        </div>
                        <div class="battle-cards">{battles_cards_html}</div>
                    </div>
                    
                    <!-- Coluna 2: Outra Conta -->
                    <div class="cr-battles-column" style="background: rgba(255,255,255,0.01); padding: 15px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.03);">
                        <h3 class="clash-font" style="font-size: 1.1em; color: #a855f7; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                            <i class="fas fa-user-ninja"></i> {other_name}
                        </h3>
                        <div class="desktop-table">
                            <table>
                                <thead><tr><th>Time</th><th>Result</th><th>Opponent</th><th>Crowns</th><th>Trophies</th><th>Arena</th></tr></thead>
                                <tbody>{other_battles_table_html if other_battles_table_html else '<tr><td colspan="6">Sem batalhas registradas</td></tr>'}</tbody>
                            </table>
                        </div>
                        <div class="battle-cards">{other_battles_cards_html}</div>
                    </div>
                    
                </div>
            </div>
            """

        except Exception as e:
            logger.error(f"Error generating account report content: {str(e)}")
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
        <p>Data is automatically updated every 30min (day) / 1h (night) via GitHub Actions.</p>
    </div>
</body>
</html>
        """
    
    def get_base_css_styles(self) -> str:
        """Get base CSS styles used across all pages - Premium v2 Refined"""
        return """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800;900&display=swap');

        :root {
            --glass-bg: rgba(15, 23, 42, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --glass-blur: 12px;
            --primary: #60a5fa;
            --primary-glow: rgba(96, 165, 250, 0.4);
            --accent: #f59e0b;
            --success: #10b981;
            --danger: #ef4444;
            --bg-dark: #020617;
            --card-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
            --premium-gradient: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            --evo-purple: #c026d3;
            --elite-gold: #fbbf24;
        }

        * {
            margin: 0; padding: 0; box-sizing: border-box;
            -webkit-font-smoothing: antialiased;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-dark);
            color: #f8fafc;
            line-height: 1.6;
            min-height: 100vh;
        }

        h1, h2, h3, h4, .clash-font {
            font-family: 'Outfit', sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* Glassmorphism Refined */
        .glass-panel, .cr-glass-premium {
            background: var(--glass-bg);
            backdrop-filter: blur(var(--glass-blur));
            -webkit-backdrop-filter: blur(var(--glass-blur));
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: var(--card-shadow);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
            animation: cr-fade-in-up 0.8s cubic-bezier(0.2, 0.8, 0.2, 1);
        }

        @keyframes cr-fade-in-up {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Account Tabs - Premium v2 */
        .cr-account-tabs {
            display: flex;
            gap: 12px;
            margin: 20px 0 40px 0;
            padding: 6px;
            background: rgba(15, 23, 42, 0.4);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            width: fit-content;
        }

        .cr-tab {
            padding: 12px 28px;
            border-radius: 16px;
            cursor: pointer;
            font-weight: 800;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: rgba(255, 255, 255, 0.4);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            gap: 10px;
            border: 1px solid transparent;
        }

        .cr-tab:hover {
            color: #fff;
            background: rgba(255, 255, 255, 0.05);
            transform: translateY(-2px);
        }

        .cr-tab.active {
            color: #fff;
            background: linear-gradient(135deg, #38bdf8 0%, #1d4ed8 100%);
            border-color: rgba(255, 255, 255, 0.2);
            box-shadow: 0 10px 25px rgba(56, 189, 248, 0.25);
            transform: translateY(-2px);
        }

        .cr-tab-content {
            display: none;
            animation: cr-tab-fade-in 0.6s cubic-bezier(0.2, 0.8, 0.2, 1);
        }

        .cr-tab-content.active {
            display: block;
        }

        @keyframes cr-tab-fade-in {
            from { opacity: 0; transform: scale(0.98) translateY(10px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }

        /* VS Stage Premium v2 - New Hierarchy */
        .cr-vs-stage-v2 {
            display: flex;
            flex-direction: column;
            gap: 24px;
            padding: 30px;
            background: rgba(30, 41, 59, 0.3);
            border-radius: 32px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            margin-bottom: 20px;
        }

        .cr-vs-top-row-v2 {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            gap: 40px;
            width: 100%;
        }

        .cr-vs-side-info {
            display: flex;
            flex-direction: column;
            gap: 15px;
            align-items: center;
        }

        .cr-vs-side-info.player { align-items: center; }
        .cr-vs-side-info.opponent { align-items: center; }

        .cr-vs-player-meta {
            text-align: center;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .cr-vs-tag {
            font-size: 0.65em;
            color: rgba(255,255,255,0.3);
            font-weight: 800;
            letter-spacing: 1px;
        }

        .cr-vs-name {
            font-size: 1.2em;
            font-weight: 900;
            color: #fff;
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }

        .cr-vs-clan {
            font-size: 0.75em;
            color: rgba(255,255,255,0.5);
            font-weight: 600;
        }

        .cr-tower-display-v2 {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
        }

        .cr-tower-img-premium {
            width: 120px;
            height: 120px;
            object-fit: contain;
            filter: drop-shadow(0 10px 25px rgba(0,0,0,0.6));
            transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .cr-tower-img-premium:hover {
            transform: scale(1.1) translateY(-10px);
        }

        .cr-tower-level-badge {
            position: absolute;
            top: -10px;
            background: #1e293b;
            color: var(--accent);
            padding: 2px 8px;
            border-radius: 8px;
            font-size: 0.7em;
            font-weight: 900;
            border: 1px solid var(--accent);
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }

        .cr-tower-hp-v2 {
            font-size: 0.85em;
            font-weight: 900;
            color: var(--success);
            text-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
        }

        .opponent .cr-vs-name { color: var(--danger); }
        .opponent .cr-tower-hp-v2 { color: var(--danger); }

        .cr-vs-center-v2 {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
        }

        .cr-vs-score-v2 {
            font-size: 4em;
            font-weight: 950;
            font-family: 'Outfit', sans-serif;
            line-height: 0.8;
            letter-spacing: -2px;
            text-shadow: 0 10px 30px rgba(0,0,0,0.8);
        }

        .cr-vs-mode-v2 {
            background: rgba(255,255,255,0.05);
            padding: 6px 16px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 900;
            color: rgba(255,255,255,0.7);
            text-transform: uppercase;
            letter-spacing: 2px;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .cr-vs-trophies-v2 {
            font-size: 1.1em;
            font-weight: 900;
        }

        /* Decks Row */
        .cr-vs-decks-row-v2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }

        .cr-vs-deck-wrap {
            background: rgba(15, 23, 42, 0.4);
            padding: 20px;
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: inset 0 4px 20px rgba(0,0,0,0.3);
        }

        /* Card Premium v2 */
        .cr-card-wrap-premium {
            aspect-ratio: 5/6;
            background: #1e293b;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
            position: relative;
            overflow: hidden;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            box-shadow: 0 8px 20px rgba(0,0,0,0.4);
        }

        .cr-card-wrap-premium:hover {
            transform: scale(1.15) translateY(-8px);
            z-index: 50;
            border-color: var(--primary);
            box-shadow: 0 20px 40px rgba(0,0,0,0.7);
        }

        .cr-card-img { width: 100%; height: 100%; object-fit: cover; }

        .cr-card-level-badge {
            position: absolute;
            bottom: 4px;
            right: 4px;
            background: rgba(15, 23, 42, 0.9);
            color: #fff;
            font-size: 0.65em;
            font-weight: 900;
            padding: 2px 6px;
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.15);
            z-index: 5;
        }

        .cr-card-level-badge.cr-lvl-15 {
            background: linear-gradient(180deg, #b45309, #fbbf24);
            border-color: #fff;
            color: #000;
            box-shadow: 0 0 10px rgba(251, 191, 36, 0.5);
        }

        /* Evolutions Premium */
        .cr-card-evo-premium {
            border: 2px solid var(--evo-purple) !important;
            box-shadow: 0 0 20px rgba(192, 38, 211, 0.4);
        }

        .cr-evo-badge-icon {
            position: absolute;
            top: 4px;
            left: 4px;
            width: 18px;
            height: 18px;
            background: var(--evo-purple);
            border-radius: 4px;
            border: 1px solid #fff;
            z-index: 10;
            box-shadow: 0 0 10px var(--evo-purple);
            background-image: url('data:image/svg+xml;utf8,<svg fill="white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/></svg>');
            background-size: 70%;
            background-position: center;
            background-repeat: no-repeat;
        }

        /* Metrics Footer */
        .cr-vs-metrics-footer-v2 {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            gap: 20px;
            background: rgba(0,0,0,0.4);
            padding: 20px;
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .cr-vs-battle-meta-v2 {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 5px;
            padding: 0 30px;
            border-left: 1px solid rgba(255,255,255,0.05);
            border-right: 1px solid rgba(255,255,255,0.05);
        }

        .cr-vs-arena-v2 {
            font-size: 0.7em;
            font-weight: 800;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .cr-vs-ranks-v2 {
            display: flex;
            gap: 15px;
            font-size: 0.7em;
            font-weight: 900;
            color: var(--accent);
        }

        /* Deck Wrapper Copy Button */
        .cr-grid-wrapper-premium {
            position: relative;
        }

        .cr-copy-deck-btn {
            position: absolute;
            bottom: -15px;
            right: 10px;
            width: 36px;
            height: 36px;
            background: var(--primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            border: 2px solid #fff;
            box-shadow: 0 5px 15px rgba(0,0,0,0.5);
            transition: all 0.3s;
            z-index: 60;
        }

        .cr-copy-deck-btn:hover {
            transform: scale(1.2) rotate(15deg);
            background: #fff;
            color: var(--primary);
        }

        .cr-grid-4x2 {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
        }

        /* Responsividade */
        @media (max-width: 900px) {
            .cr-vs-top-row-v2 {
                grid-template-columns: 1fr;
                gap: 30px;
            }
            .cr-vs-decks-row-v2 {
                grid-template-columns: 1fr;
            }
            .cr-vs-metrics-footer-v2 {
                grid-template-columns: 1fr;
            }
            .cr-vs-battle-meta-v2 {
                border: none;
                padding: 15px 0;
                border-top: 1px solid rgba(255,255,255,0.05);
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
        }
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
            width: 100px;
            height: 100px;
            object-fit: contain;
            filter: drop-shadow(0 15px 35px rgba(0,0,0,0.7));
            transition: all 0.45s cubic-bezier(0.23, 1, 0.32, 1);
            margin-bottom: -10px;
            position: relative;
            z-index: 1;
        }


        .cr-tower-lv-badge {
            position: absolute;
            top: -6px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(180deg, #1e293b, #020617);
            color: #fbbf24;
            font-size: 0.65em;
            font-weight: 950;
            padding: 2px 6px;
            border-radius: 6px;
            border: 1px solid #fbbf24;
            z-index: 10;
            box-shadow: 0 4px 10px rgba(0,0,0,0.85);
            border-bottom: 2px solid #b45309;
            text-shadow: 0 1px 2px rgba(0,0,0,1);
            letter-spacing: 0.5px;
            pointer-events: none;
            white-space: nowrap;
        }


        .cr-tower-img-large:hover {
            transform: translateY(-8px) scale(1.06);
            filter: drop-shadow(0 20px 45px rgba(0, 0, 0, 0.8));
            z-index: 5;
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
            overflow: hidden; /* Oculta textos se a altura for menor que o texto */
        }

        .segment-value {
            font-size: 8px !important;
            font-weight: 900;
            color: #fff;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            pointer-events: none;
            line-height: 1;
            text-shadow: 0 1px 2px rgba(0,0,0,0.8);
            display: inline-block;
            white-space: nowrap;
        }

        .bar-segment:hover { filter: brightness(1.2); transform: scaleX(1.1); }

        /* Estilos do Modal de Atividade Diaria Premium */
        .cr-day-modal-layout {
            display: grid;
            grid-template-columns: 350px 1fr;
            gap: 20px;
            margin-bottom: 20px;
            width: 100%;
        }

        @media (max-width: 1024px) {
            .cr-day-modal-layout {
                grid-template-columns: 1fr;
            }
        }

        .cr-day-modal-box {
            background: rgba(15, 23, 42, 0.45);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 18px;
            padding: 20px;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
        }

        .cr-day-modal-title {
            font-family: 'Inter', sans-serif;
            font-size: 1.4em;
            font-weight: 800;
            color: #f1f5f9;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 15px;
        }

        .cr-day-metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            font-size: 0.95em;
            color: #e2e8f0;
            position: relative;
        }

        .cr-day-metric-label {
            font-weight: 600;
            color: #94a3b8;
            z-index: 1;
            background: rgba(15, 23, 42, 0.95);
            padding-right: 8px;
        }

        .cr-day-metric-dots {
            flex-grow: 1;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.15);
            margin: 0 8px;
            transform: translateY(-4px);
        }

        .cr-day-metric-value {
            font-family: 'Inter', monospace;
            font-weight: 800;
            color: #f8fafc;
            z-index: 1;
            background: rgba(15, 23, 42, 0.95);
            padding-left: 8px;
        }

        .cr-day-battles-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(48px, 1fr));
            gap: 12px;
        }

        .cr-day-battle-card {
            aspect-ratio: 1;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4em;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            border: 2px solid transparent;
            position: relative;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25);
            background: rgba(255, 255, 255, 0.03);
        }

        .cr-day-battle-card:hover {
            transform: translateY(-4px) scale(1.06);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.45);
        }

        .cr-day-battle-card.win {
            background: linear-gradient(135deg, rgba(72, 187, 120, 0.25), rgba(72, 187, 120, 0.1));
            border: 1px solid rgba(72, 187, 120, 0.4);
            color: #48bb78;
        }

        .cr-day-battle-card.win.active {
            border: 2px solid #48bb78 !important;
            box-shadow: 0 0 15px rgba(72, 187, 120, 0.75) !important;
            transform: translateY(-2px);
        }

        .cr-day-battle-card.loss {
            background: linear-gradient(135deg, rgba(245, 101, 101, 0.25), rgba(245, 101, 101, 0.15));
            border: 1px solid rgba(245, 101, 101, 0.4);
            color: #f56565;
        }

        .cr-day-battle-card.loss.active {
            border: 2px solid #f56565 !important;
            box-shadow: 0 0 15px rgba(245, 101, 101, 0.75) !important;
            transform: translateY(-2px);
        }

        .cr-day-battle-card.draw {
            background: linear-gradient(135deg, rgba(113, 128, 150, 0.25), rgba(113, 128, 150, 0.1));
            border: 1px solid rgba(113, 128, 150, 0.4);
            color: #a0aec0;
        }

        .cr-day-battle-card.draw.active {
            border: 2px solid #a0aec0 !important;
            box-shadow: 0 0 15px rgba(113, 128, 150, 0.75) !important;
            transform: translateY(-2px);
        }

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
            .cr-opponents-list, .battle-cards, .cr-lethal-decks-grid {
                grid-template-columns: 1fr !important;
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

        /* Battle Cards - Redesigned Compact Cards */
        .battle-cards {
            display: none;
        }
        
        @media (max-width: 768px) {
            .battle-cards {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
                padding: 5px 0;
            }
        }
        
        @media (max-width: 480px) {
            .battle-cards {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
        }
        
        .battle-card {
            background: rgba(15, 23, 42, 0.9);
            border-radius: 12px;
            padding: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .battle-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .battle-card.battle-victory {
            border-top: 3px solid #10b981;
            background: linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.95) 30%);
        }
        
        .battle-card.battle-defeat {
            border-top: 3px solid #ef4444;
            background: linear-gradient(180deg, rgba(239, 68, 68, 0.08) 0%, rgba(15, 23, 42, 0.95) 30%);
        }
        
        .battle-card.battle-draw {
            border-top: 3px solid #f59e0b;
            background: linear-gradient(180deg, rgba(245, 158, 11, 0.08) 0%, rgba(15, 23, 42, 0.95) 30%);
        }
        
        .battle-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .battle-result {
            font-size: 0.7em;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .result-victory {
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
        }
        
        .result-defeat {
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
        }
        
        .result-draw {
            background: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
        }
        
        .battle-time {
            color: rgba(255, 255, 255, 0.4);
            font-size: 0.65em;
        }
        
        .battle-card-content {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .battle-opponent {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        
        .opp-name {
            font-size: 0.85em;
            font-weight: 700;
            color: #e2e8f0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .arena-name {
            font-size: 0.7em;
            color: rgba(255, 255, 255, 0.4);
        }
        
        .battle-metrics {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .battle-metrics .metric {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
        }
        
        .battle-metrics .metric-value {
            font-size: 0.9em;
            font-weight: 800;
        }
        
        .battle-metrics .metric-label {
            font-size: 0.65em;
            color: rgba(255, 255, 255, 0.5);
        }
        
        .battle-metrics .metric.crown {
            color: #fbbf24;
        }
        
        .battle-metrics .metric.crown .metric-value::before {
            content: '';
            display: inline-block;
            width: 12px;
            height: 12px;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23fbbf24"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>') no-repeat center;
            background-size: contain;
            vertical-align: middle;
            margin-right: 2px;
        }
        
        .battle-metrics .metric.trophy {
            color: #10b981;
        }
        
        .battle-metrics .metric.trophy .metric-value::before {
            content: '';
            display: inline-block;
            width: 12px;
            height: 12px;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%2310b981"><path d="M12 2C9.38 2 7.25 4.13 7.25 6.75c0 1.87 1.07 3.49 2.63 4.29L9.5 14h5l-.38-3.04c1.56-.8 2.63-2.42 2.63-4.21C16.75 4.13 14.62 2 12 2zm0 2c1.52 0 2.75 1.23 2.75 2.75S13.52 9.5 12 9.5 9.25 8.27 9.25 6.75 10.48 4 12 4z"/></svg>') no-repeat center;
            background-size: contain;
            vertical-align: middle;
            margin-right: 2px;
        }



        /* ===== TABS DE SELEÇÃO DE CONTA (Multi-Account) ===== */
        .cr-account-tabs {
            display: flex;
            gap: 12px;
            margin: 20px auto 30px auto;
            padding: 8px;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            width: fit-content;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 15px rgba(59, 130, 246, 0.2);
            position: relative;
            z-index: 1000;
            backdrop-filter: blur(12px);
        }

        .cr-tab {
            padding: 12px 28px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px;
            color: #94a3b8;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            gap: 10px;
        }

        .cr-tab i {
            font-size: 1.1em;
            filter: drop-shadow(0 0 5px currentColor);
        }

        .cr-tab:hover {
            background: rgba(255, 255, 255, 0.08);
            color: #fff;
            transform: translateY(-2px);
            border-color: rgba(59, 130, 246, 0.4);
        }

        .cr-tab.active {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.4), rgba(37, 99, 235, 0.4));
            color: #fff;
            border-color: #3b82f6;
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4), inset 0 0 10px rgba(59, 130, 246, 0.2);
            transform: translateY(-2px);
        }

        .cr-tab-content {
            display: none;
            animation: cr-fade-in 0.5s ease;
        }

        .cr-tab-content.active {
            display: block;
        }

        @keyframes cr-fade-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* WAR RADAR CSS - Estilos para secao de radar de guerra */
        .rd-section { border-left: 5px solid #dc2626 !important; background: rgba(20, 10, 10, 0.85) !important; border-radius: 16px; padding: 20px; }
        
        /* Widgets Analiticos Premium - Glassmorphism */
        .rd-analytics-cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 15px;
            margin-bottom: 12px;
        }
        
        .rd-card-premium {
            position: relative;
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 10px 12px;
            display: flex;
            align-items: center;
            gap: 16px;
            overflow: hidden;
            backdrop-filter: blur(16px);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        }
        
        .rd-card-premium:hover {
            transform: translateY(-4px);
            border-color: rgba(96, 165, 250, 0.4);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(96, 165, 250, 0.15);
        }
        
        .rd-card-glow {
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(96, 165, 250, 0.1) 0%, transparent 70%);
            pointer-events: none;
            transition: all 0.5s ease;
            opacity: 0.5;
        }
        
        .rd-card-premium:hover .rd-card-glow {
            transform: scale(1.1);
            opacity: 0.8;
        }
        
        .rd-card-icon {
            font-size: 1.6em;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.3s ease;
        }
        
        .rd-card-premium:hover .rd-card-icon {
            transform: scale(1.1);
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.15);
        }
        
        .rd-card-details {
            display: flex;
            flex-direction: column;
            gap: 2px;
            flex: 1;
        }
        
        .rd-card-title {
            font-size: 0.7em;
            font-weight: 800;
            color: rgba(255, 255, 255, 0.5);
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }
        
        .rd-card-value {
            font-size: 1.5em;
            font-weight: 900;
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .rd-card-sub {
            font-size: 0.72em;
            color: #94a3b8;
            font-weight: 500;
        }
        
        /* Cores Específicas dos Cartões */
        .rd-decks-card .rd-card-icon { color: #60a5fa; }
        .rd-efficiency-card .rd-card-icon { color: #f59e0b; }
        .rd-projection-card .rd-card-icon { color: #10b981; }
        
        /* Barra de Métricas dos Clãs */
        .rd-clan-metrics-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 14px;
            background: rgba(0, 0, 0, 0.2);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            flex-wrap: wrap;
        }
        
        .rd-clan-metric-item {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 0.72em;
            color: #e2e8f0;
            background: rgba(255, 255, 255, 0.05);
            padding: 2px 8px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            font-weight: 600;
        }
        
        /* Badges de Ameaça Neon Semafórica */
        .rd-threat-badge {
            font-size: 0.65em;
            font-weight: 900;
            padding: 2px 8px;
            border-radius: 6px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-left: auto;
            display: inline-block;
            box-shadow: 0 0 10px currentColor;
        }
        
        .rd-threat-critical {
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.35);
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.25);
        }
        
        .rd-threat-moderate {
            background: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.35);
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.25);
        }
        
        .rd-threat-controlled {
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.35);
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.25);
        }
        
        /* Ajuste responsivo para os cartões */
        @media (max-width: 768px) {
            .rd-analytics-cards {
                grid-template-columns: 1fr;
                gap: 10px;
            }
            
            .rd-threat-badge {
                margin-left: 0;
            }
        }
        .rd-header { text-align: center; margin-bottom: 24px; }
        .rd-badge { display: inline-block; background: linear-gradient(135deg, #dc2626, #991b1b); color: white; font-weight: 900; font-size: 0.8em; letter-spacing: 2px; padding: 4px 16px; border-radius: 20px; margin-bottom: 8px; }
        .rd-header h2 { font-size: 1.5em; margin: 8px 0; }
        .rd-legend { font-size: 0.75em; color: #94a3b8; display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; }
        .rd-legend-item { display: flex; align-items: center; }
        .rd-legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
        .rd-red { background: #ef4444; }
        .rd-gray { background: #6b7280; }
        .rd-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
        .rd-clan { background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; overflow: hidden; }
        .rd-clan:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
        .rd-clan-me { border-color: rgba(96, 165, 250, 0.5) !important; box-shadow: 0 0 20px rgba(96, 165, 250, 0.15); }
        .rd-clan-header { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.08); }
        .rd-pos { background: #ef4444; color: white; font-weight: 800; font-size: 0.7em; padding: 2px 7px; border-radius: 4px; min-width: 28px; text-align: center; }
        .rd-clan-name { font-weight: 800; font-size: 0.85em; flex: 1; color: #f1f5f9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .rd-me-badge { background: #3b82f6; color: white; font-size: 0.6em; padding: 2px 6px; border-radius: 4px; font-weight: 800; }
        .rd-clan-fame { font-size: 0.75em; color: #fbbf24; font-weight: 700; white-space: nowrap; }
        .rd-players { display: flex; flex-direction: column; }
        .rd-player { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .rd-player:last-child { border-bottom: none; }
        .rd-player-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
        .rd-rank { font-size: 0.65em; color: #6b7280; font-weight: 700; min-width: 20px; }
        .rd-name { font-size: 0.85em; font-weight: 600; color: #e2e8f0; flex: 1; }
        .rd-fame { font-size: 0.7em; color: #4ade80; font-weight: 700; }
        .rd-lutou { font-size: 0.8em; }
        .rd-attacks { font-size: 0.65em; color: #94a3b8; background: rgba(255,255,255,0.08); padding: 1px 6px; border-radius: 4px; }
        .rd-decks { display: flex; flex-direction: column; gap: 2px; }
        .rd-deck-row { display: flex; flex-direction: column; gap: 2px; }
        .rd-deck-label { font-size: 0.65em; color: #60a5fa; font-weight: 700; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.5px; }
        .rd-deck { display: flex; gap: 2px; flex-wrap: wrap; min-height: 40px; align-items: center; padding: 2px 0; }
        .rd-deck-break { width: 100%; height: 4px; }
        .rd-clan { border-bottom: 1px solid rgba(96, 165, 250, 0.3); padding-bottom: 15px; margin-bottom: 15px; }
        .rd-clan:last-child { border-bottom: none; }
        .rd-card { width: 40px; height: 40px; border-radius: 6px; background: #0f172a; border: 1px solid rgba(255,255,255,0.1); overflow: hidden; }
        .rd-card img { width: 100%; height: 100%; object-fit: cover; }
        .rd-no-deck { color: #475569; font-size: 0.7em; font-style: italic; padding: 4px 0; }
        .rd-deck-count { font-size: 0.6em; color: #475569; text-align: right; margin-top: 2px; }
        .rd-tabs-container { margin-bottom: 30px; }
        .rd-tabs-header { display: flex; gap: 8px; margin-bottom: 15px; justify-content: center; }
        .rd-tab { background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; padding: 10px 24px; border-radius: 12px; cursor: pointer; font-weight: 700; font-size: 0.85em; transition: all 0.3s; }
        .rd-tab:hover { background: rgba(59, 130, 246, 0.2); border-color: var(--primary); color: #fff; }
        .rd-tab.active { background: var(--primary); border-color: var(--primary); color: white; box-shadow: 0 4px 15px rgba(96, 165, 250, 0.4); }
        .rd-mode-selector { display: flex; gap: 10px; margin-bottom: 20px; justify-content: center; }
        .rd-mode-btn { background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; padding: 8px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.8em; transition: all 0.3s; }
        .rd-mode-btn:hover { background: rgba(59, 130, 246, 0.2); border-color: var(--primary); color: #fff; }
        .rd-mode-btn.rd-mode-active { background: var(--primary); border-color: var(--primary); color: white; }
        
        /* Estatísticas de Guerra do Jogador */
        .rd-player-stats {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 8px;
            padding: 6px 8px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
        }
        .rd-stat {
            font-size: 0.7em;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
        }
        .rd-vitorias { color: #4ade80; background: rgba(74, 222, 128, 0.1); }
        .rd-derrotas { color: #f87171; background: rgba(248, 113, 113, 0.1); }
        .rd-medals { color: #fbbf24; background: rgba(251, 191, 36, 0.1); }
        .rd-battles { color: #60a5fa; background: rgba(96, 165, 250, 0.1); }
        .rd-torre { color: #a78bfa; background: rgba(167, 139, 250, 0.1); }
        
        /* Calendário de Dias de Guerra - NOVO LAYOUT REDUZIDO */
        .rd-calendar-container { 
            background: rgba(15, 23, 42, 0.8); 
            border-radius: 20px; 
            padding: 12px 16px; 
            margin-bottom: 15px; 
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        .rd-calendar-title { 
            font-size: 1em; 
            font-weight: 700; 
            color: #94a3b8; 
            text-transform: uppercase; 
            letter-spacing: 2px; 
            margin-bottom: 10px; 
            text-align: center;
        }
        
        .rd-calendar-timeline {
            display: flex;
            justify-content: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .rd-calendar-day {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 8px 10px;
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            min-width: 80px;
            gap: 2px;
        }
        .rd-calendar-label {
            color: #94a3b8;
            font-size: 0.85em;
            font-weight: 700;
            text-transform: uppercase;
        }
        .rd-calendar-medal { font-size: 1.1em; }
        .rd-calendar-pos { font-size: 0.9em; font-weight: bold; color: #fff; }
        .rd-calendar-fame { font-size: 0.85em; color: #cbd5e1; }
        .rd-calendar-boat { font-size: 0.9em; }
        .rd-calendar-status { font-size: 0.75em; color: #ef4444; }

        .rd-calendar-day:hover { 
            background: rgba(59, 130, 246, 0.2); 
            border-color: rgba(96, 165, 250, 0.5);
            transform: translateY(-2px);
        }
        .rd-calendar-day:hover .rd-calendar-label {
            color: #e2e8f0;
        }
        .rd-calendar-day-active { 
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(139, 92, 246, 0.2)) !important; 
            border-color: #3b82f6 !important; 
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.3) !important;
            transform: scale(1.05);
        }
        .rd-calendar-day-active .rd-calendar-label {
            color: #fff;
        }
        
        .rd-war-summary {
            /* Mesclado ao rd-calendar-container */
            background: transparent;
            border: none;
            border-radius: 0;
            padding: 4px 12px;
            margin: 0;
            animation: rdSummaryFadeIn 0.3s ease;
            box-shadow: none;
        }
        @keyframes rdSummaryFadeIn {
            from { opacity: 0; transform: translateY(-6px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .rd-war-summary-inner {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .rd-war-summary-label {
            color: #94a3b8;
            font-size: 0.78em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .rd-war-summary-date {
            color: #e2e8f0;
            font-size: 0.85em;
            font-weight: 700;
            font-family: monospace;
        }
        .rd-war-summary-pos {
            color: #fbbf24;
            font-size: 0.95em;
            font-weight: 800;
        }
        .rd-war-summary-fame {
            color: #00ffcc;
            font-size: 0.95em;
            font-weight: 800;
        }
        .rd-war-summary-sep {
            color: #334155;
            font-size: 0.9em;
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
            padding: 15px;
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
        """
    
    def generate_full_html(self, account_tabs_html: str, account_contents_html: str,
                          clan_member_activity_html: str = "",
                          war_intel_html: str = "",
                          war_radar_html: str = "") -> str:
        """Generate the complete HTML document with multi-account support"""
        
        css_styles = self.get_base_css_styles()
        build_timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        return f"""
<!DOCTYPE html>
<html lang="pt-br" data-build="{build_timestamp}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Royale Analytics - Dashboard Multi-Contas</title>
    <link rel="icon" type="image/x-icon" href="favicon.ico">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/charts.css/dist/charts.min.css">
    <style>{css_styles}</style>
</head>
<body>

    <div id="cr-battle-modal" class="cr-modal-overlay">
        <div class="cr-modal-container">
            <button class="cr-modal-close" onclick="closeBattleModal()">x</button>
            <div id="battle-modal-content">
                <div style="text-align: center; padding: 40px; color: #94a3b8;">
                    <p>Carregando visualizacao de batalha...</p>
                </div>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="cr-dashboard-main-header">
            <h1 class="clash-font" style="text-shadow: 0 0 20px rgba(59, 130, 246, 0.5);">&#9876; Royale Analytics Dashboard</h1>
            <p style="color: #94a3b8; margin-bottom: 25px; font-weight: 500;">Painel Inteligente de Desempenho e Estratégia</p>
            <!-- Injeção Crítica: Seletor de Contas -->
            <div style="display: flex; justify-content: center; width: 100%;">
                {account_tabs_html}
            </div>
        </div>

        <div class="cr-dashboard-content">
            {account_contents_html}
        </div>

        <div class="cr-global-sections">
            {war_intel_html}
            {war_radar_html}
            {clan_member_activity_html}
        </div>

        <div class="footer">
            <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Automatically updated via GitHub Actions</p>
        </div>
    </div>
    
    <script>
    
    // Tab switching for multiple accounts (Main vs Secondary)
/**
     * @description Gerencia a troca de abas principais (Contas)
     * e restaura a aba interna selecionada anteriormente para cada conta
     * @author Especialista em QA/Dev
     */
    function switchAccountTab(tag, element) {{
        console.log('Solicitando troca para conta:', tag);
        
        // 0. Salva o estado da aba interna atual ANTES de trocar
        const activeAccountContent = document.querySelector('.cr-dashboard-content > .cr-tab-content.active');
        if (activeAccountContent) {{
            const currentInnerTab = activeAccountContent.querySelector('.cr-inner-tabs-container .cr-tab.active');
            if (currentInnerTab) {{
                const currentAccountTag = activeAccountContent.id.replace('account-tab-', '');
                const match = currentInnerTab.getAttribute('onclick').match(/'([^']+)'/);
                if (match) {{
                    localStorage.setItem('cr_inner_tab_' + currentAccountTag, match[1]);
                }}
            }}
        }}
        
        // 1. Limpeza de estados de abas
        const allTabs = document.querySelectorAll('.cr-dashboard-main-header .cr-tab');
        allTabs.forEach(t => t.classList.remove('active'));
        
        // 2. Ativação da aba clicada
        if (element) {{
            element.classList.add('active');
        }} else {{
            // Fallback caso o clique venha de outro lugar
            const cleanTagForSearch = tag.replace('#', '');
            const tabToActivate = document.querySelector(`.cr-tab[onclick*="${{cleanTagForSearch}}"]`);
            if (tabToActivate) tabToActivate.classList.add('active');
        }}
        
        // 3. Gerenciamento de Conteúdo
        const allContents = document.querySelectorAll('.cr-dashboard-content > .cr-tab-content');
        allContents.forEach(c => {{
            c.classList.remove('active');
            c.style.display = 'none'; // Garantia extra
        }});
        
        const cleanTag = tag.replace('#', '');
        const targetId = 'account-tab-' + cleanTag;
        const targetContent = document.getElementById(targetId);
        
        if (targetContent) {{
            targetContent.classList.add('active');
            targetContent.style.display = 'block';
            console.info('Conteúdo da conta ativado com sucesso: ' + targetId);
            
            // 4. Salva a conta ativa no localStorage
            localStorage.setItem('cr_active_account', cleanTag);
            
            // 5. Restaura a aba interna que estava selecionada para esta conta
            const savedInnerTabId = localStorage.getItem('cr_inner_tab_' + cleanTag);
            if (savedInnerTabId) {{
                const savedTab = targetContent.querySelector(`.cr-tab[onclick*="${{savedInnerTabId}}"]`);
                if (savedTab) {{
                    // Simula o click diretamente
                    savedTab.dispatchEvent(new Event('click', {{ bubbles: true }}));
                }}
            }}
            
            // Trigger para redimensionar gráficos se houver
            window.dispatchEvent(new Event('resize'));
            
            // Sincronizar o Radar de Guerra da parte inferior (evitando loops de recursão)
            const radarTab = document.querySelector(`.rd-tab[data-tag*="${{cleanTag}}"]`);
            if (radarTab && !radarTab.classList.contains('active')) {{
                console.log('Sincronizando aba do Radar de Guerra para tag:', cleanTag);
                radarTab.click();
            }}
        }} else {{
            console.error('ERRO CRÍTICO: Container de conta não encontrado no DOM: ' + targetId);
            const availableIds = Array.from(allContents).map(c => c.id);
            console.debug('IDs disponíveis no DOM:', availableIds);
        }}
    }}

    // Tab switching for INNER sections (VS Stage, Decks, etc)
    function switchInnerTab(event, targetId) {{
        if (!event || !event.currentTarget) return;
        
        const container = event.currentTarget.closest('.cr-inner-tabs-container');
        if (!container) {{
            console.error('Container não encontrado');
            return;
        }}

        // Remove active from ALL tabs in container
        container.querySelectorAll('.cr-tab').forEach(t => t.classList.remove('active'));
        // Add active to current tab
        event.currentTarget.classList.add('active');

        // Hide ALL tab contents in container
        container.querySelectorAll('.cr-tab-content').forEach(c => {{
            c.classList.remove('active');
            c.style.display = 'none';
        }});
        
        // Show target tab content
        const target = document.getElementById(targetId);
        if (target) {{
            target.classList.add('active');
            target.style.display = 'block';
            console.log('Tab activated:', targetId);
        }} else {{
            console.error('Target not found:', targetId);
        }}
        
        // Salva a aba interna ativa no localStorage
        const activeAccount = document.querySelector('.cr-dashboard-content > .cr-tab-content.active');
        if (activeAccount) {{
            const accountId = activeAccount.id.replace('account-tab-', '');
            localStorage.setItem('cr_inner_tab_' + accountId, targetId);
        }}
    }}
    
    // Radar Tab switching (Conta Principal vs Secundária)
    function switchRadarTab(tabId, element) {{
        if (!element) return;
        
        // Get the parent container
        const container = element.closest('.rd-tabs-container');
        if (!container) return;
        
        // Remove active from all radar tabs
        container.querySelectorAll('.rd-tab').forEach(t => t.classList.remove('active'));
        element.classList.add('active');
        
        // Hide all radar contents
        container.querySelectorAll('.rd-content').forEach(c => {{
            c.classList.remove('active');
            c.style.display = 'none';
        }});
        
        // Show target radar content
        const target = document.getElementById('rd-content-' + tabId);
        if (target) {{
            target.classList.add('active');
            target.style.display = 'block';
            
            // Garantir o recalculamento das métricas ao tornar a aba visível física no DOM
            // Busca o dia ativo no calendário desta aba e simula o clique nele com delay de 50ms
            setTimeout(function() {{
                const activeDayBtn = target.querySelector('.rd-calendar-day.rd-calendar-day-active') || target.querySelector('.rd-calendar-day');
                if (activeDayBtn) {{
                    const date = activeDayBtn.getAttribute('data-date');
                    selectWarDay(tabId, date, activeDayBtn, true);
                }}
            }}, 50);
        }}
        
        // Salvar seleção no localStorage
        localStorage.setItem('cr_radar_tab_' + tabId, tabId);
        
        // Sincronizar com a aba de conta principal do topo (evitando loops de recursão)
        const tag = element.getAttribute('data-tag');
        if (tag) {{
            const cleanTag = tag.replace('#', '');
            const accountTab = document.querySelector(`.cr-dashboard-main-header .cr-tab[onclick*="${{cleanTag}}"]`);
            if (accountTab && !accountTab.classList.contains('active')) {{
                console.log('Sincronizando aba de conta no topo com o Radar para tag:', cleanTag);
                accountTab.click();
            }}
        }}
    }}
    
    // War Day selection - filtrar jogadores e clans por data e atualizar painel de resumo
    function selectWarDay(tabId, date, element, isAutoLoad) {{
        if (!element) return;
        
        var calendar = element.closest('.rd-calendar-container');
        if (!calendar) return;
        
        // Remover active de todos os dias e marcar o clicado
        calendar.querySelectorAll('.rd-calendar-day').forEach(function(d) {{ d.classList.remove('rd-calendar-day-active'); }});
        element.classList.add('rd-calendar-day-active');
        
        // Encontrar o conteudo do radar para esta tab
        var radarContent = document.getElementById('rd-content-' + tabId);
        if (!radarContent) return;
        
        // Ocultar todos os grids de dias operacionais deste radar no modo 'my-war'
        radarContent.querySelectorAll('.rd-my-war-grid-day').forEach(function(grid) {{
            grid.style.display = 'none';
        }});
        
        // Exibir apenas o grid correspondente ao dia selecionado
        var myWarContainer = radarContent.querySelector('.rd-my-war-container');
        if (myWarContainer) {{
            myWarContainer.style.display = 'block';
        }}
        var globalContainer = radarContent.querySelector('.rd-global-container');
        if (globalContainer) {{
            globalContainer.style.display = 'none';
        }}
        
        var targetGrid = document.getElementById('rd-grid-' + tabId + '-' + date);
        if (targetGrid) {{
            targetGrid.style.display = 'grid';
        }}
        
        // Make sure mode button is synced
        var myWarBtn = radarContent.querySelector('.rd-mode-btn[onclick*="my-war"]');
        if (myWarBtn) {{
            radarContent.querySelectorAll('.rd-mode-btn').forEach(function(b) {{ b.classList.remove('rd-mode-active'); }});
            myWarBtn.classList.add('rd-mode-active');
        }}
        
        // Se estiver no modo TOP Global, renderiza os dados do TOP Global daquele dia
        var topGlobalBtn = radarContent.querySelector('.rd-mode-btn[onclick*="top-global"]');
        if (topGlobalBtn && topGlobalBtn.classList.contains('active')) {{
            renderTopGlobal(tabId, date);
        }}
        
        // Atualizar os cards analíticos do topo dinamicamente
        var decksPlayed = parseFloat(element.getAttribute('data-decks-played')) || 0;
        var decksRemaining = parseFloat(element.getAttribute('data-decks-remaining')) || 200;
        var efficiency = parseFloat(element.getAttribute('data-efficiency')) || 0.0;
        var projectedFame = parseFloat(element.getAttribute('data-projected-fame')) || 0;
        
        var decksValEl = document.getElementById('rd-decks-value-' + tabId);
        var decksSubEl = document.getElementById('rd-decks-sub-' + tabId);
        var effValEl = document.getElementById('rd-efficiency-value-' + tabId);
        var projValEl = document.getElementById('rd-projection-value-' + tabId);
        
        if (decksValEl) {{ decksValEl.textContent = decksPlayed + ' / 200'; }}
        if (decksSubEl) {{ decksSubEl.textContent = decksRemaining + ' restantes'; }}
        if (effValEl) {{ effValEl.textContent = efficiency.toFixed(1) + '%'; }}
        if (projValEl) {{ projValEl.textContent = Math.round(projectedFame).toLocaleString() + ' ⭐'; }}
        
        // Atualizar o painel de resumo com fama e posicao do dia clicado
        var fame = element.getAttribute('data-fame') || '0';
        var pos  = element.getAttribute('data-position') || '0';
        var summaryEl   = document.getElementById('rd-war-summary-' + tabId);
        var dateEl      = document.getElementById('rd-summary-date-' + tabId);
        var posEl       = document.getElementById('rd-summary-pos-' + tabId);
        var fameEl      = document.getElementById('rd-summary-fame-' + tabId);
        
        if (summaryEl) {{
            summaryEl.style.display = 'block';
            if (dateEl)  dateEl.textContent  = date.replace(/_/g, '-');
            if (posEl)   posEl.textContent   = pos > 0 ? '#' + pos : '—';
            if (fameEl)  fameEl.textContent  = parseInt(fame).toLocaleString() + ' ⭐';
        }}
        
        // Salvar selecao do dia no localStorage por tab
        localStorage.setItem('cr_radar_day_' + tabId, date);
    }}
    
    // Task 3: Restaurar conta e dia selecionado do localStorage ao carregar a pagina
    document.addEventListener('DOMContentLoaded', function() {{
        // Restaurar conta ativa
        let savedAccount = localStorage.getItem('cr_active_account');
        if (!savedAccount) {{
            // Se não houver conta ativa no localStorage (ex: primeira visita), ativa a primeira aba do topo
            const firstTab = document.querySelector('.cr-dashboard-main-header .cr-tab');
            if (firstTab) {{
                const match = firstTab.getAttribute('onclick').match(/'([^']+)'/);
                if (match) {{
                    savedAccount = match[1];
                }}
            }}
        }}
        
        if (savedAccount) {{
            const savedTab = document.querySelector(`.cr-tab[onclick*="${{savedAccount}}"]`);
            if (savedTab) {{
                savedTab.dispatchEvent(new Event('click', {{ bubbles: true }}));
            }}
        }}
        
        // Task 3: Restaurar o dia de guerra salvo por tab (pri/sec) ou simular clique inicial no dia ativo/primeiro
        ['pri', 'sec'].forEach(function(tabId) {{
            var savedDay = localStorage.getItem('cr_radar_day_' + tabId);
            var calendarEl = document.getElementById('rd-calendar-' + tabId);
            if (!calendarEl) return;
            
            var dayBtn = null;
            if (savedDay) {{
                // Localizar o botao do dia salvo
                dayBtn = calendarEl.querySelector('.rd-calendar-day[data-date="' + savedDay + '"]');
            }}
            
            // Se nao encontrou botao salvo, tenta o dia ativo do sistema (.rd-calendar-day-active)
            if (!dayBtn) {{
                dayBtn = calendarEl.querySelector('.rd-calendar-day.rd-calendar-day-active');
            }}
            
            // Se ainda assim nao encontrou, tenta o primeiro dia disponivel (Reset)
            if (!dayBtn) {{
                dayBtn = calendarEl.querySelector('.rd-calendar-day');
            }}
            
            if (dayBtn) {{
                var date = dayBtn.getAttribute('data-date');
                selectWarDay(tabId, date, dayBtn, true);
            }}
        }});
    }});

    // Table sorting functionality
    document.addEventListener('DOMContentLoaded', function() {{
        var table = document.getElementById('clan-members-table');
        if (!table) return;
        
        var headers = table.querySelectorAll('th.sortable');
        var currentSort = {{ column: '', direction: '' }};
        
        headers.forEach(function(header) {{
            header.addEventListener('click', function() {{
                var column = this.getAttribute('data-column');
                var direction = currentSort.column === column && currentSort.direction === 'asc' ? 'desc' : 'asc';
                
                headers.forEach(function(h) {{ h.classList.remove('sort-asc', 'sort-desc'); }});
                this.classList.add('sort-' + direction);
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
    <script>
    function copyDeckLink(e, btn, link) {{
        if(e) {{
            e.preventDefault();
            e.stopPropagation();
        }}
        
        function fallbackCopy() {{
            navigator.clipboard.writeText(link).then(() => {{
                const originalHTML = btn.innerHTML;
                const isSmall = originalHTML.includes('📋') || originalHTML.includes('span');
                btn.innerHTML = isSmall ? '✔️' : '<i class="fas fa-check"></i> Copiado!';
                btn.style.color = '#4CAF50';
                btn.style.borderColor = '#4CAF50';
                setTimeout(() => {{
                    btn.innerHTML = originalHTML;
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }}, 2000);
            }}).catch(err => {{
                console.error('Falha ao copiar:', err);
                window.open(link, '_blank');
            }});
        }}

        if (navigator.share) {{
            navigator.share({{
                title: 'Deck Clash Royale',
                text: 'Copie ou abra este deck no Clash Royale:',
                url: link
            }}).catch(err => {{
                if (err.name !== 'AbortError') {{
                    console.error('Falha ao compartilhar:', err);
                    fallbackCopy();
                }}
            }});
        }} else {{
            fallbackCopy();
        }}
    }}
    </script>
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
    
    # Salva HTML e valida tamanho minimo para evitar commits truncados
    index_path = os.path.join(root_dir, 'docs', 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    html_size = len(html_content)
    MIN_SIZE = 700000  # ~700KB - HTML completo tem ~1.2MB mas pode variar
    if html_size < MIN_SIZE:
        logger.error(f"ERRO CRITICO: HTML truncado ({html_size} bytes < {MIN_SIZE}). Regenerando...")
        import sys
        sys.exit(1)
    
    logger.info(f"GitHub Pages HTML report gerado: {index_path} ({html_size} bytes)")

if __name__ == "__main__":
    main()
