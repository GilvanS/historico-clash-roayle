
import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.abspath('src'))
from csv_database_manager import CSVDatabaseManager

def check_results():
    db_path = "file:clash_mem?mode=memory&cache=shared"
    manager = CSVDatabaseManager()
    manager.load_all_csvs()
    
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    
    cursor.execute("SELECT MAX(battle_time) FROM battles")
    max_date = cursor.fetchone()[0]
    print(f"Max battle date: {max_date}")
    
    cursor.execute("SELECT MIN(battle_time) FROM battles")
    min_date = cursor.fetchone()[0]
    print(f"Min battle date: {min_date}")
    
    cursor.execute("SELECT DATE('now')")
    now_date = cursor.fetchone()[0]
    print(f"SQLite 'now' date: {now_date}")
    
    conn.close()

if __name__ == "__main__":
    check_results()
