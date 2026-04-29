import glob, csv
print('Checking for draws in csvs...')
files = glob.glob('src/data_csv_oficial/oponentes_*.csv')
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        if reader.fieldnames and len(reader.fieldnames) == 1 and ';' in reader.fieldnames[0]:
            file.seek(0)
            reader = csv.DictReader(file, delimiter=';')
        
        for i, row in enumerate(reader):
            res = str(row.get('resultado') or row.get('result') or '').strip().lower()
            norm_res = 'unknown'
            if any(x in res for x in ['vitoria', 'victory', 'vitória']):
                norm_res = 'victory'
            elif any(x in res for x in ['derrota', 'defeat']):
                norm_res = 'defeat'
            elif any(x in res for x in ['empate', 'draw']):
                norm_res = 'draw'
            else:
                norm_res = 'draw_fallback'
            
            if norm_res == 'draw_fallback':
                print(f"{f}:{i} - result: '{res}', tag: '{row.get('tag_oponente') or row.get('opponent_tag')}'")
