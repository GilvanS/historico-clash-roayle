import pandas as pd

def extract_from_global_recovery():
    csv_path = "src/data_csv_oficial/recuperacao_hp_global.csv"
    output_path = "src/data_csv_oficial/extracao_especifica_maio_2026_FINAL.csv"
    
    print(f"Lendo CSV de recuperação global: {csv_path}")
    # O arquivo usa ';' como separador conforme verificado
    df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
    
    target_dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
    
    # Filtrar por data
    # No CSV a coluna 'data' está no formato 'dd/mm/yyyy HH:MM'
    df_filtered = df[df['data'].str.contains('|'.join(target_dates), na=False)].copy()
    
    if not df_filtered.empty:
        # Colunas solicitadas: data, nome_oponente, tag_oponente, resultado, nivel_torre_jogador, 
        # vida_torre_rei_jogador, vida_torre_rei_oponente, vida_torres_princesa_jogador, vida_torres_princesa_oponente
        
        # Mapeamento de colunas baseado na observação do conteúdo:
        # data (0), nome_oponente (1), tag_oponente (2), ..., resultado (6), ...
        # nivel_torre_jogador (18), vida_torre_rei_jogador (19), vida_torre_rei_oponente (20), 
        # vida_torres_princesa_jogador (21), vida_torres_princesa_oponente (22)
        
        cols_to_keep = [
            'data', 'nome_oponente', 'tag_oponente', 'resultado',
            'nivel_torre_jogador', 'vida_torre_rei_jogador', 'vida_torre_rei_oponente',
            'vida_torres_princesa_jogador', 'vida_torres_princesa_oponente'
        ]
        
        # Verificar se as colunas existem (podem ter nomes ligeiramente diferentes no CSV lido)
        # Se o pandas não as identificou pelo nome no header, usaremos indexação
        
        final_df = df_filtered[cols_to_keep]
        
        final_df.to_csv(output_path, index=False, sep=';', encoding='utf-8')
        print(f"Sucesso! {len(final_df)} batalhas extraídas para: {output_path}")
        
        # Mostrar as primeiras linhas para conferência
        print("\nPreview dos dados extraídos:")
        print(final_df.head())
        return True
    else:
        print("Nenhuma batalha encontrada para as datas solicitadas.")
        return False

if __name__ == "__main__":
    extract_from_global_recovery()
