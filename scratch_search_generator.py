with open('src/member_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("--- member_generator.py ---")
for i, line in enumerate(lines):
    if any(term in line.lower() for term in ['battle', 'summary', 'recent', 'lut', 'luta', 'modal', 'vazio']):
        print(f"Line {i+1}: {line.strip()[:100]}")
