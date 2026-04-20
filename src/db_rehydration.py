import sqlite3
import csv
import os
import argparse
from datetime import datetime

CSV_DIR = 'data_csv_oficial'

def ensure_tables_clash_royale(cursor):
    """Ensure all required tables exist before importing into clash_royale.db"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS battles (
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
            FOREIGN KEY (player_tag) REFERENCES players (player_tag),
            UNIQUE(player_tag, battle_time, battle_type, game_mode)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clan_members (
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clan_rankings_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_tag TEXT,
            name TEXT,
            clan_rank INTEGER,
            trophies INTEGER,
            donations INTEGER,
            donations_received INTEGER,
            trophy_change INTEGER,
            donation_change INTEGER,
            clan_tag TEXT,
            clan_name TEXT,
            recorded_at TEXT,
            FOREIGN KEY (player_tag) REFERENCES players (player_tag),
            UNIQUE(player_tag, recorded_at)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clan_member_decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            clan_name TEXT,
            FOREIGN KEY (player_tag) REFERENCES players (player_tag)
        )
    """)
    
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS deck_performance AS
        SELECT 
            deck_cards,
            COUNT(*) as total_battles,
            SUM(CASE WHEN result = 'victory' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'defeat' THEN 1 ELSE 0 END) as losses,
            ROUND(AVG(CASE WHEN result = 'victory' THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate,
            SUM(COALESCE(trophy_change, 0)) as total_trophy_change,
            ROUND(AVG(COALESCE(trophy_change, 0)), 2) as avg_trophy_change,
            ROUND(AVG(crowns), 2) as avg_crowns
        FROM battles 
        WHERE deck_cards IS NOT NULL
        GROUP BY deck_cards
        ORDER BY win_rate DESC, total_battles DESC
    """)

def ensure_tables_oponentes(cursor):
    """Ensure tables exist for oponentes.db"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oponentes_batalhas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_tag TEXT,
            battle_time TEXT,
            data_formatada TEXT,
            nome_oponente TEXT,
            tag_oponente TEXT,
            nivel_oponente INTEGER,
            trofes_oponente INTEGER,
            clan_oponente TEXT,
            resultado TEXT,
            coroas_jogador INTEGER,
            coroas_oponente INTEGER,
            mudanca_trofes INTEGER,
            modo_jogo TEXT,
            tipo_batalha TEXT,
            arena TEXT,
            deck_jogador TEXT,
            deck_oponente TEXT,
            UNIQUE(player_tag, battle_time, tag_oponente)
        )
    """)

DATABASES = {
    'clash_royale.db': {
        'tables': ['players', 'battles', 'clan_members', 'clan_rankings_history', 'clan_member_decks'],
        'ensure_func': ensure_tables_clash_royale
    },
    'oponentes.db': {
        'tables': ['oponentes_batalhas'],
        'ensure_func': ensure_tables_oponentes
    }
}

def export_db(db_name="all"):
    print(f"[{datetime.now().isoformat()}] Iniciando a exportacao de SQLite para CSVs...")
    if not os.path.exists(CSV_DIR):
        os.makedirs(CSV_DIR)
        
    for db_file, db_config in DATABASES.items():
        if db_name != "all" and db_name != db_file:
            continue
            
        if not os.path.exists(db_file):
            print(f"[{db_file}] Banco de dados nao encontrado.")
            continue
            
        print(f"[{db_file}] Exportando para CSV...")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        for table in db_config['tables']:
            cursor.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone()[0] == 0:
                print(f"  - Tabela {table} nao existe. Ignorando.")
                continue
                
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            col_names = [description[0] for description in cursor.description]
            csv_path = os.path.join(CSV_DIR, f"{table}.csv")
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(col_names)
                writer.writerows(rows)
                
            print(f"  + Obteve {len(rows)} registros para {table}.csv")
            
        conn.close()
    print(f"[{datetime.now().isoformat()}] Exportacao concluida com sucesso!")

def import_csv(db_name="all"):
    print(f"[{datetime.now().isoformat()}] Iniciando a importacao de CSVs para os Bancos SQLite...")
    if not os.path.exists(CSV_DIR):
        print(f"Erro: Diretorio {CSV_DIR} nao encontrado.")
        return
        
    for db_file, db_config in DATABASES.items():
        if db_name != "all" and db_name != db_file:
            continue
            
        print(f"[{db_file}] Reidratando tabelas...")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA journal_mode = MEMORY")
        
        db_config['ensure_func'](cursor)
        
        for table in db_config['tables']:
            csv_path = os.path.join(CSV_DIR, f"{table}.csv")
            if not os.path.exists(csv_path):
                print(f"  - Arquivo {csv_path} nao encontrado. Pulando tabela {table}.")
                continue
                
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    continue
                    
                cursor.execute(f"DELETE FROM {table}")
                placeholders = ','.join(['?'] * len(header))
                rows = list(reader)
                
                if rows:
                    cursor.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", rows)
                    
                print(f"  + Importou {len(rows)} registros para a tabela {table}")
                
        conn.commit()
        conn.close()
    print(f"[{datetime.now().isoformat()}] Importacao concluida com sucesso!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Exporta/Importa os banco de dados SQLite para arquivos CSV para evitar o historico do Git.")
    parser.add_argument('--export', action='store_true', help="Exporta tabelas do SQLite para CSV")
    parser.add_argument('--import-csv', action='store_true', help="Cria/Popula SQLite a partir dos CSVs")
    parser.add_argument('--db', type=str, default="all", help="Especifica qual DB processar (clash_royale.db, oponentes.db) ou all")
    
    args = parser.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    if args.export:
        export_db(args.db)
    elif args.import_csv:
        import_csv(args.db)
    else:
        print("Use --export ou --import-csv")
