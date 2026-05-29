import os

terms = ['batalhas recentes', 'battle summary', 'battle_summary', 'worst enemy', 'elixir leaked', 'daily activity']
for root, dirs, files in os.walk('.'):
    # Ignorar pastas de controle ou caches gigantes
    if any(p in root.lower() for p in ['.git', '.idea', '__pycache__', 'node_modules', '.gemini']):
        continue
    for file in files:
        if file.endswith(('.html', '.js', '.py', '.css')):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                for term in terms:
                    if term in content:
                        print(f"Found '{term}' in {path}")
            except Exception as e:
                pass
