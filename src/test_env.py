import os
import requests

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    # Remove aspas se existirem
                    value = value.strip('"').strip("'")
                    os.environ[key] = value

def test():
    load_env()
    token = os.getenv('CR_API_TOKEN')
    tag = os.getenv('CR_PLAYER_TAG')
    
    print("=== RAIO-X DA CONEXAO (LOCAL/GITHUB) ===")
    
    try:
        ip_externo = requests.get('https://api.ipify.org').text
        print(f"INFO: Seu IP atual: {ip_externo}")
    except Exception as e:
        print(f"AVISO: Nao foi possivel determinar o IP externo: {e}")

    if token:
        print(f"SUCESSO: CR_API_TOKEN carregado (Tamanho: {len(token)})")
    else:
        print("ERRO: CR_API_TOKEN nao encontrado no .env ou no sistema.")
        return

    tag_clean = tag.replace("#", "%23")
    endpoints = {
        "Proxy RoyaleAPI": f"https://proxy.royaleapi.dev/v1/players/{tag_clean}/battlelog",
        "API Oficial Supercell": f"https://api.clashroyale.com/v1/players/{tag_clean}/battlelog"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    for name, url in endpoints.items():
        print(f"\n--- Testando: {name} ---")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print(f"VITORIA: Conexao estabelecida com {name}!")
            elif response.status_code == 403:
                print(f"BLOQUEIO (403): O IP {ip_externo} esta bloqueado para {name}.")
            else:
                print(f"AVISO ({response.status_code}): {response.text[:100]}")
        except Exception as e:
            print(f"FALHA: Erro ao conectar com {name}: {e}")

if __name__ == "__main__":
    test()
