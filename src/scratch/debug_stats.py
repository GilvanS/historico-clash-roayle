
import sys
import os
sys.path.append('a:/Workspace/historico-clash-roayle/src')
from html_generator import GitHubPagesHTMLGenerator
from datetime import datetime

# Simular ambiente
os.environ['CR_PLAYER_TAG'] = '#2QR292P'

gen = GitHubPagesHTMLGenerator()
# O método get_daily_battle_stats agora carrega internamente as batalhas
stats = gen.get_daily_battle_stats(days_limit=30)

v = sum(d['wins'] for d in stats)
d = sum(d['losses'] for d in stats)
total_days = len(stats)

print(f"Stats nos ultimos 30 dias:")
print(f"Total dias: {total_days}")
print(f"Total Vitórias: {v}")
print(f"Total Derrotas: {d}")

if stats:
    print(f"Primeiro dia: {stats[0]['date']}")
    print(f"Último dia: {stats[-1]['date']}")
