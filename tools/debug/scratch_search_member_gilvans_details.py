terms = ['worst', 'enemy', 'elixir', 'summary', 'recent', 'battle', 'batalha', 'recentes', 'streak', 'crowns', 'win_rate']
with open('member_gilvans.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    line_lower = line.lower()
    for term in terms:
        if term in line_lower:
            # Imprime tudo, sem filtrar por prefixos do CSS
            safe_line = line.strip()[:120].encode('ascii', errors='replace').decode('ascii')
            print(f"Line {i+1}: {safe_line}")
            break
