with open('member_gilvans.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'cr-opp-stats-summary' in line or 'recent' in line or 'summary' in line:
        if not line.strip().startswith(('/*', '.', 'margin', 'padding', 'display', 'border', 'background', 'color', 'font', 'box-shadow', 'border-radius', 'width', 'height', 'align', 'justify', 'gap', 'flex', 'transition', 'cursor', 'text', 'outline', 'position', 'left', 'top', 'right', 'bottom', 'transform', 'overflow')):
            safe_line = line.strip()[:120].encode('ascii', errors='replace').decode('ascii')
            print(f"Line {i+1}: {safe_line}")
