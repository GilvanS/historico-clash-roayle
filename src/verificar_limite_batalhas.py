#!/usr/bin/env python3
"""
Script para verificar quantas batalhas a API retorna
"""

import requests
import sys
from datetime import datetime

def verificar_batalhas(token: str, player_tag: str):
    """Verifica quantas batalhas a API retorna"""
    base_url = "https://proxy.royaleapi.dev/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    clean_tag = player_tag.replace('#', '')
    url = f"{base_url}/players/%23{clean_tag}/battlelog"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        battles = response.json()
        
        print("=" * 60)
        print("Limite de Batalhas - Clash Royale API")
        print("=" * 60)
        print(f"Total de batalhas retornadas: {len(battles)}")
        
        if battles:
            # Primeira batalha (mais recente)
            primeira = battles[0]
            primeira_data = primeira.get('battleTime', '')
            
            # Ultima batalha (mais antiga)
            ultima = battles[-1]
            ultima_data = ultima.get('battleTime', '')
            
            print(f"\nBatalha mais recente: {formatar_data(primeira_data)}")
            print(f"Batalha mais antiga: {formatar_data(ultima_data)}")
            
            # Calcula periodo coberto
            if primeira_data and ultima_data:
                try:
                    primeira_dt = datetime.strptime(primeira_data[:8], '%Y%m%d')
                    ultima_dt = datetime.strptime(ultima_data[:8], '%Y%m%d')
                    dias = (primeira_dt - ultima_dt).days
                    print(f"\nPeriodo coberto: {dias} dias")
                    print(f"Media de batalhas por dia: {len(battles) / max(dias, 1):.1f}")
                except:
                    pass
        
        print("\n" + "=" * 60)
        print("IMPORTANTE:")
        print("=" * 60)
        print("A API do Clash Royale retorna apenas as ULTIMAS")
        print("25-30 batalhas disponiveis, independente do periodo.")
        print("\nPara acumular mais dados ao longo do tempo:")
        print("- Execute o script regularmente (diariamente)")
        print("- Salve os dados em um banco de dados")
        print("- Combine os dados de diferentes execucoes")
        print("=" * 60)
        
    except Exception as e:
        print(f"Erro: {e}")

def formatar_data(battle_time_str: str) -> str:
    """Formata a data da batalha"""
    try:
        if len(battle_time_str) >= 8:
            year = battle_time_str[:4]
            month = battle_time_str[4:6]
            day = battle_time_str[6:8]
            hour = battle_time_str[9:11] if len(battle_time_str) > 9 else '00'
            minute = battle_time_str[11:13] if len(battle_time_str) > 11 else '00'
            return f"{day}/{month}/{year} {hour}:{minute}"
    except:
        pass
    return battle_time_str

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python verificar_limite_batalhas.py <token> <player_tag>")
        sys.exit(1)
    
    token = sys.argv[1]
    player_tag = sys.argv[2]
    
    verificar_batalhas(token, player_tag)

