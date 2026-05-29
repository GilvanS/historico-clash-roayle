
import csv
import os

# Arquivos
main_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv"
recovery_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\recuperacao_hp_global.csv"
temp_file = main_file + ".tmp"

def merge_recovery():
    print("Iniciando mesclagem de dados recuperados...")
    
    # 1. Carrega dados de recuperacao
    recovery_data = {}
    with open(recovery_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            key = f"{row['data']}|{row['tag_oponente']}"
            recovery_data[key] = row
            
    # 2. Processa o arquivo principal
    updated_count = 0
    with open(main_file, 'r', encoding='utf-8-sig') as fin, \
         open(temp_file, 'w', encoding='utf-8-sig', newline='') as fout:
        
        reader = csv.DictReader(fin, delimiter=';')
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames, delimiter=';')
        writer.writeheader()
        
        for row in reader:
            key = f"{row['data']}|{row['tag_oponente']}"
            if key in recovery_data:
                rec_row = recovery_data[key]
                # Se o HP no principal esta vazio/zerado e o recuperado tem valor, atualiza
                if row.get('vida_torre_rei_jogador', '') in ["0", "", "0.0"] and \
                   rec_row.get('vida_torre_rei_jogador', '') not in ["0", "", "0.0"]:
                    
                    row['nivel_torre_jogador'] = rec_row.get('nivel_torre_jogador', row['nivel_torre_jogador'])
                    row['vida_torre_rei_jogador'] = rec_row['vida_torre_rei_jogador']
                    row['vida_torre_rei_oponente'] = rec_row['vida_torre_rei_oponente']
                    row['vida_torres_princesa_jogador'] = rec_row['vida_torres_princesa_jogador']
                    row['vida_torres_princesa_oponente'] = rec_row['vida_torres_princesa_oponente']
                    updated_count += 1
            writer.writerow(row)
            
    # 3. Substitui arquivo
    os.replace(temp_file, main_file)
    print(f"Sucesso! {updated_count} batalhas foram atualizadas com dados de HP recuperados.")

if __name__ == "__main__":
    merge_recovery()
