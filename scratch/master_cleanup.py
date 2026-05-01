import pandas as pd
import glob
import os
import csv

def clean_and_redistribute():
    # 1. Carregar todos os dados de todos os CSVs oficiais (Anual, Mensal, Diário)
    all_files = glob.glob('src/data_csv_oficial/oponentes_*.csv')
    all_files.append('src/data_csv_oficial/dados_manuais_preservados.csv')
    
    # Lista de arquivos para ignorar (redundantes ou globais que causariam loop)
    ignored_patterns = ['oponentes_todos.csv', 'oponentes_batalhas.csv']
    all_files = [f for f in all_files if os.path.basename(f) not in ignored_patterns]
    
    dfs = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            df.columns = [c.lower() for c in df.columns]
            dfs.append(df)
            print(f"Lido: {f} ({len(df)} registros)")
        except Exception as e:
            print(f"Erro ao ler {f}: {e}")
            
    if not dfs:
        return
        
    df_all = pd.concat(dfs, ignore_index=True)
    
    # 2. Converter data para datetime
    df_all['data_dt'] = pd.to_datetime(df_all['data'], errors='coerce', dayfirst=True)
    df_all = df_all.dropna(subset=['data_dt'])
    df_all['data'] = df_all['data_dt'].dt.strftime('%d/%m/%Y %H:%M')
    df_all = df_all.sort_values(by='data_dt')
    
    # 3. Deduplicação Global (Janela de 2 min)
    print("Deduplicando (janela 2 min)...")
    df_all = df_all.drop_duplicates(subset=['data', 'tag_oponente'], keep='first')
    
    # 4. Deduplicação de Timezone (Janela de 180 min +/- 5 min)
    print("Deduplicando Timezone (shift 3h)...")
    df_clean = df_all.sort_values(by='data_dt')
    clean_list = df_clean.to_dict('records')
    processed_indices = set()
    final_records = []
    
    for i, row in enumerate(clean_list):
        if i in processed_indices:
            continue
            
        # Procurar à frente por uma luta do mesmo oponente em aproximadamente 3h
        # 10800 segundos = 3h. Margem ampliada para 10 minutos (600s)
        found_dupe = False
        for j in range(i + 1, len(clean_list)):
            next_row = clean_list[j]
            time_diff = (next_row['data_dt'] - row['data_dt']).total_seconds()
            
            # Se passou de 3h10, não precisa mais procurar para este registro
            if time_diff > 11400:
                break
                
            if next_row['tag_oponente'] == row['tag_oponente'] and next_row['resultado'].lower() == row['resultado'].lower():
                if abs(time_diff - 10800) < 600: # Entre 2h50 e 3h10
                    print(f"Removendo duplicata TZ: {row['data']} vs {next_row['data']} ({row['tag_oponente']})")
                    processed_indices.add(j)
                    # Não paramos o loop 'j' aqui para remover TODAS as duplicatas possíveis, 
                    # mas geralmente é só uma.
        
        final_records.append(row)
        
    df_final = pd.DataFrame(final_records)
    
    # 5. Redistribuir por ano
    print("\nRedistribuindo arquivos...")
    df_final['ano_aux'] = df_final['data_dt'].dt.year
    
    for ano, group in df_final.groupby('ano_aux'):
        target_file = f'src/data_csv_oficial/oponentes_ano_{ano}.csv'
        group_to_save = group.drop(columns=['data_dt', 'ano_aux'])
        
        # Sanitização final
        for col in group_to_save.columns:
            if col in ['vezes_enfrentado', 'nivel_oponente', 'trofes_oponente', 'coroas_jogador', 'coroas_oponente', 'mudanca_trofes']:
                group_to_save[col] = pd.to_numeric(group_to_save[col], errors='coerce').fillna(0).astype(int)
        
        group_to_save.to_csv(target_file, index=False)
        print(f"Salvo: {target_file} ({len(group_to_save)} registros)")

    print("\nProcesso concluído!")

if __name__ == "__main__":
    clean_and_redistribute()
