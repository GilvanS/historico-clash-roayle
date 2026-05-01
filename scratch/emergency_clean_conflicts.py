import os
import re

def clean_csv_conflicts(directory):
    print(f"Limpando marcadores de conflito em: {directory}")
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Filtra linhas de conflito e limpa sujeira no final das linhas
            clean_lines = []
            for line in lines:
                # Remove marcadores de conflito
                if any(marker in line for marker in ["<<<<<<<", "=======", ">>>>>>>"]):
                    print(f"  - Marcador removido de {filename}")
                    continue
                
                # Se a linha contiver o marcador mas não iniciar com ele (ex: no cabeçalho)
                line = re.sub(r',?<<<<<<<.*$', '', line)
                line = re.sub(r',?=======.*$', '', line)
                line = re.sub(r',?>>>>>>>.*$', '', line)
                
                # Remove espaços em branco extras e vírgulas pendentes no final
                line = line.strip()
                if line:
                    clean_lines.append(line + "\n")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(clean_lines)
            print(f"  - {filename} limpo.")

if __name__ == "__main__":
    target_dir = "src/data_csv_oficial"
    clean_csv_conflicts(target_dir)
