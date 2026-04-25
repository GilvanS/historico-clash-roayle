
import sqlite3
import os
import sys

# Add src to path
sys.path.append('src')
from csv_database_manager import CSVDatabaseManager

# Initialize with default settings (it will use file:clash_mem?mode=memory&cache=shared)
db_manager = CSVDatabaseManager()
db_manager.load_all_csvs()

# Connect to the SAME shared memory DB
conn = sqlite3.connect("file:clash_mem?mode=memory&cache=shared", uri=True)
cursor = conn.cursor()

print("--- Player Statistics ---")
cursor.execute("SELECT player_tag, COUNT(*) FROM battles GROUP BY player_tag ORDER BY COUNT(*) DESC LIMIT 10")
for row in cursor.fetchall():
    print(f"Tag: {row[0]}, Battles: {row[1]}")

print("\n--- Results for #2QR292P ---")
# Count all occurrences including case variants
cursor.execute("SELECT result, COUNT(*) FROM battles WHERE player_tag = '#2QR292P' GROUP BY result")
for row in cursor.fetchall():
    print(f"Result: {row[0]}, Count: {row[1]}")

print("\n--- Total count for #2QR292P ---")
cursor.execute("SELECT COUNT(*) FROM battles WHERE player_tag = '#2QR292P'")
print(f"Total: {cursor.fetchone()[0]}")

conn.close()
