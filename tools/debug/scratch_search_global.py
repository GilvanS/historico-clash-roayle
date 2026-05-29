with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'global' in line.lower() and ('modal' in line.lower() or 'tooltip' in line.lower() or 'skill' in line.lower() or 'popup' in line.lower() or 'show' in line.lower() or 'open' in line.lower() or 'click' in line.lower()):
        print(f"Line {i+1}: {line.strip()[:120]}")
