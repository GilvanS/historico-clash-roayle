import os
import requests
import pandas as pd
from dotenv import load_dotenv

# Carregar variaveis de ambiente
load_dotenv()

def update_cards_master():
    """
    Consome o endpoint /cards e gera um CSV master com nomes, IDs e URLs das imagens.
    Suporta cartas normais, herois (heroMedium) e evolucoes (evolutionMedium).
    """
    api_key = os.getenv('CR_API_TOKEN')
    if not api_key:
        print("Erro: CR_API_TOKEN nao encontrado no .env")
        return

    url = "https://api.clashroyale.com/v1/cards"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    print("Buscando lista completa de cartas da API...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Erro ao acessar API: {e}")
        return

    cards_list = []
    
    # Processar cada carta
    for item in data.get('items', []):
        name = item.get('name')
        card_id = item.get('id')
        max_level = item.get('maxLevel')
        max_evo_level = item.get('maxEvolutionLevel', 0)
        rarity = item.get('rarity', '')
        elixir = item.get('elixirCost', 0)
        icons = item.get('iconUrls', {})
        
        cards_list.append({
            'card_name': name,
            'card_id': card_id,
            'rarity': rarity,
            'elixir': elixir,
            'max_level': max_level,
            'max_evo_level': max_evo_level,
            'url_icon': icons.get('medium', ''),
            'url_hero': icons.get('heroMedium', ''),
            'url_evolution': icons.get('evolutionMedium', '')
        })

    # Criar DataFrame e salvar CSV
    df = pd.DataFrame(cards_list)
    
    # Ordenar por nome para facilitar busca
    df = df.sort_values(by='card_name')
    
    # Caminho absoluto para evitar erros
    project_root = r'a:\Workspace\historico-clash-roayle'
    output_path = os.path.join(project_root, 'src', 'data_csv_oficial', 'cards_master_icons.csv')
    
    # Garantir que o diretorio existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Salvar com encoding utf-8-sig para o Excel abrir direto com acentos
    df.to_csv(output_path, index=False, sep=';', encoding='utf-8-sig')
    
    print(f"Sucesso! {len(df)} cartas processadas.")
    print(f"Arquivo salvo em: {output_path}")

if __name__ == "__main__":
    update_cards_master()
