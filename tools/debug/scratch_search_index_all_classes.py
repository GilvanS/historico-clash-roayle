with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    line_lower = line.lower()
    if 'summary' in line_lower or 'recent' in line_lower:
        if not line.strip().startswith(('<style', '/*', '.', 'margin', 'padding', 'display', 'border', 'background', 'color', 'font', 'box-shadow', 'border-radius', 'width', 'height', 'align', 'justify', 'gap', 'flex', 'transition', 'cursor', 'text', 'outline', 'position', 'left', 'top', 'right', 'bottom', 'transform', 'overflow')):
            safe_line = line.strip()[:120].encode('ascii', errors='replace').decode('ascii')
            print(f"Line {i+1}: {safe_line}")
