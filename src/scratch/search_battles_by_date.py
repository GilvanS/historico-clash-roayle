#!/usr/bin/env python3
"""
Script para buscar batalhas de um dia específico na API do Clash Royale.
"""

import requests
import sys
from datetime import datetime

def search_battles(token: str, player_tag: str, target_date: str):
    """
    Busca batalhas e filtra pela data (formato YYYY-MM-DD ou YYYYMMDD)
    """
    base_url = "https://proxy.royaleapi.dev/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    clean_tag = player_tag.replace('#', '')
    url = f"{base_url}/players/%23{clean_tag}/battlelog"
    
    # Limpa a data alvo para comparação
    target_date_clean = target_date.replace('-', '').replace('/', '')
    
    print(f"Buscando batalhas para o dia: {target_date}")
    print(f"Player: {player_tag}")
    print("-" * 60)
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Erro na API: {response.status_code}")
            print(response.text)
            return
            
        battles = response.json()
        found_battles = []
        
        for battle in battles:
            # Exemplo de battleTime: 20260426T212510.000Z
            battle_time = battle.get('battleTime', '')
            battle_date = battle_time.split('T')[0] # 20260426
            
            if battle_date == target_date_clean:
                found_battles.append(battle)
        
        if not found_battles:
            print(f"Nenhuma batalha encontrada na API para o dia {target_date}.")
            print(f"Nota: A API retorna apenas as últimas ~25 batalhas recentes.")
        else:
            print(f"Encontradas {len(found_battles)} batalhas:")
            for i, b in enumerate(found_battles, 1):
                opponent = b.get('opponent', [{}])[0]
                team = b.get('team', [{}])[0]
                
                # Formata a hora para facilitar a leitura
                raw_time = b.get('battleTime', '')
                time_part = raw_time.split('T')[1].split('.')[0]
                formatted_time = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                
                print(f"\n[{i}] Hora: {formatted_time} (UTC)")
                print(f"    Tipo: {b.get('type')} | Modo: {b.get('gameMode', {}).get('name')}")
                print(f"    Resultado: {team.get('crowns')} x {opponent.get('crowns')} " + 
                      f"({'Vitória' if team.get('crowns') > opponent.get('crowns') else 'Derrota' if team.get('crowns') < opponent.get('crowns') else 'Empate'})")
                print(f"    Oponente: {opponent.get('name')} ({opponent.get('tag')})")
                
    except Exception as e:
        print(f"Erro ao processar: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python search_battles_by_date.py <token> <player_tag> <data_YYYY-MM-DD>")
        print("Exemplo: python search_battles_by_date.py 'SEU_TOKEN' '#2QR292P' '2026-04-26'")
        sys.exit(1)
    
    token = sys.argv[1]
    tag = sys.argv[2]
    data = sys.argv[3]
    
    search_battles(token, tag, data)
