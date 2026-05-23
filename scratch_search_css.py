terms = ['cr-opp-stats-summary', 'cr-battle-preview', 'battle-card', 'battle-cards', 'recent', 'summary']
with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    line_lower = line.lower()
    for term in terms:
        if term in line_lower:
            print(f"Line {i+1}: {line.strip()[:100]}")
            break
