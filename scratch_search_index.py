terms = ['worst', 'elixir', 'streak', 'recent', 'summary', 'lut', 'luta', 'recentes', 'batalha', 'avatar']
with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    for term in terms:
        if term in line.lower():
            print(f"Line {i+1}: {line.strip()[:100]}")
            break
