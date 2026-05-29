import os
import re

def mega_fix_csv(file_path):
    print(f"Iniciando Mega Fix estrutural em {file_path}...")
    if not os.path.exists(file_path):
        print("Arquivo não encontrado!")
        return

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    fixed_lines = []
    header = lines[0]
    fixed_lines.append(header)
    
    # Padrao para identificar a TAG (ex: #89U2YVLY ou #ABC123)
    tag_pattern = re.compile(r'^#[0-9A-Z]+$')
    # Padroes para Resultado (aceita PT e EN)
    results = ['Vitoria', 'Derrota', 'Empate', 'victory', 'defeat', 'draw', 'Victory', 'Defeat', 'Draw']

    correcoes = 0
    for i, line in enumerate(lines[1:], 1):
        clean_line = line.replace('"', '')
        parts = clean_line.strip().split(';')
        
        # Condicao de erro: mais colunas que o esperado OU a TAG nao esta na 3a coluna
        needs_fix = len(parts) > 28
        if not needs_fix and len(parts) >= 3:
            if not tag_pattern.match(parts[2]):
                needs_fix = True

        if needs_fix:
            correcoes += 1
            if "Duduzin" in line:
                print(f"Corrigindo Duduzin na linha {i} (TAG na coluna errada ou colunas extras)")
            
            new_parts = []
            # 1. Data e Hora
            new_parts.append(parts[0])
            
            # 2. Reconstruir o Nome ate encontrar a TAG
            current_idx = 1
            name_parts = []
            while current_idx < len(parts) and not tag_pattern.match(parts[current_idx]):
                name_parts.append(parts[current_idx])
                current_idx += 1
            
            # Sanitiza o nome trocando ; por -
            name_full = "-".join(name_parts)
            new_parts.append(name_full)
            
            # 3. Adicionar a TAG
            if current_idx < len(parts):
                new_parts.append(parts[current_idx])
                current_idx += 1
            else:
                new_parts.append("") # Fallback se nao achar tag
            
            # 4. Adicionar campos numericos
            for _ in range(3):
                if current_idx < len(parts):
                    new_parts.append(parts[current_idx])
                    current_idx += 1
                else:
                    new_parts.append("0")
            
            # 5. Reconstruir Clã ate encontrar o Resultado
            clan_parts = []
            while current_idx < len(parts) and parts[current_idx] not in results:
                clan_parts.append(parts[current_idx])
                current_idx += 1
            
            new_parts.append(" ".join(clan_parts).replace(';', '-'))
            
            # 6. Adicionar o resto dos campos
            while current_idx < len(parts):
                new_parts.append(parts[current_idx])
                current_idx += 1
            
            # Ajuste final para 28 colunas
            if len(new_parts) > 28:
                new_parts = new_parts[:28]
            elif len(new_parts) < 28:
                new_parts.extend([''] * (28 - len(new_parts)))
                
            fixed_lines.append(";".join(new_parts) + "\n")
        else:
            fixed_lines.append(clean_line.strip() + "\n")

    with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
        f.writelines(fixed_lines)
    
    print(f"Mega Fix concluido. {len(fixed_lines)} linhas processadas. {correcoes} correcoes feitas.")

if __name__ == "__main__":
    target = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'
    mega_fix_csv(target)
