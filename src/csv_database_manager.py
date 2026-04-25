import sqlite3
import csv
import os
import logging
from typing import Optional

# Configuração de logging seguindo a regra de não usar acentos
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CSVDatabaseManager:
    """
    Manager to load Clash Royale CSV data into an in-memory SQLite database.
    This ensures the dashboard always has the most up-to-date data from CSV files.
    """
    def __init__(self, data_dir: Optional[str] = None):
        # Usando URI de memoria compartilhada para permitir multiplas conexoes ao mesmo banco em memoria
        self.db_path = "file:clash_mem?mode=memory&cache=shared"
        self.conn = sqlite3.connect(self.db_path, uri=True)
        self.cursor = self.conn.cursor()
        
        if data_dir is None:
            # Default path relative to this script
            self.data_dir = os.path.join(os.path.dirname(__file__), 'data_csv_oficial')
        else:
            self.data_dir = data_dir
            
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite schema in memory"""
        logger.info("Inicializando banco de dados em memoria")
        
        # Players table
        self.cursor.execute("""
            CREATE TABLE players (
                player_tag TEXT PRIMARY KEY,
                name TEXT,
                trophies INTEGER,
                best_trophies INTEGER,
                level INTEGER,
                clan_tag TEXT,
                clan_name TEXT,
                last_updated TEXT
            )
        """)
        
        # Battles table
        self.cursor.execute("""
            CREATE TABLE battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT,
                battle_time TEXT,
                battle_type TEXT,
                game_mode TEXT,
                is_ladder_tournament BOOLEAN,
                arena_id INTEGER,
                arena_name TEXT,
                result TEXT,
                crowns INTEGER,
                king_tower_hit_points INTEGER,
                princess_towers_hit_points TEXT,
                deck_cards TEXT,
                deck_card_levels TEXT,
                opponent_tag TEXT,
                opponent_name TEXT,
                opponent_trophies INTEGER,
                opponent_deck_cards TEXT,
                opponent_deck_card_levels TEXT,
                opponent_clan_tag TEXT,
                opponent_clan_name TEXT,
                player_level INTEGER,
                opponent_level INTEGER,
                battle_duration_seconds INTEGER,
                trophy_change INTEGER,
                UNIQUE(player_tag, battle_time, opponent_tag)
            )
        """)
        
        # Clan members table
        self.cursor.execute("""
            CREATE TABLE clan_members (
                player_tag TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                level INTEGER,
                trophies INTEGER,
                donations INTEGER,
                donations_received INTEGER,
                clan_tag TEXT,
                clan_name TEXT,
                last_seen TEXT,
                last_updated TEXT
            )
        """)
        
        # Clan member decks table
        self.cursor.execute("""
            CREATE TABLE clan_member_decks (
                id INTEGER PRIMARY KEY,
                player_tag TEXT,
                name TEXT,
                deck_cards TEXT,
                favorite_card TEXT,
                arena_id INTEGER,
                arena_name TEXT,
                league_id INTEGER,
                league_name TEXT,
                exp_level INTEGER,
                trophies INTEGER,
                best_trophies INTEGER,
                first_seen TEXT,
                last_seen TEXT,
                clan_tag TEXT,
                clan_name TEXT
            )
        """)
        
        self.conn.commit()

    def load_all_csvs(self):
        """Load all relevant CSVs from the data directory and parent directory"""
        import glob
        
        # 1. Main official files
        # Support for multiple battles files (e.g., battles_2024.csv, battles_2025.csv)
        official_patterns = {
            'players.csv': 'players',
            'battles*.csv': 'battles',
            'clan_members.csv': 'clan_members',
            'clan_member_decks.csv': 'clan_member_decks'
        }
        
        loaded_files = set()
        for pattern, table_name in official_patterns.items():
            for file_path in glob.glob(os.path.join(self.data_dir, pattern)):
                self._load_csv_to_table(file_path, table_name)
                loaded_files.add(os.path.basename(file_path))
        
        # 2. Secondary battle files (oponentes_*.csv) from parent directory and official dir
        parent_dir = os.path.dirname(self.data_dir)
        secondary_patterns = [
            os.path.join(parent_dir, 'oponentes_*.csv'),
            os.path.join(self.data_dir, 'oponentes_*.csv')
        ]
        
        # Mapping for oponentes_*.csv to battles table
        battle_mapping = {
            'data': 'battle_time',
            'battleTime': 'battle_time',
            'nome_oponente': 'opponent_name',
            'opponent_name': 'opponent_name',
            'tag_oponente': 'opponent_tag',
            'opponent_tag': 'opponent_tag',
            'nivel_oponente': 'opponent_level',
            'opponent_level': 'opponent_level',
            'trofes_oponente': 'opponent_trophies',
            'opponent_trophies': 'opponent_trophies',
            'clan_oponente': 'opponent_clan_name',
            'opponent_clan_name': 'opponent_clan_name',
            'resultado': 'result',
            'result': 'result',
            'coroas_jogador': 'crowns',
            'crowns': 'crowns',
            'mudanca_trofes': 'trophy_change',
            'trophy_change': 'trophy_change',
            'modo_jogo': 'game_mode',
            'game_mode': 'game_mode',
            'tipo_batalha': 'battle_type',
            'battle_type': 'battle_type',
            'arena': 'arena_name',
            'arena_name': 'arena_name',
            'deck_jogador': 'deck_cards',
            'deck_cards': 'deck_cards',
            'deck_oponente': 'opponent_deck_cards',
            'opponent_deck_cards': 'opponent_deck_cards'
        }
        
        for pattern in secondary_patterns:
            for file_path in glob.glob(pattern):
                # Skip the main ones if they are in the same pattern
                if os.path.basename(file_path) in loaded_files:
                    continue
                self._load_csv_to_table(file_path, 'battles', column_mapping=battle_mapping)

    def _load_csv_to_table(self, file_path: str, table_name: str, column_mapping: Optional[dict] = None):
        """Generic CSV loader to SQLite table with optional column mapping"""
        logger.info(f"Carregando {file_path} para tabela {table_name}")
        
        try:
            # Usar utf-8-sig para lidar com possiveis BOM no inicio do arquivo
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                # Get columns from table to filter CSV fields
                self.cursor.execute(f"PRAGMA table_info({table_name})")
                # Excluir 'id' da insercao automatica para deixar o SQLite gerenciar
                table_columns = [row[1] for row in self.cursor.fetchall() if row[1] != 'id']
                
                rows_to_insert = []
                for row in reader:
                    # Apply mapping if available
                    mapped_row = {}
                    if column_mapping:
                        for csv_col, val in row.items():
                            target_col = column_mapping.get(csv_col)
                            if target_col:
                                mapped_row[target_col] = val
                    else:
                        mapped_row = row
                        
                    # Filter row keys to match table columns
                    filtered_row = {k: v for k, v in mapped_row.items() if k in table_columns}
                    
                    # Special case: default player_tag if missing in battles
                    if table_name == 'battles' and 'player_tag' in table_columns and not filtered_row.get('player_tag'):
                        filtered_row['player_tag'] = '#2QR292P' # Tag default do usuario
                    
                    # Ensure all table columns have a value (None if missing in CSV)
                    values = [filtered_row.get(col) for col in table_columns]
                    rows_to_insert.append(values)
                
                if rows_to_insert:
                    placeholders = ', '.join(['?' for _ in table_columns])
                    insert_sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(table_columns)}) VALUES ({placeholders})"
                    self.cursor.executemany(insert_sql, rows_to_insert)
                    self.conn.commit()
                    logger.info(f"Inseridos {len(rows_to_insert)} registros em {table_name}")
                
        except Exception as e:
            logger.error(f"Erro ao carregar {file_path}: {str(e)}")


    def get_connection(self):
        return self.conn

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    # Test loading
    manager = CSVDatabaseManager()
    manager.load_all_csvs()
    
    # Simple check
    cursor = manager.get_connection().cursor()
    cursor.execute("SELECT COUNT(*) FROM battles")
    count = cursor.fetchone()[0]
    print(f"Total de batalhas carregadas: {count}")
    
    cursor.execute("SELECT player_tag, COUNT(*) FROM battles GROUP BY player_tag")
    tags = cursor.fetchall()
    print(f"Distribuicao por player_tag: {tags}")
    
    cursor.execute("SELECT MAX(battle_time) FROM battles")
    last_battle = cursor.fetchone()[0]
    print(f"Ultima batalha registrada: {last_battle}")
