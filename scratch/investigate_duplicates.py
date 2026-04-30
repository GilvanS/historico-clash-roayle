import csv, os
from datetime import datetime

def check_names(names):
    file_path = 'src/data_csv_oficial/oponentes_ano_2026.csv'
    if not os.path.exists(file_path):
        print("Arquivo nao encontrado")
        return

    with open(file_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for name in names:
        print(f"\n--- Analisando: {name} ---")
        found = [r for r in rows if name.lower() in r['nome_oponente'].lower()]
        for r in found:
            print(f"Data: {r['data']} | Res: {r['resultado']} | Coroas: {r['coroas_jogador']}x{r['coroas_oponente']} | Trofes: {r['mudanca_trofes']}")

if __name__ == "__main__":
    check_names(['daniel_wrld08', 'Boruto Uzumaki', 'VINI', 'Luiz03br', 'MIGUEL CR'])
