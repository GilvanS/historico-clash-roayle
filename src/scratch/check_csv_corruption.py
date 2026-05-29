import csv

file_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'

with open(file_path, mode='r', encoding='utf-8') as f:
    reader = csv.reader(f, delimiter=';')
    header = next(reader)
    
    # Encontrar índice de trofes_iniciais_jogador
    try:
        idx_trofes = header.index('trofes_iniciais_jogador')
        idx_tag = header.index('tag_oponente')
        idx_nome = header.index('nome_oponente')
    except ValueError:
        print("Coluna não encontrada")
        exit()

    print(f"Analisando {file_path}...")
    print(f"Colunas: trofes_iniciais_jogador (index {idx_trofes}), tag_oponente (index {idx_tag})")
    
    problems = []
    for i, row in enumerate(reader, start=2):
        if len(row) <= idx_trofes:
            continue
            
        val = row[idx_trofes]
        if val.startswith('#'):
            problems.append((i, row[idx_nome], row[idx_tag], val))
            if len(problems) >= 10:
                break

    if problems:
        print("\nLinhas com problemas detectadas (troféus começando com #):")
        for p in problems:
            print(f"Linha {p[0]}: Nome={p[1]}, Tag={p[2]}, Valor em Troféus={p[3]}")
    else:
        print("\nNenhuma linha com # em trofes_iniciais_jogador encontrada nas primeiras verificações.")
