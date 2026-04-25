
import sqlite3
import sys

# Add src to path
sys.path.append('src')
from csv_database_manager import CSVDatabaseManager

db_manager = CSVDatabaseManager()
db_manager.load_all_csvs()

conn = sqlite3.connect("file:clash_mem?mode=memory&cache=shared", uri=True)
cursor = conn.cursor()

p_tag = '#2QR292P'

print(f"--- Top Repeated Opponents for {p_tag} ---")
cursor.execute("""
    SELECT 
        opponent_tag, 
        opponent_name, 
        COUNT(*) as encounters,
        SUM(CASE WHEN LOWER(result) IN ('victory', 'vitoria', 'vitória') THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN LOWER(result) IN ('defeat', 'derrota') THEN 1 ELSE 0 END) as losses
    FROM battles
    WHERE player_tag = ? AND opponent_tag IS NOT NULL AND opponent_tag != ''
    GROUP BY opponent_tag, opponent_name
    HAVING encounters > 1
    ORDER BY encounters DESC, wins DESC
    LIMIT 20
""", (p_tag,))

for row in cursor.fetchall():
    print(f"Name: {row[1]} ({row[0]}), Encounters: {row[2]}, Wins: {row[3]}, Losses: {row[4]}")

conn.close()
