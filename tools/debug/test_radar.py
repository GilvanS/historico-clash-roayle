import os
import sys
import json
# Add src to path
sys.path.insert(0, os.path.abspath('src'))
from html_generator import GitHubPagesHTMLGenerator

gen = GitHubPagesHTMLGenerator()
gen.load_all_data()
data = gen.get_war_radar_data('Tropa Do Bruxo', mode='my-war', player_tag='#2QR292P')
print("Keys in data:", data.keys())
clans_by_date = data.get('clans_by_date', {})
print("Dates found:", list(clans_by_date.keys()))
for d in list(clans_by_date.keys())[:1]:
    clans = clans_by_date[d]
    print(f"Date {d} has {len(clans)} clans:")
    for c in clans:
        print(f"  Clan: {c.get('name')}, Players: {len(c.get('players', []))}")
