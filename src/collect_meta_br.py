#!/usr/bin/env python3
"""
Coleta o Top 100 do Brasil na Rota das Lendas (Path of Legends).
Parte do Plano de Expansão 2026 - Dia 2.
"""

import os
import sys
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def is_reset_day():
    """Verifica se hoje é o dia do reset (1ª segunda-feira do mês)."""
    now = datetime.now()
    # 0 = Segunda-feira
    return now.weekday() == 0 and now.day <= 7

def collect_meta_br():
    token = os.getenv('CR_API_TOKEN')
    location_id = "57000038" # Brasil
    
    if not token:
        print("[ERRO] Token da API não configurado.")
        sys.stdout.flush()
        return

    # Calcula hora BRT (UTC-3) para trava de reset
    # datetime.now() no GitHub Actions é UTC
    import datetime as dt_module
    brt_now = datetime.utcnow() - dt_module.timedelta(hours=3)
    
    # Regra: No dia do reset, coletar apenas após as 12h BRT
    if is_reset_day() and brt_now.hour < 12:
        print(f"[AVISO] Dia de Reset detectado ({brt_now.strftime('%d/%m')}). Hora BRT atual: {brt_now.hour}h. Coleta suspensa até as 12h BRT.")
        sys.stdout.flush()
        return

    url = f"https://proxy.royaleapi.dev/v1/locations/{location_id}/rankings/players?limit=100"
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"Buscando Top 100 Brasil (Ladder)...")
    sys.stdout.flush()
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        # Validação: Se retornar itens vazios, não sobrescrever o arquivo oficial
        items = data.get('items', [])
        if not items:
            print("[AVISO] API retornou ranking vazio. Mantendo dados anteriores para evitar dashboard em branco.")
            sys.stdout.flush()
            return

        # Adiciona timestamp da coleta
        data['collected_at'] = now.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Define diretório de saída
        root_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(root_dir, 'data_csv_oficial')
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, 'meta_brasil_top100.json')
        
        # Salva apenas se houver dados
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        print(f"Ranking Meta BR atualizado com sucesso: {len(items)} jogadores.")
        sys.stdout.flush()
        
    except Exception as e:
        print(f"[ERRO] Falha ao coletar Meta BR: {e}")
        sys.stdout.flush()

if __name__ == "__main__":
    collect_meta_br()
