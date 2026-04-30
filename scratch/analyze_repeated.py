
import sys
import os
sys.path.append('a:\\Workspace\\historico-clash-roayle\\src')
from html_generator import GitHubPagesHTMLGenerator

gen = GitHubPagesHTMLGenerator()
battles = gen._load_all_battles_from_csv()
opponents = {}
for b in battles:
    tag = b.get('opponent_tag')
    if tag:
        if tag not in opponents:
            opponents[tag] = []
        opponents[tag].append(b)

repeated = {tag: bs for tag, bs in opponents.items() if len(bs) >= 2}
print(f"Total repeated opponents: {len(repeated)}")
for tag, bs in repeated.items():
    name = bs[0].get('opponent_name')
    print(f"Opponent: {name} ({tag}) - Count: {len(bs)}")
    for b in bs:
        print(f"  - {b['battle_time']}")
