# -*- coding: utf-8 -*-
import json

with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

results = []
emojis = ['⚡', '🚣', '⚔️', '🛡️', '🎯', '🏆']
for i, line in enumerate(lines):
    for emo in emojis:
        if emo in line:
            results.append({
                "line": i+1,
                "emoji": emo,
                "content": line.strip()[:150]
            })
            break

with open('scratch_icons_out.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"Results saved: {len(results)} matches")
