import os
import glob
import sys

# Ensure config can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import config
    csv_dir = config.DATA_DIR
except ImportError:
    csv_dir = r'a:\Workspace\historico-clash-roayle\data\csv'

def clean_csv_conflicts():
    files = glob.glob(os.path.join(csv_dir, "*.csv"))
    
    markers = ["<<<<<<<", "=======", ">>>>>>>"]
    
    for file_path in files:
        print(f"Limpando conflitos em: {file_path}")
        with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = f.readlines()
        
        new_lines = []
        conflicts_found = False
        for line in lines:
            if any(marker in line for marker in markers):
                conflicts_found = True
                continue
            new_lines.append(line)
        
        if conflicts_found:
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(new_lines)
            print(f"  -> Conflitos removidos.")
        else:
            print(f"  -> Nenhum conflito encontrado.")

if __name__ == "__main__":
    clean_csv_conflicts()
