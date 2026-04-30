import pandas as pd
import os
from datetime import datetime, timedelta

def update_sub_csvs():
    main_file = "src/data_csv_oficial/oponentes_ano_2026.csv"
    if not os.path.exists(main_file):
        print("Arquivo principal não encontrado.")
        return
        
    df = pd.read_csv(main_file)
    # Padronizar colunas para minúsculo
    df.columns = [c.lower() for c in df.columns]
    
    df['dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M', dayfirst=True)
    
    # Atualizar Mensais
    for month in range(1, 13):
        month_str = f"{month:02d}"
        month_file = f"src/data_csv_oficial/oponentes_mes_{month_str}_2026.csv"
        df_month = df[df['dt'].dt.month == month].copy()
        if not df_month.empty:
            df_month = df_month.drop(columns=['dt'])
            df_month.to_csv(month_file, index=False)
            print(f"Atualizado: {month_file} ({len(df_month)} registros)")

    # Atualizar Semanais
    today = datetime.now()
    last_7_days = today - timedelta(days=7)
    weekly_file = "src/data_csv_oficial/oponentes_semana_atual.csv"
    df_weekly = df[df['dt'] >= last_7_days].copy()
    if not df_weekly.empty:
        df_weekly = df_weekly.drop(columns=['dt'])
        df_weekly.to_csv(weekly_file, index=False)
        print(f"Atualizado: {weekly_file} ({len(df_weekly)} registros)")

if __name__ == "__main__":
    update_sub_csvs()
