import os
import csv

def verify_csv_files(data_dir):
    """Verifica integridade dos CSVs sem modificar nada."""
    arquivo = os.path.join(data_dir, 'oponentes_ano_2026.csv')
    
    if not os.path.exists(arquivo):
        print(f"Arquivo nao encontrado: {arquivo}")
        return
    
    print(f"Verificando {arquivo}...")
    
    try:
        with open(arquivo, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f, delimiter=';')
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        conflitos = 0
        vazias = 0
        for row in rows:
            values = list(row.values())
            if any(str(v).startswith('<<<<<<<') or str(v).startswith('=======') or str(v).startswith('>>>>>>>') for v in values):
                conflitos += 1
            if not any(str(v).strip() for v in values):
                vazias += 1
        
        print(f"  - Total: {len(rows)} batalhas")
        print(f"  - Colunas: {len(fieldnames)}")
        print(f"  - Conflitos Git: {conflitos}")
        print(f"  - Linhas vazias: {vazias}")
        print(f"  - Status: OK" if conflitos == 0 and vazias == 0 else f"  - Status: PROBLEMAS DETECTADOS")
        
    except Exception as e:
        print(f"  - Erro: {e}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data_csv_oficial')
    verify_csv_files(data_dir)