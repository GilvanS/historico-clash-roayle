import pandas as pd
import subprocess
import os
from io import StringIO

def get_git_file_content(commit_hash, file_path):
    try:
        result = subprocess.run(
            ['git', 'show', f'{commit_hash}:{file_path}'],
            capture_output=True, text=True, encoding='utf-8', check=True
        )
        return result.stdout
    except Exception as e:
        print(f"Erro ao ler commit {commit_hash}: {e}")
        return None

def merge_csvs():
    file_path = "src/data_csv_oficial/oponentes_ano_2026.csv"
    
    # 1. Pegar dados do commit histórico (Jan-Abr 2026)
    historical_commit = "e1758e9fd"
    print(f"Lendo dados históricos do commit {historical_commit}...")
    historical_content = get_git_file_content(historical_commit, file_path)
    if not historical_content:
        return
    
    df_hist = pd.read_csv(StringIO(historical_content))
    print(f"Registros históricos: {len(df_hist)}")
    
    # 2. Pegar dados atuais (origin/main)
    print("Lendo dados atuais...")
    df_current = pd.read_csv(file_path)
    print(f"Registros atuais: {len(df_current)}")
    
    # Padronizar colunas para minúsculo
    df_hist.columns = [c.lower() for c in df_hist.columns]
    df_current.columns = [c.lower() for c in df_current.columns]
    
    # 3. Concatenar
    df_total = pd.concat([df_hist, df_current], ignore_index=True)
    
    # 4. Converter data para datetime para deduplicação precisa
    # Formato detectado: %d/%m/%Y %H:%M
    df_total['data_aux'] = pd.to_datetime(df_total['data'], format='%d/%m/%Y %H:%M', dayfirst=True)
    df_total = df_total.sort_values(by='data_aux')
    
    # 5. Deduplicação com janela de 2 minutos
    print("Iniciando deduplicação (janela de 2 min)...")
    final_rows = []
    if len(df_total) > 0:
        last_time = None
        last_opponent = None
        
        for _, row in df_total.iterrows():
            current_time = row['data_aux']
            current_opponent = row['tag_oponente']
            
            if last_time is not None and current_opponent == last_opponent:
                diff = (current_time - last_time).total_seconds() / 60
                if diff < 2:
                    continue # Duplicata técnica
            
            final_rows.append(row)
            last_time = current_time
            last_opponent = current_opponent
            
    df_final = pd.DataFrame(final_rows)
    df_final = df_final.drop(columns=['data_aux'])
    
    print(f"Registros finais após deduplicação: {len(df_final)}")
    
    # 6. Salvar
    df_final.to_csv(file_path, index=False)
    print(f"Arquivo {file_path} atualizado com sucesso!")

if __name__ == "__main__":
    merge_csvs()
