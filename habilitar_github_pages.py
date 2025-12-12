#!/usr/bin/env python3
"""
Script para habilitar GitHub Pages via API do GitHub
"""

import requests
import os
import sys

def habilitar_github_pages(repo_owner: str, repo_name: str, token: str):
    """Habilita GitHub Pages para o repositorio"""
    
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pages"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Configuracao para usar GitHub Actions como source
    data = {
        "source": {
            "branch": "main",
            "path": "/"
        },
        "build_type": "workflow"
    }
    
    try:
        # Primeiro, verifica se ja esta habilitado
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("GitHub Pages ja esta habilitado!")
            print(f"URL: {response.json().get('html_url', 'N/A')}")
            return True
        
        # Tenta habilitar
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 201:
            print("✅ GitHub Pages habilitado com sucesso!")
            print(f"URL: {response.json().get('html_url', 'N/A')}")
            return True
        elif response.status_code == 409:
            print("⚠️ GitHub Pages ja esta habilitado ou em processo de configuracao")
            return True
        else:
            print(f"❌ Erro ao habilitar GitHub Pages: {response.status_code}")
            print(f"Resposta: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Erro na requisicao: {e}")
        return False

def main():
    """Funcao principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Habilita GitHub Pages via API')
    parser.add_argument('--owner', type=str, default='GilvanS', help='Proprietario do repositorio')
    parser.add_argument('--repo', type=str, default='clash-royale-history', help='Nome do repositorio')
    parser.add_argument('--token', type=str, help='GitHub Personal Access Token (ou use GITHUB_TOKEN env var)')
    
    args = parser.parse_args()
    
    # Tenta pegar token do ambiente se nao foi passado
    token = args.token or os.getenv('GITHUB_TOKEN')
    
    if not token:
        print("❌ Erro: Token do GitHub nao fornecido")
        print("Use --token ou defina a variavel de ambiente GITHUB_TOKEN")
        print("\nPara criar um token:")
        print("1. Vá para: https://github.com/settings/tokens")
        print("2. Clique em 'Generate new token (classic)'")
        print("3. Selecione o escopo 'repo' (acesso completo aos repositorios)")
        print("4. Copie o token gerado")
        sys.exit(1)
    
    print(f"Habilitando GitHub Pages para {args.owner}/{args.repo}...")
    success = habilitar_github_pages(args.owner, args.repo, token)
    
    if success:
        print("\n✅ Pronto! O GitHub Pages esta habilitado.")
        print("Aguarde alguns minutos para o primeiro deploy ser concluido.")
        print(f"Seu dashboard estara disponivel em: https://{args.owner.lower()}.github.io/{args.repo}/")
    else:
        print("\n❌ Nao foi possivel habilitar automaticamente.")
        print("Por favor, habilite manualmente:")
        print(f"1. Vá para: https://github.com/{args.owner}/{args.repo}/settings/pages")
        print("2. Em 'Source', selecione 'GitHub Actions'")
        print("3. Clique em 'Save'")

if __name__ == "__main__":
    main()

