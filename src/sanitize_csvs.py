import os
import glob

def clean_csv_files(data_dir):
    pattern = os.path.join(data_dir, 'oponentes_*.csv')
    files = glob.glob(pattern)
    
    # Adicionar outros arquivos principais se existirem
    files.extend([
        os.path.join(data_dir, 'ano_2026.csv'),
        os.path.join(data_dir, 'mes_202604.csv'),
        os.path.join(data_dir, 'oponentes_ano_2026.csv'),
        os.path.join(data_dir, 'oponentes_mes_202604.csv')
    ])
    
    for file_path in files:
        if not os.path.exists(file_path):
            continue
            
        print(f"Limpando {file_path}...")
        
        cleaned_rows = []
        header = None
        
        try:
            # Tenta ler com utf-8-sig para lidar com BOM
            with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
                content = f.readlines()
                
            if not content:
                continue
                
            # Identifica o header
            header = content[0].strip()
            
            delimiter = ';' if ';' in header else ','

            for line in content[1:]:
                line = line.strip()
                if line.startswith('<<<<<<<') or line.startswith('=======') or line.startswith('>>>>>>>'):
                    print(f"  - Removendo linha de conflito: {line[:20]}...")
                    continue
                
                if not line or line.replace(',', '').replace(';', '').strip() == '':
                    continue
                
                cleaned_rows.append(line)
            
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(header + '\n')
                for row in cleaned_rows:
                    f.write(row + '\n')
                    
            print(f"  - Sucesso: {len(cleaned_rows)} linhas mantidas.")
            
        except Exception as e:
            print(f"  - Erro ao processar {file_path}: {e}")

if __name__ == "__main__":
    # Usa o diretório do script como base (src/)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data_csv_oficial')
    clean_csv_files(data_dir)
