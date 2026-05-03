#!/usr/bin/env python3
"""
Coleta o ciclo de baús do jogador e salva em JSON para o Dashboard.
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def collect_chests():
    token = os.getenv('CR_API_TOKEN')
    tag = os.getenv('CR_PLAYER_TAG').replace('#', '')
    
    if not token or not tag:
        print("[ERRO] Token ou Tag não configurados.")
        return

    url = f"https://proxy.royaleapi.dev/v1/players/%23{tag}/upcomingchests"
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"Buscando ciclo de baús para #{tag}...")
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Define diretório de saída
        root_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(root_dir, 'data_csv_oficial')
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, 'upcoming_chests.json')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        print(f"Ciclo de baús salvo com sucesso em: {output_path}")
        
    except Exception as e:
        print(f"[ERRO] Falha ao coletar baús: {e}")

if __name__ == "__main__":
    collect_chests()
