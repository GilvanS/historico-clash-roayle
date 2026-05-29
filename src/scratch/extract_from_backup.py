
import csv
import os

# Configuracoes
dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
source_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\backups\oponentes_ano_2026_restaurado.csv"
output_file = r"a:\Workspace\historico-clash-roayle\src\data_csv_oficial\recuperacao_hp_oficial.csv"

# Encodings para tentar (o restaurado parece ser UTF-16 ou UTF-8 com BOM)
encodings = ['utf-16', 'utf-8-sig', 'latin-1']

def extract_data():
    found_battles = []
    headers = []
    
    for enc in encodings:
        try:
            print(f"Tentando encoding: {enc}")
            with open(source_file, 'r', encoding=enc) as f:
                # Detecta delimitador (pode ser ; ou ,)
                first_line = f.readline()
                delimiter = ';' if ';' in first_line else ','
                f.seek(0)
                
                reader = csv.DictReader(f, delimiter=delimiter)
                headers = reader.fieldnames
                
                for row in reader:
                    battle_date = row.get('data', '')
                    if any(d in battle_date for d in dates):
                        # Verifica se tem dados de HP (nao pode ser tudo vazio ou 0 para vitorias)
                        hp_rei = row.get('vida_torre_rei_jogador', '')
                        if hp_rei and hp_rei != '0' or row.get('resultado') == 'Derrota':
                            found_battles.append(row)
                
                if found_battles:
                    print(f"Sucesso! Encontradas {len(found_battles)} batalhas com dados em {enc}")
                    break
        except Exception as e:
            print(f"Erro com {enc}: {e}")
            continue

    if found_battles:
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=';')
            writer.writeheader()
            writer.writerows(found_battles)
        print(f"Arquivo de recuperacao gerado: {output_file}")
    else:
        print("Nenhuma batalha encontrada nas datas alvo com dados validos.")

if __name__ == "__main__":
    extract_data()
