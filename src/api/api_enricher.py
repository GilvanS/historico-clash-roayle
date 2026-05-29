#!/usr/bin/env python3
"""
Enriquecedor de Dados da API Clash Royale
Adiciona novas colunas e dados das APIs não utilizadas
"""

import pandas as pd
import requests
import os
from datetime import datetime
import time

class ClashRoyaleEnricher:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        self.base_url = 'https://api.clashroyale.com/v1'
    
    def get_card_info(self, card_name):
        """Get information about a specific card"""
        try:
            response = requests.get(
                f'{self.base_url}/cards',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                cards = response.json().get('items', [])
                for card in cards:
                    if card['name'].lower() == card_name.lower():
                        return {
                            'raridade': card.get('rarity', ''),
                            'elixir': card.get('elixirCost', ''),
                            'tipo': card.get('type', '')
                        }
            return {}
        except:
            return {}
    
    def get_player_details(self, player_tag):
        """Get detailed player information"""
        try:
            response = requests.get(
                f'{self.base_url}/players/%23{player_tag.replace("#", "")}',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'nivel_jogador': data.get('expLevel', ''),
                    'trofeus_melhor': data.get('bestTrophies', ''),
                    'vitorias_total': data.get('wins', ''),
                    'trio_vitorias': data.get('threeCrownWins', '')
                }
            return {}
        except:
            return {}
    
    def enrich_battle_data(self, csv_path):
        """Enrich existing CSV with additional API data"""
        
        print("LENDO arquivo CSV...")
        
        try:
            # Ler CSV existente
            df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
            print(f"Registros encontrados: {len(df)}")
            
            # Novas colunas que serão adicionadas
            novas_colunas = [
                'raridade_deck_jogador', 'elixir_medio_jogador', 'tipo_deck_jogador',
                'raridade_deck_oponente', 'elixir_medio_oponente', 'tipo_deck_oponente',
                'nivel_jogador', 'trofeus_melhor', 'vitorias_total', 'trio_vitorias'
            ]
            
            # Adicionar colunas vazias se não existirem
            for coluna in novas_colunas:
                if coluna not in df.columns:
                    df[coluna] = ''
            
            # Processar cada registro (apenas os mais recentes para não sobrecarregar API)
            for idx, row in df.tail(50).iterrows():  # Só últimos 50 registros
                try:
                    # Informações das cartas do jogador
                    if pd.isna(df.at[idx, 'raridade_deck_jogador']):
                        deck_jogador = str(row['deck_jogador']).split(' | ')
                        raridades = []
                        elixirs = []
                        
                        for carta in deck_jogador:
                            info = self.get_card_info(carta.strip())
                            if info:
                                raridades.append(info.get('raridade', ''))
                                elixirs.append(info.get('elixir', 0))
                        
                        if raridades:
                            df.at[idx, 'raridade_deck_jogador'] = ' | '.join(raridades)
                        if elixirs:
                            df.at[idx, 'elixir_medio_jogador'] = sum(elixirs) / len(elixirs)
                    
                    # Informações do jogador
                    if pd.isna(df.at[idx, 'nivel_jogador']):
                        player_tag = "#2B2Y0R80"  # SUA TAG AQUI
                        player_info = self.get_player_details(player_tag)
                        for key, value in player_info.items():
                            df.at[idx, key] = value
                    
                    # Progresso a cada 10 registros
                    if idx % 10 == 0:
                        print(f"Processados {idx}/{len(df)} registros")
                    
                    # Respeitar rate limit da API
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Erro no registro {idx}: {e}")
                    continue
            
            # Salvar CSV enriquecido
            df.to_csv(csv_path, index=False, sep=';', encoding='utf-8')
            print(f"CSV enriquecido salvo: {csv_path}")
            print(f"Novas colunas adicionadas: {novas_colunas}")
            
        except Exception as e:
            print(f"Erro ao processar CSV: {e}")

def main():
    print("=" * 60)
    print("ENRIQUECEDOR DE DADOS CLASH ROYALE")
    print("=" * 60)
    
    # Sua API Key do Clash Royale (do .env)
    api_key = os.getenv('CLASH_ROYALE_API_KEY', 'sua-api-key-aqui')
    
    if api_key == 'sua-api-key-aqui':
        print("❌ Configure a CLASH_ROYALE_API_KEY no .env")
        return
    
    enricher = ClashRoyaleEnricher(api_key)
    
    # Enriquecer arquivo principal
    csv_path = "data/csv/oponentes_ano_2026.csv"
    enricher.enrich_battle_data(csv_path)
    
    print("\n✅ Processo concluído!")

if __name__ == "__main__":
    main()