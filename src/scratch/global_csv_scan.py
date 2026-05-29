
import csv
import os

dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
root_dir = r"a:\Workspace\historico-clash-roayle"
output_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\recuperacao_hp_global.csv"

all_found = {} # Key: DATA|TAG, Value: Row

def scan_all_csvs():
    for root, dirs, files in os.walk(root_dir):
        # Pula pastas de backup que eu mesmo criei agora para nao duplicar
        if "backup_oficial_recuperacao" in root or "backup_seguranca_antigravity" in root:
            continue
            
        for file in files:
            if file.endswith(".csv"):
                file_path = os.path.join(root, file)
                # Tenta encodings
                for enc in ['utf-8-sig', 'utf-16', 'latin-1']:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            first_line = f.readline()
                            delimiter = ';' if ';' in first_line else ','
                            f.seek(0)
                            reader = csv.DictReader(f, delimiter=delimiter)
                            
                            # Verifica se tem as colunas minimas
                            if not all(col in reader.fieldnames for col in ['data', 'tag_oponente', 'vida_torre_rei_jogador']):
                                break
                                
                            for row in reader:
                                b_date = row.get('data', '')
                                b_tag = row.get('tag_oponente', '')
                                if any(d in b_date for d in dates):
                                    key = f"{b_date}|{b_tag}"
                                    # Se ja temos, so substitui se a nova tiver HP e a antiga nao
                                    has_hp = row.get('vida_torre_rei_jogador', '') not in ["0", "", "0.0"]
                                    
                                    if key not in all_found or (not all_found[key].get('has_hp') and has_hp):
                                        row['has_hp'] = has_hp
                                        all_found[key] = row
                            break # Se conseguiu ler o arquivo, pula pro proximo arquivo
                    except:
                        continue

    if all_found:
        # Pega headers do primeiro
        sample_row = next(iter(all_found.values()))
        headers = [h for h in sample_row.keys() if h != 'has_hp']
        
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            # Ordena por data
            sorted_rows = sorted(all_found.values(), key=lambda x: x.get('data', ''))
            writer.writerows(sorted_rows)
        print(f"Sucesso! {len(all_found)} batalhas unicas encontradas em todos os CSVs.")
        print(f"Arquivo gerado: {output_file}")
    else:
        print("Nada encontrado.")

if __name__ == "__main__":
    scan_all_csvs()
