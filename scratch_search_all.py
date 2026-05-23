import os

terms = ['batalhas recentes', 'battle summary', 'taxa de vitória', 'avg. elixir leaked', 'worst enemy']
for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                for i, line in enumerate(lines):
                    for term in terms:
                        if term in line.lower():
                            print(f"{file} Line {i+1}: {line.strip()[:100]}")
            except Exception as e:
                pass
