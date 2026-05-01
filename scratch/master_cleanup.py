import pandas as pd
import glob
import os
import csv

def clean_and_redistribute():
    # 1. Carregar todos os dados de todos os CSVs oficiais
    all_files = glob.glob('src/data_csv_oficial/oponentes_ano_*.csv')
    all_files.append('src/data_csv_oficial/dados_manuais_preservados.csv')
    
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
    
    # 2. Converter data para datetime com suporte a formatos mistos
    df_all['data_dt'] = pd.to_datetime(df_all['data'], errors='coerce', dayfirst=True)
    
    # Remover registros que não puderam ser convertidos
    initial_len = len(df_all)
    df_all = df_all.dropna(subset=['data_dt'])
    if len(df_all) < initial_len:
        print(f"Aviso: {initial_len - len(df_all)} registros removidos por erro de data.")
    
    # Padronizar a string de data para o formato do projeto: DD/MM/YYYY HH:MM
    df_all['data'] = df_all['data_dt'].dt.strftime('%d/%m/%Y %H:%M')
    
    # 3. Ordenar
    df_all = df_all.sort_values(by='data_dt')
    
    # 4. Deduplicação Global (Janela de 2 min)
    print("Deduplicando (janela 2 min)...")
    final_rows = []
    last_time = None
    last_tag = None
    
    for _, row in df_all.iterrows():
        current_time = row['data_dt']
        current_tag = row['tag_oponente']
        
        if last_time is not None and current_tag == last_tag:
            diff = abs((current_time - last_time).total_seconds()) / 60
            if diff < 2:
                continue # Pula duplicata exata/próxima
        
        final_rows.append(row)
        last_time = current_time
        last_tag = current_tag
        
    df_clean = pd.DataFrame(final_rows)
    
    # 5. Deduplicação de Timezone (Janela de 180 min com mesmo resultado)
    print("Deduplicando Timezone (shift 3h)...")
    # Para cada luta, se houver outra luta do mesmo oponente exatamente 3h depois com mesmo resultado, remover.
    # Vamos usar uma abordagem conservadora.
    df_clean = df_clean.sort_values(by='data_dt')
    tz_deduped = []
    processed = set()
    
    clean_list = df_clean.to_dict('records')
    for i, row in enumerate(clean_list):
        if i in processed:
            continue
            
        # Procurar à frente por uma luta do mesmo oponente em +- 3h
        for j in range(i + 1, min(i + 100, len(clean_list))):
            next_row = clean_list[j]
            time_diff = abs((next_row['data_dt'] - row['data_dt']).total_seconds())
            
            # 3h = 10800 segundos. Permitir margem de 2 min (120s) no shift
            if abs(time_diff - 10800) < 120 and next_row['tag_oponente'] == row['tag_oponente'] and next_row['resultado'] == row['resultado']:
                print(f"Removendo duplicata TZ: {row['data']} vs {next_row['data']} ({row['tag_oponente']})")
                processed.add(j)
                break
        
        tz_deduped.append(row)
        
    df_final = pd.DataFrame(tz_deduped)
    df_final = df_final.drop(columns=['data_dt'])
    
    # 6. Redistribuir por ano
    print("\nRedistribuindo arquivos...")
    # Limpar arquivos antigos para evitar resíduos
    for f in glob.glob('src/data_csv_oficial/oponentes_ano_*.csv'):
        # Criar backup ou apenas sobrescrever? Vamos sobrescrever com os dados limpos.
        pass

    # Agrupar por ano da coluna 'data'
    df_final['ano_aux'] = df_final['data'].apply(lambda x: x.split(' ')[0].split('/')[-1])
    
    for ano, group in df_final.groupby('ano_aux'):
        target_file = f'src/data_csv_oficial/oponentes_ano_{ano}.csv'
        # Salvar e sanitizar (remover .0)
        group_to_save = group.drop(columns=['ano_aux'])
        
        # Sanitização de tipos
        for col in group_to_save.columns:
            if col in ['vezes_enfrentado', 'nivel_oponente', 'trofes_oponente', 'coroas_jogador', 'coroas_oponente', 'mudanca_trofes']:
                group_to_save[col] = pd.to_numeric(group_to_save[col], errors='coerce').fillna(0).astype(int)
        
        group_to_save.to_csv(target_file, index=False)
        print(f"Salvo: {target_file} ({len(group_to_save)} registros)")

    print("\nProcesso concluído!")

if __name__ == "__main__":
    clean_and_redistribute()
