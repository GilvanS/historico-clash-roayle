import csv, os, glob

def check_all_csvs(names):
    data_dir = 'src/data_csv_oficial'
    files = glob.glob(os.path.join(data_dir, 'oponentes_*.csv'))
    
    for name in names:
        print(f"\n--- Analisando: {name} ---")
        for file_path in files:
            with open(file_path, encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                found = [r for r in reader if name.lower() in r['nome_oponente'].lower()]
                if found:
                    print(f"Arquivo: {os.path.basename(file_path)}")
                    for r in found:
                        print(f"  Data: {r['data']} | Res: {r['resultado']} | Coroas: {r['coroas_jogador']}x{r['coroas_oponente']} | Trofes: {r.get('mudanca_trofes', 'N/A')}")

if __name__ == "__main__":
    check_all_csvs(['daniel_wrld08', 'Boruto Uzumaki', 'VINI', 'Luiz03br', 'MIGUEL CR'])
