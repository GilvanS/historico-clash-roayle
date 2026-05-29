import os

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    index_path = os.path.join(root_dir, 'index.html')
    
    if not os.path.exists(index_path):
        print(f"ERRO: {index_path} nao existe!")
        return
        
    print(f"Lendo {index_path}...")
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print(f"Tamanho do arquivo: {len(content)} bytes")
    
    terms = [
        "switchRadarTab", 
        "switchAccountTab", 
        "DOMContentLoaded",
        "Sincronizando aba do Radar de Guerra",
        "Sincronizando aba de conta no topo",
        "Se não houver conta ativa no localStorage",
        "AutoRefresh",
        "upcoming-chests",
        "chests-container"
    ]
    
    for term in terms:
        count = content.count(term)
        print(f"O termo '{term}' aparece {count} vezes.")

if __name__ == "__main__":
    main()
