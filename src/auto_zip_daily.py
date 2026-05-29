#!/usr/bin/env python3
"""
Script automático para zipar arquivos diários antigos
Executar diariamente via agendador/cron
"""

import os
import glob
import zipfile
from datetime import datetime, timedelta

def zip_daily_files_older_than(days=2):
    """Zip automaticamente arquivos diários com mais de X dias"""
    
    csv_dir = "data/csv"
    backup_dir = "src/backup_before_dedup"
    
    # Garantir que diretório de backup existe
    os.makedirs(backup_dir, exist_ok=True)
    
    # Data limite para zip (hoje - X dias)
    data_limite = datetime.now() - timedelta(days=days)
    
    print(f"📅 Zipando arquivos anteriores a: {data_limite.strftime('%Y-%m-%d')}")
    
    # Procurar arquivos diários
    padrao_diario = os.path.join(csv_dir, "oponentes_dia_*.csv")
    arquivos_diarios = glob.glob(padrao_diario)
    
    zipped_count = 0
    
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
                
                # Verificar se zip já existe
                if not os.path.exists(zip_path):
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        zipf.write(arquivo, nome_arquivo)
                    
                    # Remover arquivo original após zip
                    os.remove(arquivo)
                    print(f"✅ Zip criado: {zip_nome}")
                    zipped_count += 1
                else:
                    print(f"⚠️  Zip já existe: {zip_nome}")
                    
        except ValueError:
            continue
    
    print(f"📦 Total de arquivos zipados: {zipped_count}")
    return zipped_count

def main():
    print("=" * 50)
    print("ZIP AUTOMÁTICO DE ARQUIVOS DIÁRIOS")
    print("=" * 50)
    
    zip_daily_files_older_than(days=2)
    
    print("\n✅ Processo concluído!")

if __name__ == "__main__":
    main()