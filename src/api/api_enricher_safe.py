#!/usr/bin/env python3
"""
Enriquecedor Seguro de Dados - Versão Ilimitada com Proteções
Gerencia automaticamente limites da API e continua de onde parou
"""

import pandas as pd
import requests
import os
import time
from datetime import datetime
import json

class SafeClashRoyaleEnricher:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        self.base_url = 'https://api.clashroyale.com/v1'
        self.rate_limit_remaining = 1000  # Assume inicial
        self.rate_limit_reset = 0
        
    def check_rate_limit(self):
        """Verifica e respeita rate limit da API"""
        if self.rate_limit_remaining <= 5:
            wait_time = max(self.rate_limit_reset - time.time(), 0) + 2
            if wait_time > 0:
                print(f"⏰ Rate limit atingido. Aguardando {wait_time:.0f} segundos...")
                time.sleep(wait_time)
                self.rate_limit_remaining = 1000  # Reset após espera
        
    def api_request(self, url):
        """Request seguro com gestão de rate limit"""
        self.check_rate_limit()
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            
            # Atualizar rate limit
            if 'x-ratelimit-remaining' in response.headers:
                self.rate_limit_remaining = int(response.headers['x-ratelimit-remaining'])
            if 'x-ratelimit-reset' in response.headers:
                self.rate_limit_reset = int(response.headers['x-ratelimit-reset'])
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("🚨 Rate limit atingido! Aguardando...")
                time.sleep(30)
                return self.api_request(url)  # Retry
            else:
                print(f"❌ API Error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"🌐 Network error: {e}")
            time.sleep(5)
            return None
    
    def get_card_info(self, card_name):
        """Get card information with cache"""
        if not card_name or card_name == 'nan':
            return {}
            
        cache_file = f"src/cache/cards/{card_name.lower().replace(' ', '_')}.json"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        # Verificar cache primeiro (24h)
        if os.path.exists(cache_file):
            mod_time = os.path.getmtime(cache_file)
            if time.time() - mod_time < 86400:  # 24 horas
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        # Buscar na API
        card_data = {}
        response = self.api_request(f'{self.base_url}/cards')
        
        if response and 'items' in response:
            for card in response['items']:
                if card['name'].lower() == card_name.lower():
                    card_data = {
                        'raridade': card.get('rarity', ''),
                        'elixir': card.get('elixirCost', ''),
                        'tipo': card.get('type', '')
                    }
                    # Salvar em cache
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(card_data, f)
                    break
        
        return card_data
    
    def get_player_details(self, player_tag):
        """Get player details with cache"""
        if not player_tag or player_tag == 'nan':
            return {}
        
        cache_file = f"src/cache/players/{player_tag.replace('#', '')}.json"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        # Verificar cache (1h para dados de player)
        if os.path.exists(cache_file):
            mod_time = os.path.getmtime(cache_file)
            if time.time() - mod_time < 3600:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        # Buscar na API
        player_data = {}
        response = self.api_request(
            f'{self.base_url}/players/%23{player_tag.replace("#", "")}'
        )
        
        if response:
            player_data = {
                'nivel_jogador': response.get('expLevel', ''),
                'trofeus_melhor': response.get('bestTrophies', ''),
                'vitorias_total': response.get('wins', ''),
                'trio_vitorias': response.get('threeCrownWins', ''),
                'ultima_atualizacao': datetime.now().isoformat()
            }
            # Salvar em cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(player_data, f)
        
        return player_data
    
    def enrich_data(self, csv_path, max_records=None):
        """Enrich data safely with progress tracking"""
        
        print("📖 Lendo arquivo CSV...")
        
        try:
            # Estado de progresso
            progress_file = "src/cache/enrichment_progress.json"
            os.makedirs(os.path.dirname(progress_file), exist_ok=True)
            
            # Carregar progresso anterior
            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                last_processed = progress.get('last_processed_idx', 0)
            else:
                progress = {'last_processed_idx': 0}
                last_processed = 0
            
            # Ler CSV
            df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
            total_records = len(df)
            print(f"📊 Total de registros: {total_records}")
            print(f"⚡ Continuando do registro: {last_processed}")
            
            # Novas colunas
            novas_colunas = [
                'raridade_deck_jogador', 'elixir_medio_jogador', 
                'raridade_deck_oponente', 'elixir_medio_oponente',
                'nivel_jogador', 'trofeus_melhor', 'vitorias_total', 'trio_vitorias',
                'data_enriquecimento'
            ]
            
            for coluna in novas_colunas:
                if coluna not in df.columns:
                    df[coluna] = pd.NA
            
            # Processar registros
            start_idx = last_processed
            end_idx = total_records if max_records is None else min(start_idx + max_records, total_records)
            
            processed_count = 0
            
            for idx in range(start_idx, end_idx):
                try:
                    # Pular já processados
                    if not pd.isna(df.at[idx, 'data_enriquecimento']):
                        continue
                    
                    # Sua tag player (MODIFIQUE AQUI!)
                    YOUR_PLAYER_TAG = "#2B2Y0R80"
                    
                    # Informações do jogador
                    if pd.isna(df.at[idx, 'nivel_jogador']):
                        player_info = self.get_player_details(YOUR_PLAYER_TAG)
                        for key, value in player_info.items():
                            if key != 'ultima_atualizacao':
                                df.at[idx, key] = value
                    
                    # Informações das cartas (jogador)
                    if pd.isna(df.at[idx, 'elixir_medio_jogador']):
                        deck_jogador = str(df.at[idx, 'deck_jogador']).split(' | ')
                        elixirs = []
                        raridades = []
                        
                        for carta in deck_jogador:
                            info = self.get_card_info(carta.strip())
                            if info and info.get('elixir'):
                                elixirs.append(float(info['elixir']))
                            if info and info.get('raridade'):
                                raridades.append(info['raridade'])
                        
                        if elixirs:
                            df.at[idx, 'elixir_medio_jogador'] = sum(elixirs) / len(elixirs)
                        if raridades:
                            df.at[idx, 'raridade_deck_jogador'] = ' | '.join(raridades)
                    
                    # Informações das cartas (oponente)
                    if pd.isna(df.at[idx, 'elixir_medio_oponente']):
                        deck_oponente = str(df.at[idx, 'deck_oponente']).split(' | ')
                        elixirs = []
                        raridades = []
                        
                        for carta in deck_oponente:
                            info = self.get_card_info(carta.strip())
                            if info and info.get('elixir'):
                                elixirs.append(float(info['elixir']))
                            if info and info.get('raridade'):
                                raridades.append(info['raridade'])
                        
                        if elixirs:
                            df.at[idx, 'elixir_medio_oponente'] = sum(elixirs) / len(elixirs)
                        if raridades:
                            df.at[idx, 'raridade_deck_oponente'] = ' | '.join(raridades)
                    
                    # Marcar como processado
                    df.at[idx, 'data_enriquecimento'] = datetime.now().isoformat()
                    processed_count += 1
                    
                    # Salvar progresso a cada 10 registros
                    if processed_count % 10 == 0:
                        progress['last_processed_idx'] = idx + 1
                        with open(progress_file, 'w', encoding='utf-8') as f:
                            json.dump(progress, f)
                        
                        df.to_csv(csv_path, index=False, sep=';', encoding='utf-8')
                        print(f"💾 Progresso salvo: {idx + 1}/{total_records}")
                    
                    # Feedback visual
                    if processed_count % 5 == 0:
                        print(f"🔧 Processados: {processed_count} | Rate Limit: {self.rate_limit_remaining}")
                    
                except Exception as e:
                    print(f"❌ Erro no registro {idx}: {e}")
                    continue
            
            # Salvar final
            progress['last_processed_idx'] = end_idx
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f)
            
            df.to_csv(csv_path, index=False, sep=';', encoding='utf-8')
            
            print(f"🎉 Processo concluído! Processados: {processed_count} registros")
            print(f"📈 Rate Limit final: {self.rate_limit_remaining}")
            
            if self.rate_limit_remaining <= 50:
                print("⚠️  Rate limit baixo. Continue mais tarde.")
            
        except Exception as e:
            print(f"💥 Erro crítico: {e}")

def main():
    print("=" * 70)
    print("ENRIQUECEDOR SEGURO - CLASH ROYALE API")
    print("=" * 70)
    
    # API Key (configure no .env)
    api_key = os.getenv('CLASH_ROYALE_API_KEY')
    if not api_key:
        print("❌ Configure CLASH_ROYALE_API_KEY no arquivo .env")
        print("💡 Formato: CLASH_ROYALE_API_KEY=sua-chave-aqui")
        return
    
    enricher = SafeClashRoyaleEnricher(api_key)
    
    # Enriquecer dados
    csv_path = f"data/csv/oponentes_ano_{datetime.now().year}.csv"
    
    print("🚀 Iniciando enriquecimento...")
    print("📝 Modifique YOUR_PLAYER_TAG no código com sua tag real!")
    print("⏰ Este processo pode levar vários minutos...")
    
    enricher.enrich_data(csv_path)
    
    print("\n✅ Processo finalizado com segurança!")

if __name__ == "__main__":
    main()