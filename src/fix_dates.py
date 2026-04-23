import os
import pandas as pd
from datetime import datetime

def fix():
    csv_22 = 'a:/Workspace/historico-clash-roayle/src/oponentes_dia_20260422.csv'
    csv_23 = 'a:/Workspace/historico-clash-roayle/src/oponentes_dia_20260423.csv'
    
    if not os.path.exists(csv_22):
        print(f"Arquivo {csv_22} nao encontrado.")
        return

    df = pd.read_csv(csv_22)
    
    # Identifica linhas do dia 23
    # A data esta no formato "DD/MM/YYYY HH:MM"
    mask_23 = df['data'].str.startswith('23/04/2026')
    df_23 = df[mask_23]
    df_22 = df[~mask_23]
    
    # Salva o do dia 22 limpo
    df_22.to_csv(csv_22, index=False)
    print(f"Limpado {csv_22}: {len(df_22)} batalhas restantes.")
    
    # Salva ou anexa ao do dia 23
    if not df_23.empty:
        if os.path.exists(csv_23):
            df_existente = pd.read_csv(csv_23)
            df_final_23 = pd.concat([df_23, df_existente]).drop_duplicates(subset=['data', 'tag_oponente'])
            df_final_23.to_csv(csv_23, index=False)
        else:
            df_23.to_csv(csv_23, index=False)
        print(f"Gerado/Atualizado {csv_23}: {len(df_23)} batalhas movidas.")

if __name__ == "__main__":
    fix()
