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
from datetime import datetime, timezone
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
        
        self.failed_tags = set()
        # Caches carregados diretamente do CSV (ignora SQL)
        self.battles_cache = self._load_all_battles_from_csv('#2QR292P')
        self.clan_members_cache = self._load_clan_members_csv()
        self.rankings_history_cache = self._load_csv_as_list('clan_rankings_history.csv')
        self.clan_decks_cache = self._load_csv_as_list('clan_member_decks.csv')
        self.players_cache = self._load_csv_as_list('players.csv')
        
    def _load_csv_as_list(self, filename: str) -> List[Dict]:
        """Auxiliar para carregar qualquer CSV da pasta oficial como lista de dicts"""
        path = os.path.join('src', 'data_csv_oficial', filename)
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

    def _load_all_battles_from_csv(self, player_tag: str = '#2QR292P') -> List[Dict]:
        """Lê todos os CSVs de batalha e unifica em uma lista, sem usar SQL"""
        battles = []
        pattern = os.path.join('src', 'data_csv_oficial', 'oponentes_*.csv')
        files = glob.glob(pattern)
        
        # Também inclui battles.csv se existir
        battles_csv = os.path.join('src', 'data_csv_oficial', 'battles.csv')
        if os.path.exists(battles_csv):
            files.append(battles_csv)
            
        logger.info(f"Lendo {len(files)} arquivos CSV de batalha para o player {player_tag}...")
        
        for file in files:
            try:
                # Usa encoding latin1 para lidar com nomes com acento se utf-8 falhar
                try:
                    f = open(file, mode='r', encoding='utf-8')
                    reader = csv.DictReader(f)
                    data = list(reader)
                    f.close()
                except UnicodeDecodeError:
                    f = open(file, mode='r', encoding='latin1')
                    reader = csv.DictReader(f)
                    data = list(reader)
                    f.close()

                for row in data:
                    # Filtro de player_tag
                    row_tag = row.get('player_tag')
                    if row_tag and row_tag != player_tag and player_tag != '#YVJR0JLY':
                        # Se estivermos buscando a tag antiga e o row for da tag nova, ignoramos (ou vice-versa)
                        # Mas se o usuário quer unificado, podemos remover esse filtro ou torná-lo flexível
                        if row_tag not in ['#2QR292P', '#YVJR0JLY']:
                            continue
                            
                    # Normaliza resultado
                    res = row.get('resultado', row.get('result', '')).lower()
                    if any(x in res for x in ['vitoria', 'victory', 'vitória']):
                        norm_res = 'victory'
                    elif any(x in res for x in ['derrota', 'defeat']):
                        norm_res = 'defeat'
                    elif any(x in res for x in ['empate', 'draw']):
                        norm_res = 'draw'
                    else:
                        norm_res = 'draw' # fallback
                        
                    # Normaliza campos
                    b_time = row.get('data', row.get('battle_time', ''))
                    opp_name = row.get('oponente', row.get('opponent_name', 'Oponente'))
                    opp_tag = row.get('tag_oponente', row.get('opponent_tag', ''))
                    crowns = row.get('coroas', row.get('crowns', '0'))
                    arena = row.get('arena', row.get('arena_name', 'Arena'))
                    deck_p = row.get('deck_jogador', row.get('deck_cards', ''))
                    deck_o = row.get('deck_oponente', row.get('opponent_deck_cards', ''))
                    clan_o = row.get('cla_oponente', row.get('opponent_clan_name', ''))
                    
                    # Níveis de cartas (se houver)
                    levels_p = row.get('deck_card_levels', '')
                    levels_o = row.get('opponent_deck_card_levels', '')
                    p_level = row.get('player_level', row.get('nivel_jogador', '0'))
                    o_level = row.get('opponent_level', row.get('nivel_oponente', '0'))
                    
                    try:
                        t_change = int(row.get('mudanca_trofes', row.get('trophy_change', 0)) or 0)
                    except:
                        t_change = 0
                        
                    battles.append({
                        'battle_time': b_time,
                        'result': norm_res,
                        'player_tag': player_tag,
                        'opponent_name': opp_name,
                        'opponent_tag': opp_tag,
                        'crowns': crowns,
                        'arena_name': arena,
                        'deck_cards': deck_p,
                        'deck_card_levels': levels_p,
                        'player_level': int(p_level or 0),
                        'opponent_deck_cards': deck_o,
                        'opponent_deck_card_levels': levels_o,
                        'opponent_level': int(o_level or 0),
                        'opponent_clan_name': clan_o,
                        'trophy_change': t_change
                    })
            except Exception as e:
                logger.error(f"Erro ao processar {file}: {e}")
        
        # Ordena por tempo
        battles.sort(key=lambda x: x['battle_time'] or '', reverse=True)
        return battles

    def _load_clan_members_csv(self) -> List[Dict]:
        """Lê clan_members.csv diretamente"""
        members = []
        path = os.path.join('src', 'data_csv_oficial', 'clan_members.csv')
        if not os.path.exists(path):
            return []
        try:
            with open(path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    members.append(row)
        except Exception as e:
            logger.error(f"Erro ao ler clan_members.csv: {e}")
        return members
        
        # Card name mapping for file names (GitHub Pages uses relative paths)
        self.card_name_mapping = {
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
    
    def get_card_filename(self, card_name: str) -> str:
        """Convert card name to filename"""
        return self.card_name_mapping.get(card_name, card_name.replace(' ', '').replace('.', '').replace('-', ''))
    
    def safe_filename(self, name: str) -> str:
        """Convert member name to safe filename"""
        # Remove special characters and spaces
        safe_name = re.sub(r'[^\w\s-]', '', name)
        safe_name = re.sub(r'\s+', '_', safe_name)
        return safe_name.lower()
    
    def get_card_image_path(self, card_name: str) -> str:
        """Get the relative path to card image or fallback to RoyaleAPI CDN"""
        filename = self.get_card_filename(card_name)
        
        # Check if it's an evolution (usually represented as 'Card Name (Evolution)' in some data sources)
        is_evolution = "Evolution" in card_name
        clean_name = card_name.replace(" (Evolution)", "") if is_evolution else card_name
        
        # Try local files first
        cards_base = "../cards" if os.path.exists("../cards") else "cards"
        
        # Priority search order for filenames
        search_paths = [
            f"{cards_base}/hero_cards/{filename}.png",
            f"{cards_base}/evolution_cards/{filename}.png",
            f"{cards_base}/normal_cards/{filename}.png"
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                # Return path relative to the generated index.html location (which is inside docs/ or root)
                # If we are in src/, the path to cards is ../cards/
                # If we are in docs/, the path to cards is cards/
                return path.replace("../", "")
            
        # 4. CDN Fallback (RoyaleAPI)
        # Convert name to RoyaleAPI format (lowercase, no spaces, hyphens)
        cdn_name = card_name.lower().replace(" ", "-").replace(".", "").replace("'", "")
        if is_evolution:
            cdn_name = cdn_name.replace("-evolution", "")
            return f"https://royaleapi.com/static/img/cards-150/{cdn_name}-ev1.png"
        
        # Special CDN mapping for some heroes or problematic names
        cdn_mapping = {
            'archer-queen': 'archer-queen',
            'mighty-miner': 'mighty-miner',
            'golden-knight': 'golden-knight',
            'skeleton-king': 'skeleton-king',
            'little-prince': 'little-prince',
            'monk': 'monk',
            'the-log': 'log',
            'pe-kk-a': 'pekka',
            'mini-pe-kk-a': 'mini-pekka'
        }
        cdn_name = cdn_mapping.get(cdn_name, cdn_name)
        
        return f"https://royaleapi.com/static/img/cards-150/{cdn_name}.png"
    
    def get_player_stats(self) -> Optional[Dict]:
        """Get player statistics from CSV files"""
        player_row = self._load_players_csv('#2QR292P')
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
            o_name = latest_b.get('opponent_name', 'Desconhecido')
            latest_o_trophies = latest_b.get('opponent_trophies', 0)
            
            stats = self._get_opponent_period_stats_from_cache(battles)
            
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
                'stats': stats,
                'best_deck': best_deck
            })
            
        # Ordena por total de batalhas desc, win rate do usuário asc (nemeses primeiro)
        results.sort(key=lambda x: (x['total_battles'], -x['user_win_rate']), reverse=True)
        return results

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
            player_tag = '#2QR292P'
            
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
                dt = dt.replace(tzinfo=timezone.utc)
                
            time_diff = now - dt
            
            if time_diff.days > 0:
                return f"{time_diff.days} days ago"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                return f"{hours} hours ago"
            elif time_diff.seconds > 60:
                minutes = time_diff.seconds // 60
                return f"{minutes} minutes ago"
            else:
                return "just now"
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
                                            stats: Dict, player_tag: str = None) -> str:
        """Generate HTML for deck performance section with 2 tabs: Meus Decks da Semana + Oponentes Repetidos"""

        # Aba 1: Meus Decks da Semana - le CSVs diarios
        weekly_data = self.get_weekly_decks_from_csv()
        weekly_decks_html = self.generate_weekly_decks_html(weekly_data)

        # Aba 2: Oponentes Repetidos - le CSVs anuais
        csv_repeated = self.get_repeated_opponents_from_csv()
        repeated_opponents_html = self.generate_repeated_opponents_html(csv_repeated)

        return f"""
        <div class="deck-tabs-container">
            <div class="deck-tabs">
                <button class="tab-button active" onclick="switchDeckTab(event, 'repeated-opponents')">Oponentes Repetidos</button>
                <button class="tab-button" onclick="switchDeckTab(event, 'weekly-decks')">Meus Decks da Semana</button>
            </div>

            <div id="tab-repeated-opponents" class="tab-content active">
                {repeated_opponents_html if repeated_opponents_html else '<p>Nenhum oponente encontrado que voce enfrentou mais de uma vez.</p>'}
            </div>

            <div id="tab-weekly-decks" class="tab-content">
                {weekly_decks_html}
            </div>
        </div>
        {self.generate_dashboard_scripts()}
        """
    def load_all_data_rows(self) -> List[Dict]:
        """Carrega e unifica dados de todas as fontes disponíveis via CSV diretamente."""
        logger.info("Carregando dados das batalhas de todos os CSVs disponíveis")
        
        # Carrega todas as batalhas usando o helper
        battles_list = self._load_all_battles_from_csv('#2QR292P')
        
        all_data = []
        for b in battles_list:
            all_data.append({
                'battle_time': b['battle_time'],
                'opponent_name': b.get('opponent_name', 'Oponente'),
                'opponent_tag': b.get('opponent_tag', ''),
                'result': b['result'],
                'deck_cards': b.get('deck_cards', ''),
                'opponent_deck_cards': b.get('opponent_deck_cards', ''),
                'opponent_clan_name': b.get('opponent_clan_name', '')
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
            dt = row['dt']
            is_recent = dt >= seven_days_ago
            cards = row['deck_jogador']
            if not cards: continue
            
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
                
            res = row['resultado']
            if res in ['vitoria', 'victory']: deck_stats[cards]['wins'] += 1
            elif res in ['derrota', 'defeat']: deck_stats[cards]['losses'] += 1
            
            if len(deck_stats[cards]['battles']) < 30:
                deck_stats[cards]['battles'].append({
                    'resultado': res, 
                    'data': dt.strftime('%d/%m %H:%M'),
                    'dt_obj': dt,
                    'my_deck': row['deck_jogador'],
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
            
        # ORDENAÇÃO CRÍTICA: Decks usados RECENTEMENTE e com maior volume na semana no topo
        # (recent_total, win_rate, total)
        final_list.sort(key=lambda x: (x['recent_total'], x['win_rate'], x['total']), reverse=True)
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
            def card_img(n):
                return f'<div class="cr-card-wrap" title="{n}"><img src="{self.get_card_image_path(n)}" class="cr-card-img" loading="lazy"></div>'
            
            grid_h = f'<div class="cr-cards-grid"><div class="cr-cards-row">{"".join(card_img(c) for c in cards_list[:4])}</div><div class="cr-cards-row">{"".join(card_img(c) for c in cards_list[4:8])}</div></div>'

            # Timeline com data e hora
            timeline_h = ""
            for idx, b in enumerate(deck['battles'][:15]):
                res = b['resultado'].lower()
                cor = '#48bb78' if res in ['vitoria','victory'] else ('#f56565' if res in ['derrota','defeat'] else '#ed8936')
                ic = 'V' if res in ['vitoria','victory'] else ('D' if res in ['derrota','defeat'] else 'E')
                b_json = urllib.parse.quote(json.dumps({'my_deck': b['my_deck'], 'opp_deck': b['opp_deck']}))
                active = "box-shadow: 0 0 0 3px #4299e1; transform: scale(1.1);" if idx == 0 else ""
                
                # Formata data para a timeline usando o objeto datetime
                d_short = b['dt_obj'].strftime('%d/%m')
                h_short = b['dt_obj'].strftime('%H:%M')
                
                timeline_h += f'''
                <div style="display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;" onclick="updateBattlePreview('{deck_id}', {idx}, '{b_json}')">
                    <span class="cr-battle-badge" style="background:{cor};{active}" title="{b["data"]}">{ic}</span>
                    <span style="font-size:0.6em;color:#4a5568;font-weight:bold;">{d_short}</span>
                </div>'''

            # Preview VS aprimorado
            first_battle = deck['battles'][0] if deck['battles'] else {}
            my_deck_init = first_battle.get('my_deck', deck['deck_cards'])
            opp_deck_init = first_battle.get('opp_deck', '')
            
            def get_preview_grid(d_str, side_class):
                if not d_str: return f'<div class="{side_class}" style="width:100px;height:60px;border:1px dashed #ccc;display:flex;align-items:center;justify-content:center;font-size:0.7em;color:#999;">N/D</div>'
                cards = [c.strip() for c in d_str.replace(' | ','|').split('|')]
                return f'''<div class="{side_class}"><div class="cr-cards-grid" style="gap:2px;padding:0;">
                    <div class="cr-cards-row" style="gap:2px;">{"".join(f'<div class="cr-card-wrap" style="width:22px;height:26px;" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img"></div>' for c in cards[:4])}</div>
                    <div class="cr-cards-row" style="gap:2px;">{"".join(f'<div class="cr-card-wrap" style="width:22px;height:26px;" title="{c}"><img src="{self.get_card_image_path(c)}" class="cr-card-img"></div>' for c in cards[4:8])}</div>
                </div></div>'''

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
                        <div id="preview-{deck_id}" class="cr-battle-preview" style="background:linear-gradient(to bottom, #f8fafc, #f1f5f9); padding:10px; border-radius:12px; margin-bottom:10px; display:flex; gap:8px; align-items:center; justify-content:center; border:1px solid #e2e8f0; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
                            <div style="text-align:center;"><small style="font-size:0.5em;color:#718096;font-weight:bold;">MEU DECK</small>{get_preview_grid(my_deck_init, 'my-deck-side')}</div>
                            <div style="font-weight:bold;color:#cbd5e0;font-size:0.8em;">VS</div>
                            <div style="text-align:center;"><small style="font-size:0.5em;color:#718096;font-weight:bold;">OPONENTE</small>{get_preview_grid(opp_deck_init, 'opp-deck-side')}</div>
                        </div>
                        <div class="cr-battles-timeline"><div class="cr-timeline-badges timeline-{deck_id}" style="display:flex; gap:8px; overflow-x:auto; padding:5px 0;">{timeline_h}</div></div>
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
            tag = b['tag_oponente']
            if not tag: continue
            
            if tag not in opp_stats:
                opp_stats[tag] = {
                    'tag': tag, 
                    'nome': b['nome_oponente'], 
                    'total': 0, 
                    'wins': 0, 
                    'losses': 0, 
                    'battles': [], 
                    'last_deck': b['deck_oponente']
                }
            
            opp_stats[tag]['total'] += 1
            res = b['resultado']
            if res in ['vitoria', 'victory']: opp_stats[tag]['wins'] += 1
            elif res in ['derrota', 'defeat']: opp_stats[tag]['losses'] += 1
            
            dt = b['dt']
            d_display = dt.strftime('%d/%m %H:%M')
                
            opp_stats[tag]['battles'].append({
                'resultado': res, 
                'data_str': d_display,
                'my_deck': b['deck_jogador'],
                'opp_deck': b['deck_oponente'],
                'dt_obj': dt # Para ordenação posterior
            })
            if b.get('deck_oponente'): opp_stats[tag]['last_deck'] = b['deck_oponente']

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
                
                const myDeckHtml = getMiniGridJS(data.my_deck, 'my-deck-side');
                const oppDeckHtml = getMiniGridJS(data.opp_deck, 'opp-deck-side');
                
                previewContainer.innerHTML = `
                    <div style="text-align:center;"><small style="font-size:0.5em;color:#718096;font-weight:bold;">MEU DECK</small>${myDeckHtml}</div>
                    <div style="font-weight:bold;color:#cbd5e0;font-size:0.8em;">VS</div>
                    <div style="text-align:center;"><small style="font-size:0.5em;color:#718096;font-weight:bold;">OPONENTE</small>${oppDeckHtml}</div>
                `;
                
                const timeline = document.querySelector('.timeline-' + deckId);
                if (timeline) {
                    timeline.querySelectorAll('.cr-battle-badge').forEach((b, i) => {
                        if (i === battleIdx) {
                            b.style.boxShadow = '0 0 0 3px #4299e1';
                            b.style.transform = 'scale(1.1)';
                        } else {
                            b.style.boxShadow = 'none';
                            b.style.transform = 'scale(1)';
                        }
                    });
                }
            } catch(e) { console.error("Error updating preview:", e); }
        }
        
        function getMiniGridJS(deckStr, sideClass) {
            if (!deckStr) return '<div style="width:100px;height:60px;border:1px dashed #ccc;display:flex;align-items:center;justify-content:center;font-size:0.7em;color:#999;">N/D</div>';
            const cards = deckStr.replace(/ \| /g, '|').split('|');
            return `
                <div class="${sideClass}">
                    <div class="cr-cards-grid" style="gap:2px;padding:0;">
                        <div class="cr-cards-row" style="gap:2px;">${cards.slice(0,4).map(c => `<div class="cr-card-wrap" style="width:22px;height:26px;" title="${c.trim()}"><img src="cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png" class="cr-card-img" onerror="this.src='https://royaleapi.github.io/cr-api-assets/cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png';"></div>`).join('')}</div>
                        <div class="cr-cards-row" style="gap:2px;">${cards.slice(4,8).map(c => `<div class="cr-card-wrap" style="width:22px;height:26px;" title="${c.trim()}"><img src="cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png" class="cr-card-img" onerror="this.src='https://royaleapi.github.io/cr-api-assets/cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png';"></div>`).join('')}</div>
                    </div>
                </div>
            `;
        }

        function switchDeckTab(event, tabName) {
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            if (event) event.currentTarget.classList.add('active');
        }
        </script>
        """

    def generate_repeated_opponents_html(self, opponents: List[Dict]) -> str:
        """Gera HTML para oponentes repetidos no estilo Premium com Preview de Batalha e Categorização de Rivalidade."""
        if not opponents: return '<div class="cr-empty-state">Nenhum oponente repetido encontrado no histórico recente.</div>'
        
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
            
            # Cálculo de porcentagens para a barra de progresso
            w_p = round((wins/total*100),1) if total > 0 else 0
            l_p = round((losses/total*100),1) if total > 0 else 0
            d_p = round(max(0, 100 - w_p - l_p), 1)
            
            # Pega a batalha mais recente
            stats = opp['stats']
            last_b = stats[0] if stats else {} # Usando o campo 'stats' que contem as batalhas individuais
            my_deck_last = last_b.get('my_deck', '')
            opp_deck_last = last_b.get('opp_deck', '')
            
            def get_deck_grid_html(deck_str, side_class):
                if not deck_str: return f'<div class="{side_class}" style="width:140px;height:100px;border:1px dashed #cbd5e0;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#a0aec0;font-size:0.8em;">Deck N/D</div>'
                c_list = [c.strip() for c in deck_str.replace(' | ','|').split('|')]
                def c_h(n):
                    img = self.get_card_image_path(n)
                    return f'<div class="cr-card-wrap" title="{n}" style="width:38px;height:45px;"><img src="{img}" class="cr-card-img" loading="lazy"></div>'
                t_h = "".join(c_h(c) for c in c_list[:4])
                b_h = "".join(c_h(c) for c in c_list[4:8])
                return f'<div class="{side_class}"><div class="cr-cards-grid" style="gap:2px;padding:0;"><div class="cr-cards-row" style="gap:2px;">{t_h}</div><div class="cr-cards-row" style="gap:2px;">{b_h}</div></div></div>'

            preview_html = f"""
            <div id="preview-{tag_clean}" class="cr-battle-preview" style="display:flex; justify-content:space-around; align-items:center; gap:10px; padding:12px; background:linear-gradient(to bottom, #f8fafc, #f1f5f9); border-radius:12px; margin:10px 0; border:1px solid #e2e8f0; box-shadow: inset 0 2px 4px 0 rgba(0,0,0,0.05);">
                <div style="text-align:center;"><small style="color:#718096;display:block;margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Meu Deck</small>{get_deck_grid_html(my_deck_last, 'my-deck-side')}</div>
                <div style="font-weight:900; color:#cbd5e0; font-size:1.2em; text-shadow: 1px 1px 0 #fff;">VS</div>
                <div style="text-align:center;"><small style="color:#718096;display:block;margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Oponente</small>{get_deck_grid_html(opp_deck_last, 'opp-deck-side')}</div>
            </div>
            """
            
            timeline = ""
            for idx, b in enumerate(stats[:15]):
                res = b['result'].lower()
                d_f = b['battle_time'].split('T')[0].split('-')[-1] + "/" + b['battle_time'].split('T')[0].split('-')[-2]
                h_f = b['battle_time'].split('T')[1][:5]
                
                cor = '#48bb78' if res in ['vitoria','victory'] else ('#f56565' if res in ['derrota','defeat'] else '#ed8936')
                ic = 'V' if res in ['vitoria','victory'] else ('D' if res in ['derrota','defeat'] else 'E')
                
                b_data = urllib.parse.quote(json.dumps({
                    'my_deck': b['my_deck'],
                    'opp_deck': b['opp_deck']
                }))
                
                active_style = "box-shadow: 0 0 0 3px #4299e1; transform: scale(1.1);" if idx == 0 else ""
                
                timeline += f'''
                <div style="display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;transition:all 0.2s;" onclick="updateBattlePreview('{tag_clean}', {idx}, '{b_data}')" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
                    <span class="cr-battle-badge" style="background:{cor};{active_style}">{ic}</span>
                    <span style="font-size:0.65em;color:#4a5568;font-weight:700;">{d_f}</span>
                    <span style="font-size:0.55em;color:#718096;">{h_f}</span>
                </div>'''

            wr_c = '#48bb78' if wr >= 60 else ('#f56565' if wr <= 40 else '#718096')
            
            html += f'''
            <div class="cr-deck-card" style="padding:15px;">
                <div class="cr-deck-header" style="margin-bottom:12px;">
                    <div class="cr-deck-meta">
                        <span class="cr-deck-rank">#{i}</span>
                        <span class="cr-deck-label" style="font-size:1.1em;">{opp['opponent_name']}</span>
                        <span class="{cat_class}-badge">{category}</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:0.75em;color:#718096;font-family:monospace;display:block;margin-bottom:2px;">{opp['opponent_tag']}</span>
                        <span class="cr-wr-badge" style="background:{wr_c}; font-size:0.9em; padding:4px 10px;">{wr}% WR</span>
                    </div>
                </div>

                <div class="cr-h2h-panel {cat_class}">
                    <div style="font-size:0.8em; font-weight:700; color:#4a5568;">HEAD-TO-HEAD:</div>
                    <div style="display:flex; gap:10px; font-size:0.9em; font-weight:800;">
                        <span style="color:#38a169;">{wins}V</span>
                        <span style="color:#718096;">{draws}E</span>
                        <span style="color:#e53e3e;">{losses}D</span>
                    </div>
                    <div style="margin-left:auto; font-size:0.75em; color:#718096;">Último: {opp['last_encounter'][:16].replace('T', ' ')}</div>
                </div>
                
                {preview_html}
                
                <div class="cr-progress-bar" style="height:8px; margin-bottom:15px;"><div class="cr-bar-wins" style="width:{w_p}%;"></div><div class="cr-bar-draws" style="width:{d_p}%;"></div><div class="cr-bar-losses" style="width:{l_p}%;"></div></div>
                
                <div class="cr-deck-body" style="padding-top:0;">
                    <div class="cr-stats-panel" style="width:100%;">
                        <div class="cr-battles-timeline" style="background:#f8fafc; padding:10px; border-radius:10px; border:1px solid #edf2f7;">
                            <div class="cr-timeline-label" style="font-size:0.75em; color:#718096; margin-bottom:8px; font-weight:600; text-transform:uppercase;">Histórico de Batalhas (Clique para ver os decks)</div>
                            <div class="cr-timeline-badges timeline-{tag_clean}" style="display:flex;gap:10px;padding:5px 0;overflow-x:auto;">{timeline}</div>
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
            
            # Gera HTML das abas de decks (Meus Decks da Semana + Oponentes Repetidos)
            # Os dados são lidos internamente via CSVs
            deck_performance_html = self.generate_deck_performance_with_tabs(
                [], [], [], [], stats, player_tag
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
                
                battles_table_html += f"""
                    <tr class="battle-{result_class}">
                        <td>{self.format_time_ago(battle['battle_time'])}</td>
                        <td><span class="result-{result_class}">{result_display}</span></td>
                        <td>{battle['opponent_name']}</td>
                        <td>{battle['crowns']}</td>
                        <td style="color: {trophy_color}">{int(battle['trophy_change']):+d}</td>
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
                                         battles_table_html, battles_cards_html)
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
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        @font-face {
            font-family: 'Clash-Regular';
            src: url('assets/fonts/Clash_Regular.otf') format('opentype');
            font-weight: normal;
            font-style: normal;
        }
        
        @font-face {
            font-family: 'Supercell-Magic';
            src: url('assets/fonts/Supercell-Magic Regular.ttf') format('truetype');
            font-weight: normal;
            font-style: normal;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
        }
        
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Clash-Regular', 'Supercell-Magic', sans-serif;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
        
        .header h1 {
            color: #4a5568;
            text-align: center;
            margin-bottom: 20px;
            font-size: 2.5em;
        }
        
        .player-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.8);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        
        .stat-card h3 {
            color: #2d3748;
            margin-bottom: 10px;
            white-space: normal;
            word-break: keep-all;
            line-height: 1.4;
        }
        
        .stat-card h3 br {
            display: block;
        }
        
        .stat-card .value {
            font-size: 1.8em;
            font-weight: bold;
            color: #4299e1;
        }
        
        .section {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
        
        .section h2 {
            color: #2d3748;
            margin-bottom: 25px;
            border-bottom: 3px solid #4299e1;
            padding-bottom: 10px;
        }
        
        /* ============================================================
           Clash Royale Top-Decks style – cr-deck-card components
           ============================================================ */
        .cr-decks-list {
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-top: 10px;
        }

        .cr-deck-card {
            background: #fff;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
            transition: box-shadow 0.2s;
        }
        .cr-deck-card:hover {
            box-shadow: 0 6px 20px rgba(0,0,0,0.13);
        }

        .cr-deck-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px 8px 14px;
            border-bottom: 1px solid #edf2f7;
            background: #f7fafc;
        }
        .cr-deck-meta {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .cr-deck-rank {
            background: #4299e1;
            color: #fff;
            font-weight: 700;
            font-size: 0.82em;
            padding: 2px 8px;
            border-radius: 20px;
        }
        .cr-deck-label {
            font-size: 0.85em;
            color: #4a5568;
            font-weight: 600;
        }
        .cr-wr-badge {
            color: #fff;
            font-size: 0.82em;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 20px;
        }

        /* Barra de progresso W / D / L */
        .cr-progress-bar {
            display: flex;
            height: 8px;
            width: 100%;
        }
        .cr-bar-wins   { background: #48bb78; transition: width 0.4s; }
        .cr-bar-draws  { background: #ed8936; transition: width 0.4s; }
        .cr-bar-losses { background: #f56565; transition: width 0.4s; }

        /* Corpo: cards (esq) + stats (dir) */
        .cr-deck-body {
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            padding: 14px;
        }

        /* Grid 4+4 de cartas */
        .cr-cards-grid {
            display: flex;
            flex-direction: column;
            gap: 6px;
            flex-shrink: 0;
        }
        .cr-cards-row {
            display: flex;
            gap: 5px;
        }
        .cr-card-wrap {
            width: 64px;
            height: 72px;
            background: #1a202c;
            border-radius: 8px;
            overflow: hidden;
            border: 2px solid #4a5568;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.25);
            transition: transform 0.15s;
        }
        .cr-card-wrap:hover { transform: scale(1.08); }
        .cr-card-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        /* Painel de estatisticas */
        .cr-stats-panel {
            flex: 1;
            min-width: 200px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .cr-stats-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.87em;
            background: transparent;
            border-radius: 0;
            overflow: visible;
        }

        /* Estilos de Rivais */
        .nemesis-badge { background: #e53e3e; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.05em; }
        .customer-badge { background: #38a169; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.05em; }
        .balanced-badge { background: #718096; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.05em; }
        
        .cr-h2h-panel {
            display: flex;
            align-items: center;
            gap: 15px;
            background: #fdf2f2;
            padding: 8px 12px;
            border-radius: 8px;
            border-left: 4px solid #e53e3e;
            margin-bottom: 10px;
        }
        .cr-h2h-panel.customer { background: #f0fff4; border-left-color: #38a169; }
        .cr-h2h-panel.balanced { background: #f7fafc; border-left-color: #718096; }
        .cr-stats-table th {
            background: #f7fafc;
            color: #718096;
            font-weight: 600;
            font-size: 0.8em;
            padding: 5px 8px;
            border-bottom: 1px solid #e2e8f0;
            text-align: center;
        }
        .cr-stats-table td {
            text-align: center;
            padding: 5px 8px;
            border-bottom: none;
            font-weight: 600;
            color: #2d3748;
        }
        .cr-th-win, .cr-td-win { color: #48bb78 !important; }
        .cr-th-draw,.cr-td-draw{ color: #ed8936 !important; }
        .cr-th-loss,.cr-td-loss{ color: #f56565 !important; }

        /* Timeline de batalhas */
        .cr-battles-timeline {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .cr-timeline-label {
            font-size: 0.75em;
            color: #718096;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .cr-timeline-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }
        .cr-battle-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 22px;
            height: 22px;
            border-radius: 4px;
            border: 1.5px solid transparent;
            color: #fff;
            font-weight: 700;
            font-size: 0.72em;
            cursor: default;
            padding: 0 3px;
            gap: 3px;
        }
        .cr-badge-with-date {
            min-width: 70px;
            height: auto;
            padding: 3px 6px;
            border-radius: 6px;
            flex-direction: column;
            gap: 1px;
            font-size: 0.78em;
        }
        .cr-badge-date {
            font-size: 0.78em;
            font-weight: 500;
            opacity: 0.92;
            white-space: nowrap;
        }
        .cr-no-deck {
            font-size: 0.82em;
            color: #a0aec0;
            padding: 8px;
            font-style: italic;
        }
        .cr-opp-deck-label {
            font-size: 0.75em;
            color: #718096;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 6px;
        }

        @media (max-width: 600px) {
            .cr-deck-body { flex-direction: column; }
            .cr-card-wrap { width: 52px; height: 60px; }
        }
        /* ============================================================ */

        .deck-tabs-container {
            margin-top: 20px;
        }
        
        .deck-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e2e8f0;
        }
        
        .tab-button {
            background: transparent;
            border: none;
            padding: 12px 20px;
            font-size: 1em;
            font-weight: 600;
            color: #718096;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.3s ease;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .tab-button:hover {
            color: #4299e1;
            background: rgba(66, 153, 225, 0.1);
        }
        
        .tab-button.active {
            color: #4299e1;
            border-bottom-color: #4299e1;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .deck-item {
            background: rgba(247, 250, 252, 0.8);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #e2e8f0;
        }
        
        .deck-header {
            margin-bottom: 15px;
        }
        
        .deck-header h3 {
            color: #2d3748;
            margin-bottom: 8px;
        }
        
        .deck-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .stat {
            background: rgba(255, 255, 255, 0.8);
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }
        
        .deck-cards {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-top: 15px;
        }
        
        .deck-cards-compact {
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            gap: 8px;
            margin-top: 15px;
            justify-content: flex-start;
        }
        
        @media (max-width: 768px) {
            .deck-cards-compact {
                grid-template-columns: repeat(4, 1fr);
            }
        }
        
        .deck-cards-compact .card-container {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 5px;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }
        
        .deck-cards-compact .card-image {
            width: 100%;
            max-width: 100px;
            height: auto;
            object-fit: contain;
            border-radius: 5px;
        }
        
        .card-container {
            text-align: center;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            padding: 10px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .card-image {
            width: 60px;
            height: 72px;
            object-fit: contain;
            border-radius: 5px;
        }
        
        .card-name {
            font-size: 0.8em;
            margin-top: 5px;
            color: #4a5568;
            font-weight: 500;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            overflow: hidden;
        }
        
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        
        th {
            background: #4299e1;
            color: white;
            font-weight: 600;
        }
        
        .battle-victory {
            background-color: rgba(72, 187, 120, 0.1);
        }
        
        .battle-defeat {
            background-color: rgba(245, 101, 101, 0.1);
        }
        
        .battle-draw {
            background-color: rgba(237, 137, 54, 0.1);
        }
        
        .result-victory {
            color: #38a169;
            font-weight: bold;
        }
        
        .result-defeat {
            color: #e53e3e;
            font-weight: bold;
        }
        
        .result-draw {
            color: #ed8936;
            font-weight: bold;
        }
        
        .current-player {
            background-color: rgba(66, 153, 225, 0.2);
            font-weight: bold;
        }
        
        .role-leader {
            color: #d69e2e;
            font-weight: bold;
        }
        
        .role-co-leader {
            color: #3182ce;
            font-weight: bold;
        }
        
        .role-elder {
            color: #38a169;
            font-weight: bold;
        }
        
        .role-member {
            color: #718096;
        }
        
        /* Mobile Battle Cards */
        .battle-cards {
            display: none;
        }
        
        .battle-card {
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #e2e8f0;
        }
        
        .battle-card.battle-victory {
            border-left-color: #38a169;
            background-color: rgba(72, 187, 120, 0.05);
        }
        
        .battle-card.battle-defeat {
            border-left-color: #e53e3e;
            background-color: rgba(245, 101, 101, 0.05);
        }
        
        .battle-card.battle-draw {
            border-left-color: #ed8936;
            background-color: rgba(237, 137, 54, 0.05);
        }
        
        .battle-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .battle-result {
            font-size: 1.1em;
            font-weight: bold;
            padding: 5px 10px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.8);
        }
        
        .battle-time {
            color: #718096;
            font-size: 0.9em;
        }
        
        .battle-card-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .battle-info {
            display: flex;
            flex-direction: column;
        }
        
        .battle-info span {
            color: #718096;
            font-size: 0.9em;
        }
        
        .battle-stats {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 5px;
        }
        
        .crown-count, .trophy-change {
            padding: 3px 8px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.8);
            font-size: 0.9em;
        }
        
        /* Mobile Clan Member Cards */
        .clan-member-cards {
            display: none;
        }
        
        .clan-member-card {
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #e2e8f0;
        }
        
        .current-player-card {
            border-left-color: #4299e1;
            background: rgba(66, 153, 225, 0.1);
        }
        
        .member-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .member-name {
            font-size: 1.1em;
            color: #2d3748;
        }
        
        .member-role {
            padding: 3px 8px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.8);
            font-size: 0.9em;
            font-weight: bold;
        }
        
        .member-card-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .member-stats {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .trophy-count, .donation-stats {
            padding: 3px 8px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.8);
            font-size: 0.9em;
        }
        
        .member-activity {
            text-align: right;
        }
        
        .last-seen {
            color: #718096;
            font-size: 0.9em;
            padding: 3px 8px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.8);
        }
        
        .footer {
            text-align: center;
            color: rgba(255, 255, 255, 0.8);
            margin-top: 30px;
            font-size: 0.9em;
        }
        
        /* Custom Stacked Histogram Styles */
        .chart-container {
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        
        .stacked-histogram {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            height: 200px;
            padding: 20px 10px 30px 10px;
            position: relative;
        }
        
        .histogram-bar {
            flex: 1;
            max-width: 25px;
            margin: 0 2px;
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            cursor: pointer;
        }
        
        .bar-date {
            position: absolute;
            bottom: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 0.8em;
            color: #4a5568;
            font-weight: 500;
        }
        
        .bar-stack {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
        }
        
        .bar-segment {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 2px;
            position: relative;
            font-size: 0.75em;
            font-weight: bold;
            color: white;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
        }
        
        .segment-value {
            opacity: 0.9;
        }
        
        .bar-wins {
            background: linear-gradient(180deg, #48bb78, #38a169);
            border-radius: 2px 2px 0 0;
        }
        
        .bar-losses {
            background: linear-gradient(180deg, #f56565, #e53e3e);
        }
        
        .bar-draws {
            background: linear-gradient(180deg, #a0aec0, #718096);
        }
        
        .bar-empty {
            background: linear-gradient(180deg, #cbd5e0, #a0aec0);
            border: 1px dashed #718096;
            border-radius: 2px;
        }
        
        .histogram-legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9em;
            color: #4a5568;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }
        
        .legend-wins {
            background: linear-gradient(180deg, #48bb78, #38a169);
        }
        
        .legend-losses {
            background: linear-gradient(180deg, #f56565, #e53e3e);
        }
        
        .legend-draws {
            background: linear-gradient(180deg, #ed8936, #dd6b20);
        }
        
        .legend-empty {
            background: linear-gradient(180deg, #cbd5e0, #a0aec0);
            border: 1px dashed #718096;
        }
        
        /* Clan Rankings Styles */
        .clan-rankings {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .ranking-item {
            display: flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease;
        }
        
        .ranking-item:hover {
            transform: translateY(-2px);
        }
        
        .current-player-ranking {
            background: rgba(66, 153, 225, 0.15);
            border-left: 4px solid #4299e1;
            font-weight: bold;
        }
        
        .ranking-position {
            font-size: 1.5em;
            font-weight: bold;
            color: #4299e1;
            min-width: 50px;
            text-align: center;
        }
        
        .ranking-info {
            flex: 1;
            margin-left: 20px;
        }
        
        .ranking-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .ranking-stats {
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .stat-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .trophy-up {
            color: #38a169;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .trophy-down {
            color: #e53e3e;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .trophy-neutral {
            color: #718096;
            font-size: 0.9em;
        }
        
        .donation-up {
            color: #3182ce;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .donation-down {
            color: #e53e3e;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .donation-neutral {
            color: #718096;
            font-size: 0.9em;
        }
        
        .last-seen-info {
            color: #718096;
            font-size: 0.9em;
        }
        
        /* Clan Deck Analytics Styles */
        .analytics-section {
            margin-bottom: 30px;
        }
        
        .analytics-section h3 {
            color: #2d3748;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        
        .popular-deck-item {
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .deck-popularity {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .deck-rank {
            font-size: 1.5em;
            font-weight: bold;
            color: #4299e1;
            min-width: 40px;
        }
        
        .deck-info {
            margin-left: 15px;
        }
        
        .usage-count {
            font-weight: bold;
            color: #2d3748;
        }
        
        .users-list {
            color: #718096;
            font-size: 0.9em;
            display: block;
        }
        
        .favorite-cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
        }
        
        .favorite-card-item {
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 10px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .favorite-card-image {
            width: 50px;
            height: 60px;
            object-fit: contain;
            margin-bottom: 8px;
        }
        
        .favorite-card-info .card-name {
            display: block;
            font-weight: 500;
            color: #2d3748;
            font-size: 0.9em;
        }
        
        .favorite-card-info .usage-count {
            color: #4299e1;
            font-size: 0.8em;
        }
        
        .experimenters-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .experimenter-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            padding: 10px 15px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
        }
        
        .experimenter-item .member-name {
            font-weight: 500;
            color: #2d3748;
        }
        
        .experimenter-item .change-count {
            color: #4299e1;
            font-size: 0.9em;
            font-weight: bold;
        }
        
        /* Card Level Analytics Styles */
        .level-comparison {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .level-stat {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .level-label {
            font-weight: 500;
            color: #2d3748;
        }
        
        .level-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #4299e1;
        }
        
        .level-win-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .win-stat {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.8);
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
        }
        
        .win-label {
            font-size: 0.9em;
            color: #4a5568;
        }
        
        .win-count {
            font-weight: bold;
            color: #38a169;
        }
        
        .opponent-clans-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .opponent-clan-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .clan-name {
            font-weight: 500;
            color: #2d3748;
            font-size: 1.1em;
        }
        
        .clan-stats {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 4px;
        }
        
        .battles-count {
            font-size: 0.9em;
            color: #718096;
        }
        
        .win-rate {
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .clan-analytics-link {
            color: #4299e1;
            text-decoration: none;
            font-weight: bold;
            font-size: 1.1em;
            padding: 12px 24px;
            border: 2px solid #4299e1;
            border-radius: 8px;
            display: inline-block;
            transition: all 0.3s ease;
            background: rgba(255, 255, 255, 0.9);
        }
        
        .clan-analytics-link:hover {
            background: #4299e1;
            color: white;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(66, 153, 225, 0.3);
        }
        
        @media (max-width: 768px) {
            .deck-cards {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .deck-cards-compact {
                gap: 6px;
            }
            
            .deck-cards-compact .card-container {
                padding: 3px;
                min-width: 40px;
            }
            
            .deck-cards-compact .card-image {
                width: 40px;
                height: 48px;
            }
            
            .player-stats {
                grid-template-columns: 1fr;
            }
            
            .deck-stats {
                flex-direction: column;
            }
            
            /* Hide tables on mobile, show cards */
            .desktop-table {
                display: none;
            }
            
            .battle-cards {
                display: block;
            }
            
            .clan-member-cards {
                display: block;
            }
            
            .container {
                padding: 10px;
            }
            
            .section {
                padding: 20px;
            }
            
            .header {
                padding: 20px;
            }
            
            .chart-container {
                padding: 15px;
            }
            
            .stacked-histogram {
                height: 150px;
                padding: 15px 5px 25px 5px;
            }
            
            .histogram-bar {
                max-width: 15px;
                margin: 0 1px;
            }
            
            .bar-date {
                font-size: 0.7em;
                bottom: -20px;
            }
            
            .bar-segment {
                font-size: 0.65em;
            }
            
            .histogram-legend {
                gap: 15px;
            }
            
            .ranking-stats {
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }
            
            .ranking-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 5px;
            }
            
            .level-comparison, .level-win-stats {
                grid-template-columns: 1fr;
            }
        }
        
        @media (min-width: 769px) {
            .desktop-table {
                display: block;
            }
            
            .battle-cards {
                display: none;
            }
            
            .clan-member-cards {
                display: none;
            }
        }
        
        /* Sortable table styles */
        .sortable {
            cursor: pointer;
            user-select: none;
            position: relative;
            transition: background-color 0.2s ease;
        }
        
        .sortable:hover {
            background-color: #3182ce !important;
        }
        
        .sort-indicator {
            font-size: 0.8em;
            margin-left: 5px;
            opacity: 0.6;
        }
        
        .sortable.sort-asc .sort-indicator:after {
            content: " ↑";
            color: #38a169;
            font-weight: bold;
        }
        
        .sortable.sort-desc .sort-indicator:after {
            content: " ↓";
            color: #e53e3e;
            font-weight: bold;
        }
        
        /* Responsive histogram styles */
        .histogram-desktop {
            display: block;
        }
        
        .histogram-mobile {
            display: none;
        }
        
        @media (max-width: 768px) {
            .histogram-desktop {
                display: none;
            }
            
            .histogram-mobile {
                display: block;
            }
            
            .histogram-mobile .stacked-histogram {
                height: 180px;
                padding: 20px 5px 30px 5px;
            }
            
            .histogram-mobile .histogram-bar {
                max-width: 20px;
                margin: 0 2px;
            }
        }
        """
    
    def generate_full_html(self, stats, win_rate, deck_performance_html, 
                          daily_histogram_html, clan_member_activity_html="",
                          battles_table_html="", battles_cards_html="") -> str:
        """Generate the complete HTML document"""
        
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

        <div class="section">
            <h2>⚔️ Últimas Batalhas</h2>
            <div class="desktop-table">
                <table>
                    <thead><tr><th>Horário</th><th>Resultado</th><th>Oponente</th><th>Coroas</th><th>Trofeus Δ</th><th>Arena</th></tr></thead>
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
