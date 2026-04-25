
import sqlite3
import os
import sys

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from csv_database_manager import CSVDatabaseManager
from html_generator import GitHubPagesHTMLGenerator

def debug_histogram():
    player_tag = "#2QR292P"
    db_path = "file:clash_mem?mode=memory&cache=shared"
    
    # 1. Load Data
    print("--- 1. Loading CSV Data ---")
    # GitHubPagesHTMLGenerator calls load_all_csvs internally
    gen = GitHubPagesHTMLGenerator(db_path)
    
    # 2. Check Database Raw Dates
    print("\n--- 2. Checking Raw Data in 'battles' table ---")
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    cursor.execute("SELECT battle_time, result FROM battles WHERE player_tag = ? LIMIT 5", (player_tag,))
    rows = cursor.fetchall()
    for row in rows:
        print(f"Time: {row[0]}, Result: {row[1]}")
    
    # 3. Test DATE() function
    print("\n--- 3. Testing SQL DATE() function ---")
    cursor.execute("SELECT DATE(battle_time), COUNT(*) FROM battles WHERE player_tag = ? GROUP BY DATE(battle_time) ORDER BY DATE(battle_time) DESC LIMIT 10", (player_tag,))
    for row in cursor.fetchall():
        print(f"Date: {row[0]}, Count: {row[1]}")
    
    # 4. Check Histogram Query
    print("\n--- 4. Running get_daily_battle_stats ---")
    stats = gen.get_daily_battle_stats(days_limit=30, player_tag=player_tag)
    
    print(f"Total days returned: {len(stats)}")
    active_days = [s for s in stats if s['total_battles'] > 0]
    print(f"Active days found: {len(active_days)}")
    
    for s in stats[-5:]: # Last 5 days
        print(f"Date: {s['date']}, Wins: {s['wins']}, Losses: {s['losses']}, Total: {s['total_battles']}")
    
    conn.close()

if __name__ == "__main__":
    debug_histogram()
