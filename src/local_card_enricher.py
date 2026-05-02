#!/usr/bin/env python3
"""
Enriquecedor LOCAL - Não usa API externa
Usa dados pré-definidos das cartas do Clash Royale
"""

import pandas as pd
import os
from datetime import datetime

# Dados locais das cartas (sem necessidade de API)
CARD_DATA = {
    # Cartas comuns
    'Archers': {'raridade': 'Common', 'elixir': 3},
    'Knight': {'raridade': 'Common', 'elixir': 3},
    'Goblins': {'raridade': 'Common', 'elixir': 2},
    'Spear Goblins': {'raridade': 'Common', 'elixir': 2},
    'Skeletons': {'raridade': 'Common', 'elixir': 1},
    'Bats': {'raridade': 'Common', 'elixir': 2},
    'Fire Spirit': {'raridade': 'Common', 'elixir': 1},
    'Ice Spirit': {'raridade': 'Common', 'elixir': 1},
    'Cannon': {'raridade': 'Common', 'elixir': 3},
    'Arrows': {'raridade': 'Common', 'elixir': 3},
    'Zap': {'raridade': 'Common', 'elixir': 2},
    
    # Cartas especiais  
    'Musketeer': {'raridade': 'Rare', 'elixir': 4},
    'Valkyrie': {'raridade': 'Rare', 'elixir': 4},
    'Mini P.E.K.K.A': {'raridade': 'Rare', 'elixir': 4},
    'Hog Rider': {'raridade': 'Rare', 'elixir': 4},
    'Wizard': {'raridade': 'Rare', 'elixir': 5},
    'Fireball': {'raridade': 'Rare', 'elixir': 4},
    
    # Cartas épicas
    'Prince': {'raridade': 'Epic', 'elixir': 5},
    'Baby Dragon': {'raridade': 'Epic', 'elixir': 4},
    'Skeleton Army': {'raridade': 'Epic', 'elixir': 3},
    'Witch': {'raridade': 'Epic', 'elixir': 5},
    'Balloon': {'raridade': 'Epic', 'elixir': 5},
    'Giant': {'raridade': 'Epic', 'elixir': 5},
    
    # Cartas lendárias
    'Mega Knight': {'raridade': 'Legendary', 'elixir': 7},
    'Electro Wizard': {'raridade': 'Legendary', 'elixir': 4},
    'Lumberjack': {'raridade': 'Legendary', 'elixir': 4},
    'Magic Archer': {'raridade': 'Legendary', 'elixir': 4},
    'Bandit': {'raridade': 'Legendary', 'elixir': 3},
    'Royal Ghost': {'raridade': 'Legendary', 'elixir': 3},
    
    # Novas cartas
    'Royal Recruits': {'raridade': 'Common', 'elixir': 7},
    'Dart Goblin': {'raridade': 'Common', 'elixir': 3},
    'Goblin Gang': {'raridade': 'Common', 'elixir': 3},
    'Lightning': {'raridade': 'Epic', 'elixir': 6},
    'Barbarian Barrel': {'raridade': 'Epic', 'elixir': 2},
    'Fisherman': {'raridade': 'Legendary', 'elixir': 3}
}

def get_local_card_info(card_name):
    """Get card info from local database"""
    return CARD_DATA.get(card_name, {'raridade': 'Unknown', 'elixir': 0})

def enrich_local_data():
    """Enrich data using local card database"""
    
    csv_path = "src/data_csv_oficial/oponentes_ano_2026.csv"
    
    print("Lendo arquivo CSV...")
    df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
    
    print(f"Registros encontrados: {len(df)}")
    
    # Adicionar colunas se não existirem
    novas_colunas = [
        'raridade_deck_jogador', 'elixir_medio_jogador',
        'raridade_deck_oponente', 'elixir_medio_oponente',
        'data_enriquecimento_local'
    ]
    
    for coluna in novas_colunas:
        if coluna not in df.columns:
            df[coluna] = pd.NA
    
    # Processar apenas registros não enriquecidos
    mask_nao_processados = pd.isna(df['data_enriquecimento_local'])
    df_para_processar = df[mask_nao_processados].copy()
    
    print(f"Registros para processar: {len(df_para_processar)}")
    
    for idx, row in df_para_processar.iterrows():
        try:
            # Deck do jogador
            deck_jogador = str(row['deck_jogador']).split(' | ')
            elixirs_jogador = []
            raridades_jogador = []
            
            for carta in deck_jogador:
                info = get_local_card_info(carta.strip())
                elixirs_jogador.append(info['elixir'])
                raridades_jogador.append(info['raridade'])
            
            if elixirs_jogador:
                df.at[idx, 'elixir_medio_jogador'] = sum(elixirs_jogador) / len(elixirs_jogador)
                df.at[idx, 'raridade_deck_jogador'] = ' | '.join(raridades_jogador)
            
            # Deck do oponente
            deck_oponente = str(row['deck_oponente']).split(' | ')
            elixirs_oponente = []
            raridades_oponente = []
            
            for carta in deck_oponente:
                info = get_local_card_info(carta.strip())
                elixirs_oponente.append(info['elixir'])
                raridades_oponente.append(info['raridade'])
            
            if elixirs_oponente:
                df.at[idx, 'elixir_medio_oponente'] = sum(elixirs_oponente) / len(elixirs_oponente)
                df.at[idx, 'raridade_deck_oponente'] = ' | '.join(raridades_oponente)
            
            # Marcar como processado
            df.at[idx, 'data_enriquecimento_local'] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"Erro no registro {idx}: {e}")
            continue
    
    # Salvar resultados
    df.to_csv(csv_path, index=False, sep=';', encoding='utf-8')
    print(f"✅ Dados enriquecidos localmente! {len(df_para_processar)} registros processados")

def main():
    print("=" * 60)
    print("ENRIQUECEDOR LOCAL - SEM API")
    print("=" * 60)
    
    enrich_local_data()
    
    print("\n🎯 Processo concluído com sucesso!")

if __name__ == "__main__":
    main()