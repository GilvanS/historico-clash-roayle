import sys
import os
sys.path.append('src')
from html_generator import GitHubPagesHTMLGenerator

gen = GitHubPagesHTMLGenerator()
opps = gen.get_repeated_opponents_from_csv()
print(f"Total repetidos: {len(opps)}")
for o in opps[:3]:
    name_safe = o['nome'].encode('ascii', 'ignore').decode('ascii')
    print(f"Oponente: {name_safe} ({o['tag']}) - Total: {o['total']}")
