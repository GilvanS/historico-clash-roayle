#!/usr/bin/env python3
"""
Consolidador de Arquivos CSV Históricos
Consolida anos anteriores (2023-2025) em um único arquivo e gerencia zips automáticos
"""

import os
import glob
import pandas as pd
import zipfile
from datetime import datetime, timedelta
import shutil

def consolidar_anos_anteriores():
    """Consolida todos os anos anteriores (2023-2025) em um único arquivo"""
    
    csv_dir = "src/data_csv_oficial"
    output_file = "src/data_csv_oficial/historico_completo_2023_2025.csv"
    
    arquivos_anteriores = [
        "oponentes_ano_2023.csv",
        "oponentes_ano_2024.csv", 
        "oponentes_ano_2025.csv"
    ]
    
    dados_consolidados = []
    
    for arquivo in arquivos_anteriores:
        caminho = os.path.join(csv_dir, arquivo)
        if os.path.exists(caminho):
            try:
                df = pd.read_csv(caminho)
                if not df.empty:
                    dados_consolidados.append(df)
                    print(f"✅ Adicionado {arquivo}: {len(df)} registros")
                else:
                    print(f"⚠️  {arquivo} está vazio")
            except Exception as e:
                print(f"❌ Erro ao ler {arquivo}: {e}")
    
    if dados_consolidados:
        df_final = pd.concat(dados_consolidados, ignore_index=True)
        df_final.to_csv(output_file, index=False, encoding='utf-8')
        print(f"✅ Histórico consolidado salvo em: {output_file}")
        print(f"📊 Total de registros: {len(df_final)}")
        
        # Opcional: mover arquivos originais para backup
        backup_dir = "src/backup_anos_anteriores"
        os.makedirs(backup_dir, exist_ok=True)
        
        for arquivo in arquivos_anteriores:
            origem = os.path.join(csv_dir, arquivo)
            if os.path.exists(origem):
                destino = os.path.join(backup_dir, arquivo)
                shutil.move(origem, destino)
                print(f"📦 Movido {arquivo} para backup")
    else:
        print("⚠️  Nenhum dado anterior encontrado para consolidar")

def zipar_arquivos_antigos(dias_para_zip=2):
    """Zip automaticamente arquivos com mais de X dias"""
    
    csv_dir = "src/data_csv_oficial"
    backup_dir = "src/backup_before_dedup"
    
    # Data limite para zip (hoje - X dias)
    data_limite = datetime.now() - timedelta(days=dias_para_zip)
    
    # Procurar arquivos diários antigos
    padrao_diario = os.path.join(csv_dir, "oponentes_dia_*.csv")
    arquivos_diarios = glob.glob(padrao_diario)
    
    for arquivo in arquivos_diarios:
        # Extrair data do nome do arquivo
        nome_arquivo = os.path.basename(arquivo)
        try:
            data_str = nome_arquivo.replace("oponentes_dia_", "").replace(".csv", "")
            data_arquivo = datetime.strptime(data_str, "%Y%m%d")
            
            if data_arquivo < data_limite:
                # Criar zip
                zip_nome = f"{nome_arquivo.replace('.csv', '')}.zip"
                zip_path = os.path.join(backup_dir, zip_nome)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(arquivo, nome_arquivo)
                
                # Remover arquivo original após zip
                os.remove(arquivo)
                print(f"📦 Zip criado: {zip_nome} (arquivo removido)")
                
        except ValueError:
            continue

def main():
    print("=" * 60)
    print("CONSOLIDADOR DE ARQUIVOS CSV HISTÓRICOS")
    print("=" * 60)
    
    # 1. Consolidar anos anteriores
    print("\n1. Consolidando anos anteriores (2023-2025)...")
    consolidar_anos_anteriores()
    
    # 2. Zipar arquivos diários antigos
    print("\n2. Zipando arquivos diários com mais de 2 dias...")
    zipar_arquivos_antigos(dias_para_zip=2)
    
    print("\n" + "=" * 60)
    print("PROCESSO CONCLUÍDO!")
    print("=" * 60)
    print("✅ Anos anteriores consolidados em 'historico_completo_2023_2025.csv'")
    print("✅ Arquivos diários antigos zipados em backup_before_dedup/")
    print("✅ Arquivo principal 2026 mantido intacto para continuar recebendo dados")

if __name__ == "__main__":
    main()