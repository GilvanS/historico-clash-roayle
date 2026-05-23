import re

with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

terms = ['daily activity', 'atividade', 'histogram', 'modal', 'battle summary', 'batalhas recentes', 'recent_battles']
for i, line in enumerate(lines):
    for term in terms:
        if term in line.lower():
            print(f"Line {i+1}: {line.strip()[:100]}")
            break
