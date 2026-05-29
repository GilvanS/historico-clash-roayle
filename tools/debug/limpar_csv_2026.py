#!/usr/bin/env python3
"""
Script para limpar caracteres inválidos do CSV 2026
"""

import pandas as pd
import re

def limpar_csv():
    csv_path = "src/data_csv_oficial/oponentes_ano_2026.csv"
    
    print("LENDO arquivo CSV...")
    
    # Ler como texto para limpar caracteres inválidos
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        linhas = f.readlines()
    
    print(f"Linhas totais: {len(linhas)}")
    
    # Limpar caracteres inválidos
    linhas_limpas = []
    for i, linha in enumerate(linhas, 1):
        # Remover caracteres não-ASCII exceto ; e |
        linha_limpa = re.sub(r'[^\x00-\x7F;|]', '', linha)
        linhas_limpas.append(linha_limpa)
    
    # Salvar arquivo limpo
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.writelines(linhas_limpas)
    
    print("ARQUIVO LIMPO salvo!")
    
    # Agora tentar ler com pandas
    try:
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
        print(f"CSV carregado com sucesso: {len(df)} registros")
        return True
    except Exception as e:
        print(f"ERRO ao ler CSV limpo: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("LIMPADOR DE CSV 2026")
    print("=" * 50)
    
    if limpar_csv():
        print("\nSUCESSO! Arquivo limpo e válido.")
    else:
        print("\nFALHA! Verifique manualmente o arquivo.")