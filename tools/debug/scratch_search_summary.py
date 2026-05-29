terms = ['streak', 'worst', 'win_rate', 'crowns', 'elixir_vazado', 'recent_battles', 'summary']
with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    line_lower = line.lower()
    for term in terms:
        if term in line_lower:
            safe_line = line.strip()[:120].encode('ascii', errors='replace').decode('ascii')
            print(f"Line {i+1}: {safe_line}")
            break
