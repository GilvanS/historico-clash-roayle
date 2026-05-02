#!/usr/bin/env python3
"""
Script de consolidação manual - Converte dados diários para o arquivo anual 2026
"""

import pandas as pd
import glob
import os

def consolidar_2026():
    # Configurações
    csv_dir = "src/data_csv_oficial"
    arquivo_2026 = "oponentes_ano_2026.csv"
    
    print("PROCURANDO arquivos diários de 2026...")
    
    # Encontrar todos os arquivos diários de 2026
    arquivos_diarios = glob.glob(os.path.join(csv_dir, "oponentes_dia_2026*.csv"))
    
    if not arquivos_diarios:
        print("❌ Nenhum arquivo diário de 2026 encontrado!")
        return
    
        print(f"ENCONTRADOS {len(arquivos_diarios)} arquivos diarios")
    
    # Ler dados existentes de 2026
    caminho_2026 = os.path.join(csv_dir, arquivo_2026)
    
    if os.path.exists(caminho_2026):
        df_2026 = pd.read_csv(caminho_2026, sep=';', encoding='utf-8')
        print(f"ARQUIVO 2026 atual: {len(df_2026)} registros")
    else:
        print("⚠️  Arquivo 2026 não existe, criando novo...")
        df_2026 = pd.DataFrame()
    
    # Consolidar todos os arquivos diários
    novos_dados = []
    
    for arquivo in arquivos_diarios:
        try:
            df_diario = pd.read_csv(arquivo, sep=',', encoding='utf-8')
            if not df_diario.empty:
                novos_dados.append(df_diario)
                print(f"ADICIONADO {os.path.basename(arquivo)}: {len(df_diario)} registros")
        except Exception as e:
            print(f"ERRO ao ler {arquivo}: {e}")
    
    if novos_dados:
        # Combinar todos os dados
        df_novos = pd.concat(novos_dados, ignore_index=True)
        
        # Combinar com dados existentes (evitar duplicatas)
        if not df_2026.empty:
            # Usar coluna de data/hora para evitar duplicatas
            coluna_timestamp = df_2026.columns[0]  # Primeira coluna (data/hora)
            
            # Encontrar registros novos que não estão no arquivo 2026
            # Converter para string para comparar corretamente
            mask = ~df_novos[coluna_timestamp].astype(str).isin(df_2026[coluna_timestamp].astype(str))
            df_unicos = df_novos[mask]
            
            print(f"REGISTROS unicos a adicionar: {len(df_unicos)}")
            
            if not df_unicos.empty:
                df_final = pd.concat([df_2026, df_unicos], ignore_index=True)
            else:
                df_final = df_2026
                print("NENHUM registro novo para adicionar")
        else:
            df_final = df_novos
        
        # Salvar com ponto-e-vírgula (formato correto)
        df_final.to_csv(caminho_2026, index=False, sep=';', encoding='utf-8')
        print(f"ARQUIVO 2026 salvo: {len(df_final)} registros totais")
        print(f"ADICIONADOS: {len(df_final) - len(df_2026) if not df_2026.empty else len(df_final)} novos registros")
    else:
        print("⚠️  Nenhum dado novo para consolidar")

if __name__ == "__main__":
    print("=" * 50)
    print("CONSOLIDADOR DE DADOS 2026")
    print("=" * 50)
    
    consolidar_2026()
    
    print("\n✅ Processo concluído!")