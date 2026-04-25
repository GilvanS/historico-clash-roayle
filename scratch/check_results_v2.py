
import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.abspath('src'))
from csv_database_manager import CSVDatabaseManager

def check_results():
    db_path = "file:clash_mem?mode=memory&cache=shared"
    # This will load the CSVs into the shared memory DB
    manager = CSVDatabaseManager()
    manager.load_all_csvs()
    
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT result FROM battles")
    results = cursor.fetchall()
    print(f"Distinct results in battles table: {results}")
    
    cursor.execute("SELECT COUNT(*) FROM battles")
    count = cursor.fetchone()[0]
    print(f"Total battles: {count}")
    
    cursor.execute("SELECT player_tag, COUNT(*) FROM battles GROUP BY player_tag")
    tags = cursor.fetchall()
    print(f"Distribution by player_tag: {tags}")
    
    conn.close()

if __name__ == "__main__":
    check_results()
