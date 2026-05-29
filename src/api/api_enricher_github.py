#!/usr/bin/env python3
"""
Enriquecedor para GitHub Actions - Usa secrets seguras
Versão otimizada para execução automatizada
"""

import pandas as pd
import requests
import os
import time
from datetime import datetime
import json
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

class GitHubEnricher:
    def __init__(self):
        # Usar secret do GitHub Actions ou variáveis do .env
        self.api_key = os.environ.get('CLASH_ROYALE_API_KEY') or os.environ.get('CR_API_TOKEN')
        self.player_tag = os.environ.get('PLAYER_TAG') or os.environ.get('CR_PLAYER_TAG', '#2B2Y0R80')
        
        if not self.api_key:
            raise ValueError("CLASH_ROYALE_API_KEY não encontrada nas secrets")
            
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
        self.base_url = 'https://api.clashroyale.com/v1'
        self.rate_limit_remaining = 1000
    
    def safe_api_request(self, url):
        """Request seguro com gestão de rate limit"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                if 'x-ratelimit-remaining' in response.headers:
                    self.rate_limit_remaining = int(response.headers['x-ratelimit-remaining'])
                return response.json()
            elif response.status_code == 429:
                print("Rate limit atingido. Aguardando 30 segundos...")
                time.sleep(30)
                return self.safe_api_request(url)
            else:
                print(f"API Error {response.status_code}")
                return None
                
        except requests.exceptions.RequestException:
            print("Erro de rede. Aguardando 5 segundos...")
            time.sleep(5)
            return None
    
    def get_card_info(self, card_name):
        """Informações da carta com cache simples"""
        if not card_name or pd.isna(card_name):
            return {}
            
        # Cache em memória para mesma execução
        response = self.safe_api_request(f'{self.base_url}/cards')
        if response and 'items' in response:
            for card in response['items']:
                if card['name'].lower() == str(card_name).lower():
                    return {
                        'raridade': card.get('rarity', ''),
                        'elixir': card.get('elixirCost', '')
                    }
        return {}
    
    def enrich_batch(self, df_batch):
        """Enriquecer um lote de registros"""
        for idx, row in df_batch.iterrows():
            try:
                # Informações das cartas do jogador
                deck_jogador = str(row['deck_jogador']).split(' | ')
                elixirs_jogador = []
                
                for carta in deck_jogador:
                    info = self.get_card_info(carta.strip())
                    if info and info.get('elixir'):
                        elixirs_jogador.append(float(info['elixir']))
                
                if elixirs_jogador:
                    df_batch.at[idx, 'elixir_medio_jogador'] = sum(elixirs_jogador) / len(elixirs_jogador)
                
                # Informações das cartas do oponente
                deck_oponente = str(row['deck_oponente']).split(' | ')
                elixirs_oponente = []
                
                for carta in deck_oponente:
                    info = self.get_card_info(carta.strip())
                    if info and info.get('elixir'):
                        elixirs_oponente.append(float(info['elixir']))
                
                if elixirs_oponente:
                    df_batch.at[idx, 'elixir_medio_oponente'] = sum(elixirs_oponente) / len(elixirs_oponente)
                
                # Marcar como processado
                df_batch.at[idx, 'data_enriquecimento'] = datetime.now().isoformat()
                
            except Exception as e:
                print(f"Erro no registro {idx}: {e}")
                continue
        
        return df_batch
    
    def run(self, csv_path, batch_size=20):
        """Execução principal otimizada para GitHub Actions"""
        
        print(f"Iniciando enriquecimento para: {self.player_tag}")
        print(f"Rate Limit inicial: {self.rate_limit_remaining}")
        
        try:
            # Ler CSV
            df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
            
            # Adicionar colunas se não existirem
            colunas_novas = ['elixir_medio_jogador', 'elixir_medio_oponente', 'data_enriquecimento']
            for coluna in colunas_novas:
                if coluna not in df.columns:
                    df[coluna] = pd.NA
            
            # Processar apenas registros não enriquecidos (máximo 100 por execução)
            mask_nao_processados = pd.isna(df['data_enriquecimento'])
            df_para_processar = df[mask_nao_processados].head(100)
            
            total_para_processar = len(df_para_processar)
            print(f"Registros para processar: {total_para_processar}")
            
            if total_para_processar == 0:
                print("Nenhum registro novo para processar.")
                return
            
            # Processar em lotes
            for i in range(0, total_para_processar, batch_size):
                batch = df_para_processar.iloc[i:i + batch_size].copy()
                df_processed_batch = self.enrich_batch(batch)
                
                # Atualizar DataFrame original
                df.update(df_processed_batch)
                
                # Salvar progresso
                df.to_csv(csv_path, index=False, sep=';', encoding='utf-8')
                
                print(f"Lote {i//batch_size + 1} processado. Rate Limit: {self.rate_limit_remaining}")
                
                # Pausa entre lotes
                if self.rate_limit_remaining < 100:
                    print("Rate limit baixo. Aguardando...")
                    time.sleep(10)
                else:
                    time.sleep(1)
            
            print(f"✅ Processamento concluído! {total_para_processar} registros enriquecidos")
            
        except Exception as e:
            print(f"❌ Erro crítico: {e}")
            raise

def main():
    print("=" * 60)
    print("GITHUB ACTIONS - ENRIQUECEDOR DE DADOS")
    print("=" * 60)
    
    try:
        enricher = GitHubEnricher()
        csv_path = "data/csv/oponentes_ano_2026.csv"
        enricher.run(csv_path)
        
    except ValueError as e:
        print(f"Configuração: {e}")
        print("Certifique-se de configurar as variáveis de ambiente:")
        print("- CLASH_ROYALE_API_KEY ou CR_API_TOKEN")
        print("- PLAYER_TAG ou CR_PLAYER_TAG (opcional)")
        print("No .env local: CR_API_TOKEN e CR_PLAYER_TAG")
        print("No GitHub Secrets: CLASH_ROYALE_API_KEY e PLAYER_TAG")
    except Exception as e:
        print(f"Erro inesperado: {e}")

if __name__ == "__main__":
    main()