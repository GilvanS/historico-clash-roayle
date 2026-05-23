import os

terms = ['worst', 'enemy', 'elixir leaked', 'battle summary', 'batalhas recentes', 'w10', 'l14']
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
