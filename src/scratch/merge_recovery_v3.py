
import csv
import os

main_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv"
recovery_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\recuperacao_hp_global.csv"
output_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026_CORRIGIDO.csv"

def merge_recovery():
    print("Iniciando mesclagem de dados recuperados em novo arquivo...")
    
    recovery_data = {}
    with open(recovery_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            key = f"{row['data']}|{row['tag_oponente']}"
            recovery_data[key] = row
            
    updated_count = 0
    all_rows = []
    headers = []
    
    # Tenta ler o arquivo original
    try:
        with open(main_file, 'r', encoding='utf-8-sig') as fin:
            reader = csv.DictReader(fin, delimiter=';')
            headers = reader.fieldnames
            for row in reader:
                key = f"{row['data']}|{row['tag_oponente']}"
                if key in recovery_data:
                    rec_row = recovery_data[key]
                    # Só atualiza se o original estiver zerado/vazio e o recuperado tiver dado
                    if row.get('vida_torre_rei_jogador', '') in ["0", "", "0.0"] and \
                       rec_row.get('vida_torre_rei_jogador', '') not in ["0", "", "0.0"]:
                        row['nivel_torre_jogador'] = rec_row.get('nivel_torre_jogador', row['nivel_torre_jogador'])
                        row['vida_torre_rei_jogador'] = rec_row['vida_torre_rei_jogador']
                        row['vida_torre_rei_oponente'] = rec_row['vida_torre_rei_oponente']
                        row['vida_torres_princesa_jogador'] = rec_row['vida_torres_princesa_jogador']
                        row['vida_torres_princesa_oponente'] = rec_row['vida_torres_princesa_oponente']
                        updated_count += 1
                all_rows.append(row)
    except Exception as e:
        print(f"Erro ao ler arquivo original: {e}")
        return

    # Escreve no NOVO arquivo para evitar bloqueio de permissao
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as fout:
        writer = csv.DictWriter(fout, fieldnames=headers, delimiter=';')
        writer.writeheader()
        writer.writerows(all_rows)
        
    print(f"Sucesso! Gerado arquivo: {output_file}")
    print(f"{updated_count} batalhas foram atualizadas com dados de HP recuperados.")

if __name__ == "__main__":
    merge_recovery()
