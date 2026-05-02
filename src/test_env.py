import os

def test():
    token = os.getenv('CR_API_TOKEN')
    tag = os.getenv('CR_PLAYER_TAG')
    
    print("=== TESTE DE VARIAVEIS DE AMBIENTE ===")
    if token:
        print(f"OK - CR_API_TOKEN: Carregado (Tamanho: {len(token)} caracteres)")
        if len(token) > 50:
            print("INFO: O token parece ter um tamanho valido.")
    else:
        print("ERRO - CR_API_TOKEN: NAO ENCONTRADO")
        
    if tag:
        print(f"OK - CR_PLAYER_TAG: Carregado (Valor: {tag})")
    else:
        print("ERRO - CR_PLAYER_TAG: NAO ENCONTRADO")

if __name__ == "__main__":
    test()
