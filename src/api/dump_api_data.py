import os
import requests
import json
from dotenv import load_dotenv

# Carregar variaveis do .env local
def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    value = value.strip('"').strip("'")
                    os.environ[key] = value

def get_latest_battles():
    load_env()
    token = os.getenv('CR_API_TOKEN')
    tag = os.getenv('CR_PLAYER_TAG').replace("#", "%23")
    
    if not token or not tag:
        print("Erro: Variaveis de ambiente nao encontradas.")
        return

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    try:
        # Buscar as ultimas 15 batalhas para garantir visibilidade
        response = requests.get(f"https://proxy.royaleapi.dev/v1/players/{tag}/battlelog", headers=headers)
        if response.status_code == 200:
            battles = response.json()
            print(f"INFO: Encontradas {len(battles)} batalhas no log.")
            
            # Listar os nomes dos oponentes e horarios das 10 mais recentes
            print("\n=== ULTIMAS 10 BATALHAS NO LOG DA API ===")
            for i, b in enumerate(battles[:10]):
                time = b.get('battleTime')
                opponent = b.get('opponent', [{}])[0].get('name', 'N/A')
                mode = b.get('gameMode', {}).get('name', 'N/A')
                print(f"{i+1}. Oponente: {opponent} | Hora: {time} | Modo: {mode}")
            
            # Salvar o dump completo da mais recente para analise de campos
            with open('api_latest_check.json', 'w') as f:
                json.dump(battles[0], f, indent=4)
        else:
            print(f"Erro na API: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    get_latest_battles()
