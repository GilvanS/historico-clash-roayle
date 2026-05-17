import os, sys, glob, csv
sys.path.insert(0, r'A:\Workspace\historico-clash-roayle\src')
from src.html_generator import GitHubPagesHTMLGenerator

gen = GitHubPagesHTMLGenerator()
print(f"src_dir: {gen.src_dir}")

# Testar glob
pattern = os.path.join(gen.src_dir, "data_clan", "status_barcos_*.csv")
files = sorted(glob.glob(pattern), reverse=True)
print(f"Files found via glob: {len(files)}")

# Testar leitura
if files:
    filepath = files[0]
    print(f"\nReading: {os.path.basename(filepath)}")
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            clan = row.get('Nome_Cla', '')
            if 'Tropa' in clan:
                print(f"  Found! Position: {row.get('Posicao')}, Fame: {row.get('Fama_Atual')}")
                break

# Testar get_war_calendar_data
print("\n\nTesting get_war_calendar_data('Tropa Do Bruxo'):")
calendar_data = gen.get_war_calendar_data('Tropa Do Bruxo', 5)
print(f"Days returned: {len(calendar_data)}")
for day in calendar_data:
    print(f"  {day}")