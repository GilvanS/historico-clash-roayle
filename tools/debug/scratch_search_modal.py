with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'modal' in line.lower():
        print(f"Line {i+1}: {line.strip()[:100]}")
