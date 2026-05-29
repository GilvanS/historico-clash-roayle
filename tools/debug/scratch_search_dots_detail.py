terms = ['dot', 'grid', 'circle', 'box', 'square', 'badge', 'summary', 'recent']
with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    line_lower = line.lower()
    for term in terms:
        if term in line_lower:
            if 'w10' in line_lower or 'l14' in line_lower or 'batalha' in line_lower or 'recent' in line_lower:
                safe_line = line.strip()[:120].encode('ascii', errors='replace').decode('ascii')
                print(f"Line {i+1}: {safe_line}")
                break
