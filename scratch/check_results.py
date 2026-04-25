
import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.abspath('src'))
from csv_database_manager import CSVDatabaseManager

def check_results():
    db_path = "file:clash_mem?mode=memory&cache=shared"
    # This will load the CSVs into the shared memory DB
    manager = CSVDatabaseManager(db_path)
    
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT result FROM battles")
    results = cursor.fetchall()
    print(f"Distinct results in battles table: {results}")
    
    cursor.execute("SELECT COUNT(*) FROM battles")
    count = cursor.fetchone()[0]
    print(f"Total battles: {count}")
    
    conn.close()

if __name__ == "__main__":
    check_results()
