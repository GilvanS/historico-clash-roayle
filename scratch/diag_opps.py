
import os
import sys
import csv
from datetime import datetime

# Adiciona o path do src para importar o GitHubPagesHTMLGenerator
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from html_generator import GitHubPagesHTMLGenerator
    gen = GitHubPagesHTMLGenerator()
    opps = gen.get_repeated_opponents_from_csv()
    print(f"Total de oponentes repetidos encontrados: {len(opps)}")
    for o in opps[:3]:
        print(f"Nome: {o['nome']}, Tag: {o['tag']}, Total: {o['total']}")
except Exception as e:
    print(f"Erro no teste: {e}")
