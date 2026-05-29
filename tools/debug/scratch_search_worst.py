with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'worst' in line.lower():
        safe_line = line.strip()[:120].encode('ascii', errors='replace').decode('ascii')
        print(f"Line {i+1}: {safe_line}")
