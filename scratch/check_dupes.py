import pandas as pd
import glob
import os

files = glob.glob('src/data_csv_oficial/oponentes_ano_*.csv')
report = []

for file in files:
    try:
        # Tentar UTF-8 primeiro
        df = pd.read_csv(file, encoding='utf-8')
    except:
        # Fallback para Latin-1
        df = pd.read_csv(file, encoding='latin-1')
    
    counts = df['nome_oponente'].value_counts()
    dupes = counts[counts > 1]
    
    report.append(f"Arquivo: {file}")
    if dupes.empty:
        report.append("  Nenhuma duplicata de nome encontrada.")
    else:
        report.append("  Duplicatas encontradas:")
        for name, count in dupes.items():
            report.append(f"    - {name}: {count} vezes")
    report.append("-" * 30)

with open('scratch/duplicate_report.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(report))

print("Relatório gerado em scratch/duplicate_report.txt")
