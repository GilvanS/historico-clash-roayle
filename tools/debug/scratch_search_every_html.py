import os

for root, dirs, files in os.walk('.'):
    # Ignorar caches e dotfiles
    if any(p in root.lower() for p in ['.git', '.idea', '__pycache__', 'node_modules', '.gemini']):
        continue
    for file in files:
        if file.endswith('.html'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                if 'worst' in content:
                    print(f"Found 'worst' in HTML: {path}")
            except Exception as e:
                pass
