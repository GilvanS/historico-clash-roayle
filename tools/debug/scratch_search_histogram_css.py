with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'stacked-histogram' in line or 'bar-segment' in line or 'segment-value' in line:
        safe_line = line.strip()[:120].encode('ascii', errors='replace').decode('ascii')
        print(f"Line {i+1}: {safe_line}")
