import sqlite3

db_path = "file:clash_mem?mode=memory&cache=shared"

try:
    from csv_database_manager import CSVDatabaseManager
    manager = CSVDatabaseManager()
    manager.load_all_csvs()
    
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    
    print("--- Date Formats for #2QR292P ---")
    cursor.execute("SELECT battle_time, COUNT(*) FROM battles WHERE player_tag = '#2QR292P' GROUP BY substr(battle_time, 1, 4)")
    for row in cursor.fetchall():
        print(f"Prefix: {row[0]}, Count: {row[1]}")
        
    print("\n--- Sample dates ---")
    cursor.execute("SELECT battle_time FROM battles WHERE player_tag = '#2QR292P' LIMIT 10")
    for row in cursor.fetchall():
        print(f"Date: {row[0]}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
