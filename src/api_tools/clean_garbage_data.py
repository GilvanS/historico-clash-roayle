import os
import csv
import glob

DATA_DIR = 'src/data_csv_oficial'

def clean_file(file_path):
    if not os.path.exists(file_path):
        return
    
    print(f"Limpando {file_path}...")
    
    rows = []
    header = None
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            header = next(reader)
            for row in reader:
                # Se a primeira coluna (data) for '0' ou a linha estiver cheia de zeros, ignora
                if not row or row[0] == '0' or all(cell == '0' for cell in row[:10]):
                    continue
                rows.append(row)
        
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(header)
            writer.writerows(rows)
            
        print(f"  {len(rows)} linhas validas preservadas.")
    except Exception as e:
        print(f"  Erro ao processar {file_path}: {e}")

def main():
    # Limpa arquivos diarios, mensais e anuais
    patterns = [
        os.path.join(DATA_DIR, "oponentes_dia_*.csv"),
        os.path.join(DATA_DIR, "oponentes_mes_*.csv"),
        os.path.join(DATA_DIR, "oponentes_ano_*.csv")
    ]
    
    for pattern in patterns:
        for file_path in glob.glob(pattern):
            clean_file(file_path)

if __name__ == "__main__":
    main()
