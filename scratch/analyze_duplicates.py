import pandas as pd
import glob
from datetime import timedelta

def analyze_opponent(tag):
    all_files = glob.glob('src/data_csv_oficial/*.csv')
    dfs = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            df.columns = [c.lower() for c in df.columns]
            if 'tag_oponente' in df.columns:
                subset = df[df['tag_oponente'] == tag].copy()
                subset['source_file'] = f
                dfs.append(subset)
        except:
            continue
            
    if not dfs:
        print(f"Nenhuma luta encontrada para {tag}")
        return
        
    df_total = pd.concat(dfs, ignore_index=True)
    df_total['data_dt'] = pd.to_datetime(df_total['data'], format='%d/%m/%Y %H:%M', dayfirst=True)
    
    # Ordenar por data
    df_total = df_total.sort_values(by='data_dt')
    
    print(f"Total bruto encontrado: {len(df_total)}")
    print("\nLista de lutas (Bruto):")
    print(df_total[['data', 'nome_oponente', 'resultado', 'source_file']])
    
    # Deduplicação inteligente (Timezone shift de 3h)
    print("\n--- Analisando Duplicatas de Timezone (3h) ---")
    deduped = []
    processed_indices = set()
    
    rows = df_total.reset_index()
    for i, row in rows.iterrows():
        if i in processed_indices:
            continue
            
        current_time = row['data_dt']
        
        # Procurar por uma luta do mesmo oponente +- 3 horas (180 min)
        # que tenha o mesmo resultado e coroas
        potential_dup = rows[
            (rows.index != i) & 
            (rows['tag_oponente'] == row['tag_oponente']) &
            (rows['resultado'] == row['resultado']) &
            (abs((rows['data_dt'] - current_time).dt.total_seconds()) == 3*3600)
        ]
        
        if not potential_dup.empty:
            dup_row = potential_dup.iloc[0]
            print(f"Detectada duplicata de timezone: {row['data']} vs {dup_row['data']}")
            processed_indices.add(potential_dup.index[0])
            
        deduped.append(row)
        processed_indices.add(i)
        
    df_deduped = pd.DataFrame(deduped)
    print(f"\nTotal após deduplicação de timezone: {len(df_deduped)}")
    print(df_deduped[['data', 'nome_oponente', 'resultado']])

if __name__ == "__main__":
    analyze_opponent('#2YUG0LGP8')
