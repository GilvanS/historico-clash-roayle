#!/usr/bin/env python3
"""
Adição MANUAL dos dados de maio ao arquivo 2026
"""

# Ler dados diários (maio)
with open('src/data_csv_oficial/oponentes_dia_20260501.csv', 'r', encoding='utf-8') as f:
    dados_diarios = f.readlines()

# Ler dados anuais (2026)  
with open('src/data_csv_oficial/oponentes_ano_2026.csv', 'r', encoding='utf-8') as f:
    dados_anuais = f.readlines()

print(f"Dados diários: {len(dados_diarios)} linhas")
print(f"Dados anuais: {len(dados_anuais)} linhas")

# Adicionar dados de maio (pular cabeçalho)
dados_anuais.extend(dados_diarios[1:])

print(f"Total após adição: {len(dados_anuais)} linhas")

# Salvar arquivo atualizado
with open('src/data_csv_oficial/oponentes_ano_2026.csv', 'w', encoding='utf-8') as f:
    f.writelines(dados_anuais)

print("Dados de maio adicionados manualmente!")

# Verificar
with open('src/data_csv_oficial/oponentes_ano_2026.csv', 'r', encoding='utf-8') as f:
    linhas = f.readlines()
    print(f"Verificação: {len(linhas)} linhas totais")