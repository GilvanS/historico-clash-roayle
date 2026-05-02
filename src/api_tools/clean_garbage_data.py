import os
import csv
import glob

DATA_DIR = 'a:/Workspace/historico-clash-roayle/src/data_csv_oficial'

def clean_csvs():
    pattern = os.path.join(DATA_DIR, 'oponentes_*.csv')
    files = glob.glob(pattern)
    
    for file in files:
        print(f"Limpando {os.path.basename(file)}...")
        cleaned_rows = []
        original_count = 0
        
        try:
            # Tenta ler com delimitador ;
            with open(file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames
                for row in reader:
                    original_count += 1
                    # So mantem se tiver DATA e NOME_OPONENTE
                    if row.get('data') and row.get('nome_oponente'):
                        cleaned_rows.append(row)
            
            if len(cleaned_rows) < original_count:
                print(f"  Removidas {original_count - len(cleaned_rows)} linhas corrompidas.")
                with open(file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                    writer.writeheader()
                    writer.writerows(cleaned_rows)
            else:
                print("  Arquivo ja estava limpo.")
                
        except Exception as e:
            print(f"  Erro ao processar {file}: {e}")

if __name__ == "__main__":
    clean_csvs()
