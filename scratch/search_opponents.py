import pandas as pd
import glob
import os

names_to_find = [
    "Boruto Uzumaki", "VINI", "Luiz03br", "MIGUEL CR", "alpha", "Kuppy", 
    "BELL CRANEL", "LOTSO", "MOKRANE", "Monkey D rip", "とぅもひと", 
    "Chagus21", "optimus270308", "Gyubin", "EDWIN", "cplemons", "ING", 
    "WANTED", "Duduzin"
]

files = glob.glob('src/data_csv_oficial/oponentes_ano_*.csv')
results = []

for file in files:
    try:
        df = pd.read_csv(file, encoding='utf-8')
    except:
        df = pd.read_csv(file, encoding='latin-1')
    
    for name in names_to_find:
        mask = df['nome_oponente'].str.contains(name, case=False, na=False)
        matches = df[mask]
        for _, row in matches.iterrows():
            results.append({
                'file': file,
                'name': row['nome_oponente'],
                'date': row['data'],
                'result': row['resultado']
            })

res_df = pd.DataFrame(results)
if not res_df.empty:
    res_df.to_csv('scratch/found_opponents.csv', index=False, encoding='utf-8')
    print(f"Found {len(res_df)} occurrences. See scratch/found_opponents.csv")
else:
    print("No occurrences found.")
