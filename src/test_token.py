#!/usr/bin/env python3
"""
Script simples para testar o token da API do Clash Royale
"""

import requests
import sys

def test_token(token: str, player_tag: str):
    """Testa o token com endpoints simples"""
    base_url = "https://proxy.royaleapi.dev/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    clean_tag = player_tag.replace('#', '')
    
    print("=" * 60)
    print("Teste de Token - Clash Royale API")
    print("=" * 60)
    print(f"Player Tag: {player_tag}")
    print(f"IP atual: Verificando...")
    print("=" * 60)
    
    # Teste 1: Endpoint simples - Informacoes do jogador
    print("\n1. Testando endpoint /players (informacoes basicas)...")
    url1 = f"{base_url}/players/%23{clean_tag}"
    try:
        r1 = requests.get(url1, headers=headers, timeout=10)
        print(f"   Status: {r1.status_code}")
        if r1.status_code == 200:
            data = r1.json()
            print(f"   [OK] Sucesso! Nome: {data.get('name', 'N/A')}")
            print(f"   Trofeus: {data.get('trophies', 'N/A')}")
        else:
            print(f"   [ERRO] Status {r1.status_code}: {r1.text[:200]}")
    except Exception as e:
        print(f"   [ERRO] Excecao: {e}")
    
    # Teste 2: Endpoint battlelog
    print("\n2. Testando endpoint /players/battlelog...")
    url2 = f"{base_url}/players/%23{clean_tag}/battlelog"
    try:
        r2 = requests.get(url2, headers=headers, timeout=10)
        print(f"   Status: {r2.status_code}")
        if r2.status_code == 200:
            data = r2.json()
            print(f"   [OK] Sucesso! Batalhas encontradas: {len(data)}")
        else:
            print(f"   [ERRO] Status {r2.status_code}: {r2.text[:200]}")
    except Exception as e:
        print(f"   [ERRO] Excecao: {e}")
    
    print("\n" + "=" * 60)
    print("Teste concluido!")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python test_token.py <token> <player_tag>")
        print("Exemplo: python test_token.py 'eyJ0eXAi...' '#2QR292P'")
        sys.exit(1)
    
    token = sys.argv[1]
    player_tag = sys.argv[2]
    
    test_token(token, player_tag)

