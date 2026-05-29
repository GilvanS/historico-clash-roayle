import os

terms = ['batalhas recentes', 'battle summary', 'daily activity', 'elixir leaked', 'worst enemy']
for file in os.listdir('.'):
    if file.endswith('.html'):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read().lower()
            for term in terms:
                if term in content:
                    print(f"Found '{term}' in {file}")
        except Exception as e:
            pass
