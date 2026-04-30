import pandas as pd
import csv
import glob
import os

def sanitize_csvs():
    files = glob.glob('src/data_csv_oficial/*.csv')
    for f in files:
        try:
            print(f"Sanitizando {f}...")
            df = pd.read_csv(f)
            
            # Padronizar colunas para minúsculo
            df.columns = [c.lower() for c in df.columns]
            
            # Mapeamento de colunas para tipos
            # vezes_enfrentado deve ser no mínimo 1
            if 'vezes_enfrentado' in df.columns:
                df['vezes_enfrentado'] = pd.to_numeric(df['vezes_enfrentado'], errors='coerce').fillna(1).astype(int)
            
            # Outras colunas numéricas
            num_cols = [
                'nivel_oponente', 'trofes_oponente', 'coroas_jogador', 
                'coroas_oponente', 'mudanca_trofes'
            ]
            for col in num_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
            # Salvar usando o motor do pandas mas com formatação de float vazia (embora já sejam ints)
            # Para ter certeza absoluta, convertemos tudo para string antes de salvar
            df_str = df.astype(str)
            
            # Remover o ".0" de qualquer string que tenha sobrado (segurança extra)
            for col in df_str.columns:
                df_str[col] = df_str[col].apply(lambda x: x.replace('.0', '') if x.endswith('.0') else x)
                # Também remover 'nan' strings
                df_str[col] = df_str[col].apply(lambda x: '' if x == 'nan' else x)

            df_str.to_csv(f, index=False, quoting=csv.QUOTE_MINIMAL)
            print(f"Sucesso: {f}")
            
        except Exception as e:
            print(f"Erro ao sanitizar {f}: {e}")

if __name__ == "__main__":
    sanitize_csvs()
