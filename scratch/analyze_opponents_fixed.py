import sqlite3
import os
import sys

# Forcar UTF-8 para o print
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db_path = "file:clash_mem?mode=memory&cache=shared"

try:
    from csv_database_manager import CSVDatabaseManager
    manager = CSVDatabaseManager()
    manager.load_all_csvs()
    
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    
    # 1. Total battles for the user
    cursor.execute("SELECT COUNT(*) FROM battles WHERE player_tag = '#2QR292P'")
    total = cursor.fetchone()[0]
    print(f"Total de batalhas para #2QR292P: {total}")
    
    # 2. Repeated opponents (strict filter)
    # We want oponents where the tag starts with '#'
    cursor.execute("""
        SELECT opponent_name, opponent_tag, COUNT(*) as count 
        FROM battles 
        WHERE player_tag = '#2QR292P' 
          AND opponent_tag LIKE '#%'
        GROUP BY opponent_tag
        HAVING count > 1
        ORDER BY count DESC
    """)
    
    rows = cursor.fetchall()
    print(f"Total de oponentes repetidos (limpos): {len(rows)}")
    for name, tag, count in rows[:20]:
        print(f"Opponent: {name} ({tag}), Count: {count}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
