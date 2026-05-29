# -*- coding: utf-8 -*-
with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

emojis = ['⚡', '🚣', '⚔️', '🛡️', '🎯', '🚣']
for i, line in enumerate(lines):
    for emo in emojis:
        if emo in line:
            safe_line = line.strip()[:100].encode('ascii', errors='replace').decode('ascii')
            print(f"Line {i+1} ({emo}): {safe_line}")
            break
