#!/usr/bin/env python3
"""
Coleta o Top 100 do Brasil na Rota das Lendas (Path of Legends).
Parte do Plano de Expansão 2026 - Dia 2.
"""

import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def collect_meta_br():
    token = os.getenv('CR_API_TOKEN')
    # Localização Brasil: 57000038
    location_id = "57000038"
    
    if not token:
        print("[ERRO] Token da API não configurado.")
        return

    # Endpoint: /locations/{locationId}/rankings/players
    # Nota: rankings/pathoflegend regional retornou 404, usando ladder regional.
    url = f"https://proxy.royaleapi.dev/v1/locations/{location_id}/rankings/players?limit=100"
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"Buscando Top 100 Brasil (Rota das Lendas)...")
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        # Adiciona timestamp da coleta
        data['collected_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        print(f"DEBUG: Chaves no JSON: {list(data.keys())}")
        if 'items' not in data or not data['items']:
            print(f"DEBUG: Conteudo de data: {json.dumps(data, indent=2)[:500]}")
        
        # Define diretório de saída
        root_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(root_dir, 'data_csv_oficial')
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, 'meta_brasil_top100.json')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        print(f"Ranking Meta BR salvo com sucesso em: {output_path}")
        print(f"Total de jogadores coletados: {len(data.get('items', []))}")
        
    except Exception as e:
        print(f"[ERRO] Falha ao coletar Meta BR: {e}")

if __name__ == "__main__":
    collect_meta_br()
