import sqlite3
from csv_database_manager import CSVDatabaseManager

def check_battles():
    m = CSVDatabaseManager()
    m.load_all_csvs()
    conn = sqlite3.connect('file:clash_mem?mode=memory&cache=shared', uri=True)
    cursor = conn.cursor()
    
    # Check battles for main tag
    cursor.execute("SELECT COUNT(*) FROM battles WHERE player_tag = '#2QR292P'")
    count_main = cursor.fetchone()[0]
    print(f"Total battles for #2QR292P: {count_main}")
    
    # Check battles for main tag before 2026
    cursor.execute("SELECT COUNT(*) FROM battles WHERE player_tag = '#2QR292P' AND battle_time < '2026-01-01'")
    count_old = cursor.fetchone()[0]
    print(f"Battles for #2QR292P before 2026: {count_old}")
    
    # Check other tags that might be the user
    cursor.execute("SELECT player_tag, COUNT(*) FROM battles GROUP BY player_tag HAVING COUNT(*) > 100")
    tags = cursor.fetchall()
    print("Tags with > 100 battles:")
    for tag, count in tags:
        print(f"  {tag}: {count}")
    
    conn.close()

if __name__ == '__main__':
    check_battles()
