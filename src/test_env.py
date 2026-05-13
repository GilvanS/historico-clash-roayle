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
    tag_pri = os.getenv('CR_PLAYER_TAG')
    tag_sec = os.getenv('CR_PLAYER_TAG_SEC')
    
    print("=== RAIO-X DA CONEXAO (LOCAL/GITHUB) ===")
    
    try:
        ip_externo = requests.get('https://api.ipify.org').text
        print(f"INFO: Seu IP atual: {ip_externo}")
    except Exception as e:
        print(f"AVISO: Nao foi possivel determinar o IP externo: {e}")

    if token:
        print(f"SUCESSO: CR_API_TOKEN carregado (Tamanho: {len(token)})")
    else:
        print("ERRO: CR_API_TOKEN nao encontrado.")
        return

    accounts = [("Principal", tag_pri)]
    if tag_sec:
        accounts.append(("Secundaria", tag_sec))
    else:
        print("AVISO: CR_PLAYER_TAG_SEC nao encontrada nos segredos/env.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    for name, tag in accounts:
        if not tag:
            print(f"ERRO: Tag para {name} esta vazia.")
            continue
            
        print(f"\n--- Testando Conta: {name} ({tag}) ---")
        tag_clean = tag.strip().replace("#", "%23")
        url = f"https://proxy.royaleapi.dev/v1/players/{tag_clean}/battlelog"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print(f"VITORIA: Dados recebidos com sucesso!")
                data = response.json()
                print(f"Batalhas no log: {len(data)}")
            elif response.status_code == 403:
                print(f"BLOQUEIO (403): O IP {ip_externo} esta bloqueado ou o Token e invalido.")
            else:
                print(f"AVISO ({response.status_code}): {response.text[:100]}")
        except Exception as e:
            print(f"FALHA: Erro ao conectar: {e}")

if __name__ == "__main__":
    test()
